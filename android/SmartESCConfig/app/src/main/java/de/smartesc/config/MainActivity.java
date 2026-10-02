package de.smartesc.config;

import android.Manifest;
import android.app.*;
import android.os.*;
import android.content.pm.PackageManager;
import android.graphics.Typeface;
import android.view.*;
import android.widget.*;

import java.util.Locale;

public class MainActivity extends Activity implements NinebotBleClient.Listener {
    private static final int REQ_PERMS = 10;

    private NinebotBleClient ble;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean starProfileValid;

    private TextView status, live, detectStatus;
    private Button connect;

    private EditText battA, wheelMm, poles, enterKmh, exitKmh, switchIq, settleMs, detectLoss;
    private CheckBox autoDelta;

    private EditText starR, starL, starFlux, starPhase;
    private EditText deltaR, deltaL, deltaFlux, deltaPhase;

    private final Runnable poll = new Runnable() {
        @Override public void run() {
            if (ble != null && ble.isReady()) {
                ble.sendConfig(SescProtocol.TELEMETRY,new byte[0]);
                ble.sendConfig(SescProtocol.DETECT_STATUS,new byte[0]);
            }
            handler.postDelayed(this,500);
        }
    };

    @Override public void onCreate(Bundle b) {
        super.onCreate(b);
        ble = new NinebotBleClient(this,this);
        setContentView(buildUi());
    }

    private View buildUi() {
        ScrollView scroll = new ScrollView(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(16),dp(12),dp(16),dp(30));
        scroll.addView(root);

        TextView title = text("SmartESC Config",24,true);
        root.addView(title);
        root.addView(text("G30D · SHU-Lite · STAR/DELTA Setup",14,false));

        status = text("Nicht verbunden",14,true);
        root.addView(status);

        connect = new Button(this);
        connect.setText("G30 suchen & verbinden");
        connect.setOnClickListener(v -> ensurePermissionsAndScan());
        root.addView(connect);

        section(root,"Live");
        live = text("Speed --  |  U --  |  Iq --  |  Batt --",16,true);
        root.addView(live);
        detectStatus = text("Setup: idle",14,false);
        root.addView(detectStatus);

        section(root,"Gemeinsame Limits");
        battA = field(root,"Battery current max [A]","20");
        wheelMm = field(root,"Wheel diameter [mm]","250");
        poles = field(root,"Motor poles","14");
        enterKmh = field(root,"DELTA ab [km/h]","32");
        exitKmh = field(root,"STAR zurück bis [km/h]","26");
        switchIq = field(root,"Max |Iq| beim Umschalten [A]","2");
        settleMs = field(root,"Relay settle [ms]","100");
        autoDelta = new CheckBox(this);
        autoDelta.setText("Automatische STAR/DELTA-Umschaltung");
        root.addView(autoDelta);

        section(root,"STAR Profil");
        starR = field(root,"R [mΩ]","100");
        starL = field(root,"L [µH]","100");
        starFlux = field(root,"Flux [mWb]","12");
        starPhase = field(root,"Phase current max [A]","30");

        section(root,"DELTA Profil");
        deltaR = field(root,"R [mΩ]","100");
        deltaL = field(root,"L [µH]","100");
        deltaFlux = field(root,"Flux [mWb]","12");
        deltaPhase = field(root,"Phase current max [A]","30");

        LinearLayout row = new LinearLayout(this);
        row.setOrientation(LinearLayout.HORIZONTAL);
        Button read = button("READ", v -> readAll());
        Button apply = button("APPLY RAM", v -> applyAll());
        Button save = button("SAVE FLASH", v -> saveAll());
        row.addView(read,new LinearLayout.LayoutParams(0,wrap(),1));
        row.addView(apply,new LinearLayout.LayoutParams(0,wrap(),1));
        row.addView(save,new LinearLayout.LayoutParams(0,wrap(),1));
        root.addView(row);

        section(root,"Motor Setup");
        root.addView(text("Rad frei aufbocken. Die Erkennung hält den Rotor, pulst die Wicklung und dreht den Motor anschließend im Open-Loop. Nach STAR wird für DELTA PWM abgeschaltet und das Relais sicher umgelegt.",13,false));
        detectLoss = field(root,"Detection max copper loss [W]","100");

        LinearLayout detectRow = new LinearLayout(this);
        detectRow.setOrientation(LinearLayout.HORIZONTAL);
        detectRow.addView(button("DETECT STAR",v -> confirmDetect(false)),new LinearLayout.LayoutParams(0,wrap(),1));
        detectRow.addView(button("DETECT DELTA",v -> confirmDetect(true)),new LinearLayout.LayoutParams(0,wrap(),1));
        root.addView(detectRow);

        Button reread = button("Profile nach Setup neu laden",v -> readProfiles());
        root.addView(reread);

        section(root,"Hinweis");
        root.addView(text("Änderungen werden zuerst nur im RAM angewendet. Erst SAVE FLASH schreibt dauerhaft. Die Firmware akzeptiert kritische Änderungen und Motor-Setup nur im Stillstand.",13,false));

        return scroll;
    }

