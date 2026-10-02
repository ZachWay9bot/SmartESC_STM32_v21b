package de.smartesc.config;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Arrays;
import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;

/**
 * Legacy Ninebot BLE crypto implementation for the G30 BLE110/113/114 family.
 *
 * This is an independent Java implementation based on the publicly documented
 * first-generation Ninebot/Xiaomi crypto protocol and the published
 * scooterhacking/NinebotCrypto interoperability notes.
 */
public final class LegacyNinebotCrypto {
    private static final byte[] BASIC = new byte[] {
            (byte)0x97,(byte)0xCF,(byte)0xB8,0x02,(byte)0x84,0x41,0x43,(byte)0xDE,
            0x56,0x00,0x2B,0x3B,0x34,0x78,0x0A,0x5D
    };

    private final byte[] scooterName16 = new byte[16];
    private final byte[] bleRandom = new byte[16];
    private final byte[] appRandom = new byte[16];
    private byte[] key = new byte[16];
    private long counter;

    public LegacyNinebotCrypto(String scooterName) {
        byte[] n = scooterName == null ? new byte[0] : scooterName.getBytes(StandardCharsets.US_ASCII);
        System.arraycopy(n, 0, scooterName16, 0, Math.min(16, n.length));
        key = deriveKey(scooterName16, BASIC);
    }

    public synchronized void reset() {
        Arrays.fill(bleRandom, (byte)0);
        Arrays.fill(appRandom, (byte)0);
        key = deriveKey(scooterName16, BASIC);
        counter = 0;
    }

    public synchronized void setAppRandom(byte[] random) {
        Arrays.fill(appRandom, (byte)0);
        if (random != null) System.arraycopy(random,0,appRandom,0,Math.min(16,random.length));
    }

    public synchronized byte[] encrypt(byte[] plain) {
        if (plain == null || plain.length < 3) throw new IllegalArgumentException("short Ninebot frame");
        byte[] body = Arrays.copyOfRange(plain,3,plain.length);
        byte[] crypt;
        byte[] out = new byte[plain.length + 6];
        System.arraycopy(plain,0,out,0,3);

        if (counter == 0) {
            crypt = xorFirst(body);
            System.arraycopy(crypt,0,out,3,crypt.length);
            int crc = firstChecksum(body);
            int t = 3 + crypt.length;
            out[t] = 0;
            out[t+1] = 0;
            out[t+2] = (byte)(crc & 0xFF);
            out[t+3] = (byte)((crc >>> 8) & 0xFF);
            out[t+4] = 0;
            out[t+5] = 0;
            counter = 1;
        } else {
            counter = (counter + 1) & 0xFFFFFFFFL;
            byte[] mac = nextMac(plain,counter);
            crypt = xorNext(body,counter);
            System.arraycopy(crypt,0,out,3,crypt.length);
            int t = 3 + crypt.length;
            System.arraycopy(mac,0,out,t,4);
            out[t+4] = (byte)((counter >>> 8) & 0xFF);
            out[t+5] = (byte)(counter & 0xFF);
        }
        return out;
    }

    public synchronized byte[] decrypt(byte[] encrypted) {
        if (encrypted == null || encrypted.length < 15) return null;

        long rx16 = ((long)(encrypted[encrypted.length-2] & 0xFF) << 8)
                | (long)(encrypted[encrypted.length-1] & 0xFF);
        long rxCounter = (counter & 0xFFFF0000L) | rx16;
        if ((rxCounter + 0x8000L) < counter) rxCounter += 0x10000L;

        int bodyLen = encrypted.length - 9;
        if (bodyLen < 0) return null;
        byte[] encBody = Arrays.copyOfRange(encrypted,3,3+bodyLen);
        byte[] body = rxCounter == 0 ? xorFirst(encBody) : xorNext(encBody,rxCounter);

        byte[] plain = new byte[encrypted.length - 6];
        System.arraycopy(encrypted,0,plain,0,3);
        System.arraycopy(body,0,plain,3,body.length);

        if (plain.length >= 23 &&
                (plain[0] & 0xFF) == 0x5A && (plain[1] & 0xFF) == 0xA5 &&
                (plain[3] & 0xFF) == 0x21 && (plain[4] & 0xFF) == 0x3E &&
                (plain[5] & 0xFF) == 0x5B) {
            System.arraycopy(plain,7,bleRandom,0,16);
            key = deriveKey(scooterName16,bleRandom);
        }

        if (plain.length >= 7 &&
                (plain[3] & 0xFF) == 0x21 && (plain[4] & 0xFF) == 0x3E &&
                (plain[5] & 0xFF) == 0x5C && (plain[6] & 0xFF) == 0x01) {
            key = deriveKey(appRandom,bleRandom);
        }

        if (rxCounter != 0) {
            if (counter > rxCounter) counter = rxCounter;
            else counter = (counter + 1) & 0xFFFFFFFFL;
        }
        return plain;
    }

