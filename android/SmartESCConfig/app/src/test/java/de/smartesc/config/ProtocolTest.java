package de.smartesc.config;

import static org.junit.Assert.*;
import org.junit.Test;

public class ProtocolTest {
    private static byte[] hex(String s) {
        int n=s.length()/2;
        byte[] out=new byte[n];
        for(int i=0;i<n;i++) out[i]=(byte)Integer.parseInt(s.substring(i*2,i*2+2),16);
        return out;
    }

    @Test public void legacyCryptoMatchesPublishedInitialVector() {
        LegacyNinebotCrypto c=new LegacyNinebotCrypto("MIScooter5787");
        byte[] plain=hex("5aa5003e215b00");
        byte[] expected=hex("5aa500a1616a44000045ff0000");
        assertArrayEquals(expected,c.encrypt(plain));

        LegacyNinebotCrypto d=new LegacyNinebotCrypto("MIScooter5787");
        assertArrayEquals(plain,d.decrypt(expected));
    }

    @Test public void bleInnerHasNoUartChecksum() {
        byte[] p=SescProtocol.buildBleInner(0x3E,0x21,0x5B,0,null);
        assertArrayEquals(hex("5aa5003e215b00"),p);
        SescProtocol.Frame f=SescProtocol.parseBleInner(p);
        assertNotNull(f);
        assertEquals(0x3E,f.src);
        assertEquals(0x21,f.dst);
        assertEquals(0x5B,f.cmd);
        assertEquals(0,f.arg);
        assertEquals(0,f.payload.length);
    }

    @Test public void uartConfigFrameRoundTripsWithChecksum() {
        byte[] payload=hex("01020304");
        byte[] p=SescProtocol.buildFrame(0x3E,0x20,SescProtocol.CMD_CONFIG,
                SescProtocol.SET_COMMON,payload);
        assertEquals(payload.length+9,p.length);
        SescProtocol.Frame f=SescProtocol.parse(p);
        assertNotNull(f);
        assertEquals(0x3E,f.src);
        assertEquals(0x20,f.dst);
        assertEquals(SescProtocol.CMD_CONFIG,f.cmd);
        assertEquals(SescProtocol.SET_COMMON,f.arg);
        assertArrayEquals(payload,f.payload);
    }
}
