#!/usr/bin/env python3
import argparse, struct, sys, time, zipfile
try:
    import serial
except ImportError:
    print("Fehlt: pyserial. Installieren mit: py -m pip install pyserial", file=sys.stderr)
    raise SystemExit(2)

HOST=0x3D
ESC=0x20
ACK=0x0B
ERR={0:"OK",1:"SIZE",2:"ERASE",3:"WRITEFLASH",4:"UNLOCK",5:"INDEX",6:"BUSY",7:"FORM",8:"CRC",9:"OTHER"}

def checksum16(body: bytes) -> int:
    return (~sum(body)) & 0xFFFF

def frame(cmd:int,index:int=0,data:bytes=b"",src:int=HOST,dst:int=ESC)->bytes:
    if len(data)>128:
        raise ValueError("max 128 data bytes")
    body=bytes((len(data),src,dst,cmd,index))+data
    return b"\x5A\xA5"+body+struct.pack("<H",checksum16(body))

class Parser:
    def __init__(self):
        self.buf=bytearray()
    def feed(self,b:bytes):
        self.buf.extend(b)
        out=[]
        while True:
            i=self.buf.find(b"\x5A\xA5")
            if i<0:
                if len(self.buf)>1:
                    del self.buf[:-1]
                return out
            if i:
                del self.buf[:i]
            if len(self.buf)<9:
                return out
            n=self.buf[2]
            total=2+5+n+2
            if n>128:
                del self.buf[0]
                continue
            if len(self.buf)<total:
                return out
            raw=bytes(self.buf[:total])
            del self.buf[:total]
            body=raw[2:-2]
            got=struct.unpack_from("<H",raw,total-2)[0]
            if checksum16(body)!=got:
                continue
            out.append({"len":n,"src":raw[3],"dst":raw[4],"cmd":raw[5],
                        "index":raw[6],"data":raw[7:7+n]})
        return out

def read_one(ser, parser, timeout=1.0):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        b=ser.read(max(1,ser.in_waiting or 1))
        for f in parser.feed(b):
            return f
    return None

def transact(ser, parser, cmd, index=0, data=b"", expect=None, retries=3, timeout=1.5):
    pkt=frame(cmd,index,data)
    for _ in range(retries):
        ser.write(pkt)
        ser.flush()
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            f=read_one(ser,parser,min(0.25,end-time.monotonic()))
            if not f:
                continue
            if f["src"]!=ESC or f["dst"]!=HOST:
                continue
            if expect is None or f["cmd"]==expect:
                return f
    raise TimeoutError(f"Keine Antwort auf CMD 0x{cmd:02X}")

def ack(ser, parser, cmd, index=0, data=b"", retries=4):
    f=transact(ser,parser,cmd,index,data,ACK,retries=retries)
    code=f["index"]
    if code!=0:
        raise RuntimeError(f"CMD 0x{cmd:02X}: ACK {code} ({ERR.get(code,'?')})")
    return f

def load_enc(path):
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path,"r") as z:
            cand=next((n for n in z.namelist() if n.lower().endswith("firm.bin.enc")),None)
            if not cand:
                raise SystemExit("ZIP enthält kein FIRM.bin.enc")
            data=z.read(cand)
    else:
        data=open(path,"rb").read()
    if len(data)<16 or len(data)>0xD800 or len(data)%8:
        raise SystemExit(f"Ungültige verschlüsselte IAP-Länge: {len(data)}")
    return data

def probe(ser, parser):
    f=transact(ser,parser,0x01,16,bytes((14,)),0x04,retries=3,timeout=0.8)
    ident=f["data"].split(b"\0",1)[0].decode("ascii","replace")
    if not ident.startswith("XBOTRCV1"):
        raise RuntimeError(f"Kein Recovery-Modus: Identität {ident!r}")
    return ident

def main():
    ap=argparse.ArgumentParser(description="SmartESC G30 3s Recovery IAP flasher")
    ap.add_argument("port", help="z.B. COM9")
    ap.add_argument("firmware", help="SHU-ZIP mit FIRM.bin.enc oder direkte verschlüsselte Driver.bin")
    args=ap.parse_args()

    enc=load_enc(args.firmware)
    print(f"Image: {len(enc)} Bytes encrypted")

    with serial.Serial(args.port,115200,timeout=0.05,write_timeout=2) as ser:
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        p=Parser()

        ident=probe(ser,p)
        print(f"Recovery erkannt: {ident}")

        ack(ser,p,0x07,0,struct.pack("<I",len(enc)))
        print("BEGIN OK")

        blocks=(len(enc)+127)//128
        for bi,off in enumerate(range(0,len(enc),128)):
            chunk=enc[off:off+128]
            ack(ser,p,0x08,bi&0xFF,chunk,retries=5)
            if bi==0 or (bi+1)%16==0 or bi+1==blocks:
                print(f"WRITE {bi+1}/{blocks}")

        ack(ser,p,0x09,0,b"\0\0\0\0")
        print("FINALIZE OK, Pending-Block gesetzt")

        ack(ser,p,0x0A,0,b"")
        print("RESET gesendet. Stock-IAP kopiert Staging -> 0x08001000.")

if __name__=="__main__":
    main()