    private static int firstChecksum(byte[] data) {
        long sum = 0;
        for (byte b : data) sum += b; // signed-byte behavior of legacy implementation
        return (int)(~sum) & 0xFFFF;
    }

    private byte[] nextMac(byte[] plain,long msgCounter) {
        byte[] seed = new byte[16];
        seed[0] = 0x59;
        seed[1] = (byte)((msgCounter >>> 24) & 0xFF);
        seed[2] = (byte)((msgCounter >>> 16) & 0xFF);
        seed[3] = (byte)((msgCounter >>> 8) & 0xFF);
        seed[4] = (byte)(msgCounter & 0xFF);
        System.arraycopy(bleRandom,0,seed,5,8);
        seed[15] = (byte)(plain.length - 3);

        byte[] chain = aes(seed,key);
        byte[] head = new byte[16];
        System.arraycopy(plain,0,head,0,Math.min(3,plain.length));
        chain = aes(xor16(head,chain),key);

        int pos = 3;
        while (pos < plain.length) {
            byte[] block = new byte[16];
            int n = Math.min(16,plain.length-pos);
            System.arraycopy(plain,pos,block,0,n);
            chain = aes(xor16(block,chain),key);
            pos += n;
        }

        seed[0] = 0x01;
        seed[15] = 0;
        byte[] finish = aes(seed,key);
        byte[] mac = new byte[4];
        for (int i=0;i<4;i++) mac[i] = (byte)(finish[i] ^ chain[i]);
        return mac;
    }

    private byte[] xorNext(byte[] data,long msgCounter) {
        byte[] out = new byte[data.length];
        byte[] ctr = new byte[16];
        ctr[0] = 0x01;
        ctr[1] = (byte)((msgCounter >>> 24) & 0xFF);
        ctr[2] = (byte)((msgCounter >>> 16) & 0xFF);
        ctr[3] = (byte)((msgCounter >>> 8) & 0xFF);
        ctr[4] = (byte)(msgCounter & 0xFF);
        System.arraycopy(bleRandom,0,ctr,5,8);

        int pos=0;
        int blockNo=0;
        while(pos<data.length) {
            ctr[15] = (byte)(++blockNo);
            byte[] ks = aes(ctr,key);
            int n = Math.min(16,data.length-pos);
            for(int i=0;i<n;i++) out[pos+i]=(byte)(data[pos+i]^ks[i]);
            pos+=n;
        }
        return out;
    }

    private byte[] xorFirst(byte[] data) {
        byte[] out = new byte[data.length];
        byte[] ks = aes(BASIC,key);
        int pos=0;
        while(pos<data.length) {
            int n=Math.min(16,data.length-pos);
            for(int i=0;i<n;i++) out[pos+i]=(byte)(data[pos+i]^ks[i]);
            pos+=n;
        }
        return out;
    }

    private static byte[] deriveKey(byte[] a,byte[] b) {
        try {
            byte[] in=new byte[32];
            System.arraycopy(a,0,in,0,Math.min(16,a.length));
            System.arraycopy(b,0,in,16,Math.min(16,b.length));
            byte[] sha= MessageDigest.getInstance("SHA-1").digest(in);
            return Arrays.copyOf(sha,16);
        } catch(Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private static byte[] aes(byte[] block,byte[] key) {
        try {
            Cipher c=Cipher.getInstance("AES/ECB/NoPadding");
            c.init(Cipher.ENCRYPT_MODE,new SecretKeySpec(key,"AES"));
            return c.doFinal(block);
        } catch(Exception e) {
            throw new IllegalStateException(e);
        }
    }

    private static byte[] xor16(byte[] a,byte[] b) {
        byte[] r=new byte[16];
        for(int i=0;i<16;i++) r[i]=(byte)(a[i]^b[i]);
        return r;
    }
}
