package de.smartesc.config;

import android.annotation.SuppressLint;
import android.bluetooth.*;
import android.bluetooth.le.*;
import android.content.Context;
import android.os.Handler;
import android.os.Looper;

import java.io.ByteArrayOutputStream;
import java.security.SecureRandom;
import java.util.*;

public final class NinebotBleClient {
    public interface Listener {
        void onStatus(String text);
        void onReady(boolean encrypted);
        void onFrame(SescProtocol.Frame frame);
        void onDisconnected();
    }

    private static final UUID NUS_SERVICE = UUID.fromString("6e400001-b5a3-f393-e0a9-e50e24dcca9e");
    private static final UUID NUS_TX = UUID.fromString("6e400002-b5a3-f393-e0a9-e50e24dcca9e");
    private static final UUID NUS_RX = UUID.fromString("6e400003-b5a3-f393-e0a9-e50e24dcca9e");
    private static final UUID CCCD = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");

    private final Context context;
    private final Listener listener;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final BluetoothAdapter adapter;
    private BluetoothLeScanner scanner;
    private BluetoothGatt gatt;
    private BluetoothGattCharacteristic tx;
    private BluetoothGattCharacteristic rx;

    private LegacyNinebotCrypto crypto;
    private boolean encryptedMode = true;
    private boolean ready;
    private int pairState;
    private byte[] serial = new byte[14];
    private byte[] appRandom = new byte[16];

    private final ArrayDeque<byte[]> writeQueue = new ArrayDeque<>();
    private boolean writeBusy;
    private final ByteArrayOutputStream rxBuffer = new ByteArrayOutputStream();

    private static final int PAIR_WAIT_5B = 1;
    private static final int PAIR_WAIT_5C = 2;
    private static final int PAIR_WAIT_5D = 3;
    private static final int PAIR_READY = 4;

    public NinebotBleClient(Context context, Listener listener) {
        this.context = context.getApplicationContext();
        this.listener = listener;
        BluetoothManager bm = (BluetoothManager) context.getSystemService(Context.BLUETOOTH_SERVICE);
        adapter = bm.getAdapter();
    }

    @SuppressLint("MissingPermission")
    public void scanAndConnect() {
        disconnect();
        if (adapter == null || !adapter.isEnabled()) {
            listener.onStatus("Bluetooth ist ausgeschaltet");
            return;
        }
        scanner = adapter.getBluetoothLeScanner();
        listener.onStatus("Suche Ninebot…");
        scanner.startScan(scanCallback);
        handler.postDelayed(() -> {
            if (scanner != null) {
                try { scanner.stopScan(scanCallback); } catch (Exception ignored) {}
                listener.onStatus("Kein G30 gefunden");
            }
        }, 10000);
    }

    private final ScanCallback scanCallback = new ScanCallback() {
        @Override @SuppressLint("MissingPermission")
        public void onScanResult(int callbackType, ScanResult result) {
            BluetoothDevice d = result.getDevice();
            String name = d.getName();
            if (name == null && result.getScanRecord() != null) name = result.getScanRecord().getDeviceName();
            String n = name == null ? "" : name.toLowerCase(Locale.ROOT);
            if (n.contains("nbscooter") || n.contains("ninebot") || n.contains("segway")) {
                if (scanner != null) scanner.stopScan(this);
                scanner = null;
                listener.onStatus("Verbinde " + (name == null ? d.getAddress() : name));
                gatt = d.connectGatt(context, false, gattCallback, BluetoothDevice.TRANSPORT_LE);
            }
        }

        @Override public void onScanFailed(int errorCode) {
            listener.onStatus("BLE-Scan Fehler " + errorCode);
        }
    };