    private void ensurePermissionsAndScan() {
        if (Build.VERSION.SDK_INT >= 31) {
            if (checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN) != PackageManager.PERMISSION_GRANTED ||
                    checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{Manifest.permission.BLUETOOTH_SCAN,Manifest.permission.BLUETOOTH_CONNECT},REQ_PERMS);
                return;
            }
        } else if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.ACCESS_FINE_LOCATION},REQ_PERMS);
            return;
        }
        ble.scanAndConnect();
    }

    @Override public void onRequestPermissionsResult(int requestCode,String[] permissions,int[] results) {
        super.onRequestPermissionsResult(requestCode,permissions,results);
        if (requestCode == REQ_PERMS) ensurePermissionsAndScan();
    }

    private void readAll() {
        if (!ble.isReady()) return;
        ble.sendConfig(SescProtocol.GET_COMMON,new byte[0]);
        readProfiles();
    }

    private void readProfiles() {
        if (!ble.isReady()) return;
        ble.sendConfig(SescProtocol.GET_PROFILE,SescProtocol.profileRequest(false));
        handler.postDelayed(() -> ble.sendConfig(SescProtocol.GET_PROFILE,SescProtocol.profileRequest(true)),150);
    }

    private void applyAll() {
        if (!ble.isReady()) return;
        try {
            SescProtocol.CommonConfig c = readCommonFromUi();
            ble.sendConfig(SescProtocol.SET_COMMON,SescProtocol.commonPayload(c));
            handler.postDelayed(() -> ble.sendConfig(SescProtocol.SET_PROFILE,
                    SescProtocol.profilePayload(readProfileFromUi(false))),150);
            handler.postDelayed(() -> ble.sendConfig(SescProtocol.SET_PROFILE,
                    SescProtocol.profilePayload(readProfileFromUi(true))),300);
            status.setText("RAM-Konfiguration gesendet");
        } catch (Exception e) {
            toast("Ungültiger Wert: " + e.getMessage());
        }
    }

    private void saveAll() {
        applyAll();
        handler.postDelayed(() -> {
            if (ble.isReady()) ble.sendConfig(SescProtocol.SAVE,new byte[0]);
        },600);
    }

    private void confirmDetect(boolean delta) {
        if (!ble.isReady()) return;
        if (delta && !starProfileValid) {
            toast("Zuerst STAR erfolgreich erkennen");
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle(delta ? "DELTA erkennen" : "STAR erkennen")
                .setMessage("Rad muss frei in der Luft sein. Gas nicht berühren. Der Motor wird verriegelt und anschließend gedreht. Fortfahren?")
                .setNegativeButton("Abbrechen",null)
                .setPositiveButton("Start", (d,w) -> startDetect(delta))
                .show();
    }

    private void startDetect(boolean delta) {
        try {
            int loss = Integer.parseInt(detectLoss.getText().toString().trim());
            ble.sendConfig(SescProtocol.DETECT,SescProtocol.detectPayload(delta,loss));
            detectStatus.setText((delta ? "DELTA" : "STAR") + " Setup startet…");
        } catch (Exception e) {
            toast("Detection power loss prüfen");
        }
    }

    private SescProtocol.CommonConfig readCommonFromUi() {
        SescProtocol.CommonConfig c = new SescProtocol.CommonConfig();
        c.batteryCurrentA = f(battA);
        c.wheelDiameterM = f(wheelMm) / 1000f;
        c.motorPoles = Math.round(f(poles));
        c.deltaEnterKmh = f(enterKmh);
        c.deltaExitKmh = f(exitKmh);
        c.switchIqA = f(switchIq);
        c.relaySettleMs = Math.round(f(settleMs));
        c.autoDelta = autoDelta.isChecked();
        return c;
    }

    private SescProtocol.Profile readProfileFromUi(boolean delta) {
        SescProtocol.Profile p = new SescProtocol.Profile();
        p.delta = delta;
        p.resistanceOhm = f(delta ? deltaR : starR) / 1000f;
        p.inductanceH = f(delta ? deltaL : starL) / 1_000_000f;
        p.fluxWb = f(delta ? deltaFlux : starFlux) / 1000f;
        p.phaseCurrentA = f(delta ? deltaPhase : starPhase);
        return p;
    }

    @Override public void onStatus(String text) {
        runOnUiThread(() -> status.setText(text));
    }

    @Override public void onReady(boolean encrypted) {
        runOnUiThread(() -> {
            status.setText(encrypted ? "Verbunden · Ninebot Crypto" : "Verbunden · Plain/Legacy");
            connect.setText("Neu verbinden");
            ble.sendConfig(SescProtocol.HELLO,new byte[0]);
            handler.postDelayed(this::readAll,150);
            handler.removeCallbacks(poll);
            handler.post(poll);
        });
    }

    @Override public void onFrame(SescProtocol.Frame frame) {
        if (frame.cmd != SescProtocol.CMD_CONFIG) return;
        runOnUiThread(() -> handleConfigFrame(frame));
    }

    private void handleConfigFrame(SescProtocol.Frame f) {
        switch (f.arg) {
            case SescProtocol.HELLO:
                if (f.payload.length >= 5) {
                    int ver=SescProtocol.u8(f.payload[0]);
                    int flags=SescProtocol.u8(f.payload[1]);
                    status.setText("SmartESC Config v"+ver+" · flags 0x"+Integer.toHexString(flags));
                }
                break;
            case SescProtocol.TELEMETRY: {
                SescProtocol.Telemetry t=SescProtocol.parseTelemetry(f.payload);
                if(t!=null) {
                    live.setText(String.format(Locale.US,
                            "%.1f km/h  |  %.1f V  |  Iq %.1f A  |  Batt %.2f A  |  %d%%  |  %s%s",
                            t.speedKmh,t.busVoltageV,t.iqA,t.inputCurrentA,t.soc,
                            t.delta?"DELTA":"STAR",t.bmsOnline?" · BMS":" · BMS offline"));
                    detectStatus.setText("Setup state "+t.detectState+" · "+t.detectProgress+"%"+
                            (t.detectError!=0?" · error "+t.detectError:""));
                    if (t.detectState==5 && t.detectProgress==100) readProfiles();
                }
                break;
            }
            case SescProtocol.GET_COMMON: {
                SescProtocol.CommonConfig c=SescProtocol.parseCommon(f.payload);
                if(c!=null) showCommon(c);
                break;
            }
            case SescProtocol.GET_PROFILE: {
                SescProtocol.Profile p=SescProtocol.parseProfile(f.payload);
                if(p!=null) showProfile(p);
                break;
            }
            case SescProtocol.SET_COMMON:
            case SescProtocol.SET_PROFILE:
                if(f.payload.length>0 && f.payload[0]==0) toast("ESC hat Änderung abgelehnt");
                break;
            case SescProtocol.SAVE:
                toast(f.payload.length>0 && f.payload[0]!=0 ? "Konfiguration gespeichert" : "Speichern abgelehnt");
                break;
            case SescProtocol.DETECT:
                if(f.payload.length==0 || f.payload[0]==0) toast("Motor-Setup konnte nicht gestartet werden");
                break;
            case SescProtocol.DETECT_STATUS:
                if(f.payload.length>=4) {
                    detectStatus.setText("Setup state "+SescProtocol.u8(f.payload[0])+
                            " · "+SescProtocol.u8(f.payload[3])+"% · err "+(byte)f.payload[1]);
                }
                break;
        }
    }

    private void showCommon(SescProtocol.CommonConfig c) {
        battA.setText(num(c.batteryCurrentA,1));
        wheelMm.setText(num(c.wheelDiameterM*1000f,0));
        poles.setText(Integer.toString(c.motorPoles));
        enterKmh.setText(num(c.deltaEnterKmh,1));
        exitKmh.setText(num(c.deltaExitKmh,1));
        switchIq.setText(num(c.switchIqA,1));
        settleMs.setText(Integer.toString(c.relaySettleMs));
        autoDelta.setChecked(c.autoDelta);
    }

    private void showProfile(SescProtocol.Profile p) {
        if (!p.delta) starProfileValid = p.valid;
        EditText r=p.delta?deltaR:starR, l=p.delta?deltaL:starL,
                fl=p.delta?deltaFlux:starFlux, ph=p.delta?deltaPhase:starPhase;
        r.setText(num(p.resistanceOhm*1000f,3));
        l.setText(num(p.inductanceH*1_000_000f,2));
        fl.setText(num(p.fluxWb*1000f,3));
        ph.setText(num(p.phaseCurrentA,1));
        if(!p.valid) r.setError("noch nicht erkannt/gespeichert");
    }

    @Override public void onDisconnected() {
        runOnUiThread(() -> {
            handler.removeCallbacks(poll);
            connect.setText("G30 suchen & verbinden");
        });
    }

    @Override protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        if(ble!=null) ble.disconnect();
        super.onDestroy();
    }

    private EditText field(LinearLayout root,String label,String def) {
        TextView l=text(label,12,false);
        l.setPadding(0,dp(6),0,0);
        root.addView(l);
        EditText e=new EditText(this);
        e.setSingleLine(true);
        e.setInputType(android.text.InputType.TYPE_CLASS_NUMBER |
                android.text.InputType.TYPE_NUMBER_FLAG_DECIMAL |
                android.text.InputType.TYPE_NUMBER_FLAG_SIGNED);
        e.setText(def);
        root.addView(e,new LinearLayout.LayoutParams(match(),wrap()));
        return e;
    }

    private void section(LinearLayout root,String s) {
        TextView t=text(s,18,true);
        t.setPadding(0,dp(18),0,dp(4));
        root.addView(t);
    }

    private TextView text(String s,int sp,boolean bold) {
        TextView t=new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        if(bold)t.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        return t;
    }

    private Button button(String s,View.OnClickListener l) {
        Button b=new Button(this); b.setText(s); b.setOnClickListener(l); return b;
    }

    private float f(EditText e) { return Float.parseFloat(e.getText().toString().trim().replace(',','.')); }
    private String num(float v,int dec) { return String.format(Locale.US,"%."+dec+"f",v); }
    private void toast(String s) { Toast.makeText(this,s,Toast.LENGTH_SHORT).show(); }
    private int dp(int x){return Math.round(x*getResources().getDisplayMetrics().density);}
    private int wrap(){return ViewGroup.LayoutParams.WRAP_CONTENT;}
    private int match(){return ViewGroup.LayoutParams.MATCH_PARENT;}
}
