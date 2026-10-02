package de.smartesc.config;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;

public final class SescProtocol {
    public static final int CMD_CONFIG = 0x7D;

    public static final int HELLO = 0x00;
    public static final int TELEMETRY = 0x01;
    public static final int GET_COMMON = 0x02;
    public static final int SET_COMMON = 0x03;
    public static final int GET_PROFILE = 0x04;
    public static final int SET_PROFILE = 0x05;
    public static final int SAVE = 0x06;
    public static final int DETECT = 0x07;
    public static final int DETECT_STATUS = 0x08;

    private SescProtocol() {}

    public static byte[] buildFrame(int src, int dst, int cmd, int arg, byte[] payload) {
        if (payload == null) payload = new byte[0];
        byte[] out = new byte[payload.length + 9];
        out[0] = 0x5A;
        out[1] = (byte) 0xA5;
        out[2] = (byte) payload.length;
        out[3] = (byte) src;
        out[4] = (byte) dst;
        out[5] = (byte) cmd;
        out[6] = (byte) arg;
        System.arraycopy(payload, 0, out, 7, payload.length);
        int sum = 0;
        for (int i = 2; i < out.length - 2; i++) sum = (sum + u8(out[i])) & 0xFFFF;
        int ck = (~sum) & 0xFFFF;
        out[out.length - 2] = (byte) (ck & 0xFF);
        out[out.length - 1] = (byte) ((ck >>> 8) & 0xFF);
        return out;
    }

    public static byte[] buildConfig(int arg, byte[] payload) {
        return buildFrame(0x3E, 0x20, CMD_CONFIG, arg, payload);
    }

    public static Frame parse(byte[] raw) {
        if (raw == null || raw.length < 9 || u8(raw[0]) != 0x5A || u8(raw[1]) != 0xA5) return null;
        int len = u8(raw[2]);
        if (raw.length != len + 9) return null;
        int sum = 0;
        for (int i = 2; i < raw.length - 2; i++) sum = (sum + u8(raw[i])) & 0xFFFF;
        int ck = (~sum) & 0xFFFF;
        int got = u16(raw, raw.length - 2);
        if (ck != got) return null;
        return new Frame(u8(raw[3]), u8(raw[4]), u8(raw[5]), u8(raw[6]),
                Arrays.copyOfRange(raw, 7, 7 + len));
    }

    public static byte[] commonPayload(CommonConfig c) {
        byte[] p = new byte[14];
        putU16(p, 0, Math.round(c.batteryCurrentA * 10f));
        putU16(p, 2, Math.round(c.wheelDiameterM * 1000f));
        p[4] = (byte)c.motorPoles;
        p[5] = (byte)(c.autoDelta ? 0x04 : 0x00);
        putU16(p, 6, Math.round(c.deltaEnterKmh * 10f));
        putU16(p, 8, Math.round(c.deltaExitKmh * 10f));
        putU16(p, 10, Math.round(c.switchIqA * 10f));
        putU16(p, 12, c.relaySettleMs);
        return p;
    }

    public static CommonConfig parseCommon(byte[] p) {
        if (p.length < 14) return null;
        CommonConfig c = new CommonConfig();
        c.batteryCurrentA = u16(p,0) / 10f;
        c.wheelDiameterM = u16(p,2) / 1000f;
        c.motorPoles = u8(p[4]);
        c.flags = u8(p[5]);
        c.autoDelta = (c.flags & 0x04) != 0;
        c.deltaEnterKmh = u16(p,6) / 10f;
        c.deltaExitKmh = u16(p,8) / 10f;
        c.switchIqA = u16(p,10) / 10f;
        c.relaySettleMs = u16(p,12);
        return c;
    }

    public static byte[] profileRequest(boolean delta) {
        return new byte[] { (byte)(delta ? 1 : 0) };
    }