    @SuppressLint("MissingPermission")
    public void disconnect() {
        ready = false;
        pairState = 0;
        handler.removeCallbacksAndMessages(null);
        if (scanner != null) {
            try { scanner.stopScan(scanCallback); } catch (Exception ignored) {}
            scanner = null;
        }
        if (gatt != null) {
            try { gatt.disconnect(); } catch (Exception ignored) {}
            try { gatt.close(); } catch (Exception ignored) {}
            gatt = null;
        }
        tx = rx = null;
        synchronized (writeQueue) {
            writeQueue.clear();
            writeBusy = false;
        }
        synchronized (rxBuffer) { rxBuffer.reset(); }
    }

    public boolean isReady() { return ready; }

    public void sendConfig(int arg, byte[] payload) {
        if (!ready) {
            listener.onStatus("Noch nicht verbunden/authentifiziert");
            return;
        }
        sendNinebot(SescProtocol.buildConfig(arg,payload));
    }

    private final BluetoothGattCallback gattCallback = new BluetoothGattCallback() {
        @Override @SuppressLint("MissingPermission")
        public void onConnectionStateChange(BluetoothGatt g, int status, int newState) {
            if (newState == BluetoothProfile.STATE_CONNECTED) {
                listener.onStatus("BLE verbunden, suche UART…");
                g.discoverServices();
            } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                ready = false;
                listener.onStatus("Verbindung getrennt");
                listener.onDisconnected();
            }
        }

        @Override @SuppressLint("MissingPermission")
        public void onServicesDiscovered(BluetoothGatt g, int status) {
            BluetoothGattService s = g.getService(NUS_SERVICE);
            if (s == null) {
                listener.onStatus("Ninebot UART-Service nicht gefunden");
                return;
            }
            tx = s.getCharacteristic(NUS_TX);
            rx = s.getCharacteristic(NUS_RX);
            if (tx == null || rx == null) {
                listener.onStatus("Ninebot UART-Characteristics fehlen");
                return;
            }
            g.setCharacteristicNotification(rx,true);
            BluetoothGattDescriptor d = rx.getDescriptor(CCCD);
            if (d == null) {
                listener.onStatus("CCCD fehlt");
                return;
            }
            d.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
            g.writeDescriptor(d);
        }

        @Override public void onDescriptorWrite(BluetoothGatt g, BluetoothGattDescriptor descriptor, int status) {
            if (CCCD.equals(descriptor.getUuid()) && status == BluetoothGatt.GATT_SUCCESS) startHandshake();
        }