    public static byte[] profilePayload(Profile p) {
        byte[] out = new byte[16];
        out[0] = (byte)(p.delta ? 1 : 0);
        out[1] = 0;
        putU32(out, 2, Math.round(p.resistanceOhm * 1_000_000f));
        putU32(out, 6, Math.round(p.inductanceH * 1_000_000_000f));
        putU32(out,10, Math.round(p.fluxWb * 1_000_000f));
        putU16(out,14, Math.round(p.phaseCurrentA * 10f));
        return out;
    }

    public static Profile parseProfile(byte[] p) {
        if (p.length < 16) return null;
        Profile r = new Profile();
        r.delta = p[0] != 0;
        r.valid = p[1] != 0;
        r.resistanceOhm = u32(p,2) / 1_000_000f;
        r.inductanceH = u32(p,6) / 1_000_000_000f;
        r.fluxWb = u32(p,10) / 1_000_000f;
        r.phaseCurrentA = u16(p,14) / 10f;
        if (p.length >= 24) r.hall = Arrays.copyOfRange(p,16,24);
        return r;
    }

    public static byte[] detectPayload(boolean delta, int maxPowerLossW) {
        byte[] p = new byte[3];
        p[0] = (byte)(delta ? 1 : 0);
        putU16(p,1,maxPowerLossW);
        return p;
    }

    public static Telemetry parseTelemetry(byte[] p) {
        if (p.length < 16) return null;
        Telemetry t = new Telemetry();
        t.speedKmh = i16(p,0) / 10f;
        t.iqA = i16(p,2) / 10f;
        t.busVoltageV = u16(p,4) / 10f;
        t.inputCurrentA = i16(p,6) / 100f;
        t.soc = u8(p[8]);
        t.delta = p[9] != 0;
        t.fault = u16(p,10);
        t.bmsOnline = p[12] != 0;
        t.detectState = u8(p[13]);
        t.detectProgress = u8(p[14]);
        t.detectError = (byte)p[15];
        return t;
    }

    public static int u8(byte b) { return b & 0xFF; }
    public static int u16(byte[] b, int o) { return u8(b[o]) | (u8(b[o+1]) << 8); }
    public static short i16(byte[] b, int o) { return (short)u16(b,o); }
    public static long u32(byte[] b, int o) {
        return ((long)u8(b[o])) | ((long)u8(b[o+1]) << 8) |
                ((long)u8(b[o+2]) << 16) | ((long)u8(b[o+3]) << 24);
    }
    public static void putU16(byte[] b, int o, int v) {
        b[o] = (byte)(v & 0xFF); b[o+1] = (byte)((v >>> 8) & 0xFF);
    }
    public static void putU32(byte[] b, int o, long v) {
        b[o] = (byte)(v & 0xFF); b[o+1]=(byte)((v>>>8)&0xFF);
        b[o+2]=(byte)((v>>>16)&0xFF); b[o+3]=(byte)((v>>>24)&0xFF);
    }

    public static final class Frame {
        public final int src, dst, cmd, arg;
        public final byte[] payload;
        public Frame(int src, int dst, int cmd, int arg, byte[] payload) {
            this.src=src; this.dst=dst; this.cmd=cmd; this.arg=arg; this.payload=payload;
        }
    }

    public static final class CommonConfig {
        public float batteryCurrentA = 20f;
        public float wheelDiameterM = 0.25f;
        public int motorPoles = 14;
        public int flags;
        public boolean autoDelta;
        public float deltaEnterKmh = 32f;
        public float deltaExitKmh = 26f;
        public float switchIqA = 2f;
        public int relaySettleMs = 100;
    }

    public static final class Profile {
        public boolean delta;
        public boolean valid;
        public float resistanceOhm;
        public float inductanceH;
        public float fluxWb;
        public float phaseCurrentA = 30f;
        public byte[] hall = new byte[8];
    }

    public static final class Telemetry {
        public float speedKmh, iqA, busVoltageV, inputCurrentA;
        public int soc, fault, detectState, detectProgress, detectError;
        public boolean delta, bmsOnline;
    }
}