        @Override public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic characteristic) {
            if (NUS_RX.equals(characteristic.getUuid())) onRxChunk(characteristic.getValue());
        }

        @Override public void onCharacteristicWrite(BluetoothGatt g, BluetoothGattCharacteristic characteristic, int status) {
            synchronized (writeQueue) {
                writeBusy = false;
            }
            writeNext();
        }
    };

    private void startHandshake() {
        String name = "";
        try { name = gatt.getDevice().getName(); } catch (Exception ignored) {}
        crypto = new LegacyNinebotCrypto(name == null ? "" : name);
        encryptedMode = true;
        ready = false;
        pairState = PAIR_WAIT_5B;
        listener.onStatus("Authentifiziere Legacy-G30 BLE…");
        sendEncryptedPair(0x5B,0,new byte[0]);

        handler.postDelayed(() -> {
            if (!ready && pairState == PAIR_WAIT_5B) {
                encryptedMode = false;
                pairState = PAIR_READY;
                ready = true;
                synchronized (rxBuffer) { rxBuffer.reset(); }
                listener.onStatus("Keine Crypto-Antwort, probiere Legacy/Plain");
                listener.onReady(false);
            }
        }, 2500);
    }

    private void sendEncryptedPair(int cmd,int arg,byte[] payload) {
        byte[] p = SescProtocol.buildFrame(0x3E,0x21,cmd,arg,payload);
        queueBytes(crypto.encrypt(p));
    }

    private void sendNinebot(byte[] plain) {
        queueBytes(encryptedMode ? crypto.encrypt(plain) : plain);
    }

    private void schedule5c() {
        handler.postDelayed(() -> {
            if (!ready && pairState == PAIR_WAIT_5C) {
                sendEncryptedPair(0x5C,0,appRandom);
                schedule5c();
            }
        },1000);
    }

    private void onRxChunk(byte[] chunk) {
        if (chunk == null || chunk.length == 0) return;
        synchronized (rxBuffer) {
            rxBuffer.write(chunk,0,chunk.length);
            while (true) {
                byte[] b = rxBuffer.toByteArray();
                int start = findHeader(b);
                if (start < 0) {
                    if (b.length > 2) rxBuffer.reset();
                    return;
                }
                if (start > 0) {
                    rxBuffer.reset();
                    rxBuffer.write(b,start,b.length-start);
                    b = rxBuffer.toByteArray();
                }
                if (b.length < 3) return;
                int len = b[2] & 0xFF;
                int total = len + (encryptedMode ? 15 : 9);
                if (total < 9 || total > 270) {
                    rxBuffer.reset();
                    return;
                }
                if (b.length < total) return;

                byte[] msg = Arrays.copyOfRange(b,0,total);
                byte[] remain = Arrays.copyOfRange(b,total,b.length);
                rxBuffer.reset();
                rxBuffer.write(remain,0,remain.length);
                handleMessage(msg);
            }
        }
    }

    private static int findHeader(byte[] b) {
        for (int i=0;i+1<b.length;i++) if ((b[i]&0xFF)==0x5A && (b[i+1]&0xFF)==0xA5) return i;
        return -1;
    }

    private void handleMessage(byte[] wire) {
        byte[] plain = encryptedMode ? crypto.decrypt(wire) : wire;
        SescProtocol.Frame f = SescProtocol.parse(plain);
        if (f == null) return;

        if (!ready && encryptedMode && f.src == 0x21 && f.dst == 0x3E) {
            if (f.cmd == 0x5B && pairState == PAIR_WAIT_5B) {
                if (f.payload.length >= 30) {
                    serial = Arrays.copyOfRange(f.payload,16,30);
                    new SecureRandom().nextBytes(appRandom);
                    crypto.setAppRandom(appRandom);
                    pairState = PAIR_WAIT_5C;
                    listener.onStatus("Power-Taste am Scooter drücken…");
                    sendEncryptedPair(0x5C,0,appRandom);
                    schedule5c();
                }
                return;
            }
            if (f.cmd == 0x5C && pairState == PAIR_WAIT_5C) {
                if (f.arg == 1) {
                    pairState = PAIR_WAIT_5D;
                    listener.onStatus("Pairing bestätigt…");
                    sendEncryptedPair(0x5D,0,serial);
                }
                return;
            }
            if (f.cmd == 0x5D && pairState == PAIR_WAIT_5D && f.arg == 1) {
                pairState = PAIR_READY;
                ready = true;
                listener.onStatus("SmartESC BLE bereit");
                listener.onReady(true);
                return;
            }
        }

        if (ready) listener.onFrame(f);
    }

    private void queueBytes(byte[] data) {
        synchronized (writeQueue) {
            for (int p=0;p<data.length;p+=20) {
                writeQueue.add(Arrays.copyOfRange(data,p,Math.min(data.length,p+20)));
            }
        }
        writeNext();
    }

    @SuppressLint("MissingPermission")
    private void writeNext() {
        BluetoothGatt g = gatt;
        BluetoothGattCharacteristic c = tx;
        if (g == null || c == null) return;
        byte[] next;
        synchronized (writeQueue) {
            if (writeBusy) return;
            next = writeQueue.poll();
            if (next == null) return;
            writeBusy = true;
        }
        c.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);
        c.setValue(next);
        if (!g.writeCharacteristic(c)) {
            synchronized (writeQueue) { writeBusy = false; }
            handler.postDelayed(this::writeNext,30);
        }
    }
}
