#!/usr/bin/env python3
"""Decode read-only STM32F103 G30D SWD register captures.

Input is either a directory or ZIP created by docs/G30_SWD_READONLY_BENCH.md.
This tool only parses local files; it does not talk to ST-Link or write hardware.
"""
from __future__ import annotations
import argparse
import json
import struct
import zipfile
from pathlib import Path
from typing import Callable

EXPECTED = {
    "VECTORS.bin": 0x08,
    "TIM1.bin": 0x48,
    "RCC.bin": 0x24,
    "ADC1.bin": 0x3C,
    "ADC2.bin": 0x3C,
    "GPIOA.bin": 0x10,
    "GPIOB.bin": 0x10,
    "GPIOC.bin": 0x10,
    "AFIO_MAPR.bin": 0x04,
    "USART2_CFG.bin": 0x10,
}


def u16(b: bytes, o: int) -> int:
    return struct.unpack_from("<H", b, o)[0]


def u32(b: bytes, o: int) -> int:
    return struct.unpack_from("<I", b, o)[0]


def bit(v: int, n: int) -> int:
    return (v >> n) & 1


def field(v: int, lo: int, width: int) -> int:
    return (v >> lo) & ((1 << width) - 1)


def load_source(path: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    if path.is_dir():
        for name in EXPECTED:
            p = path / name
            if p.exists():
                out[name] = p.read_bytes()
    elif path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            by_base = {Path(n).name: n for n in z.namelist() if not n.endswith("/")}
            for name in EXPECTED:
                if name in by_base:
                    out[name] = z.read(by_base[name])
    else:
        raise ValueError(f"expected capture directory or .zip: {path}")

    if not out:
        raise ValueError(f"no known capture files found in {path}")

    for name, data in out.items():
        need = EXPECTED[name]
        if len(data) < need:
            raise ValueError(f"{name}: {len(data)} bytes, expected at least {need}")
    return out


def decode_vectors(b: bytes) -> dict:
    sp, reset = struct.unpack_from("<II", b, 0)
    return {
        "sp": sp,
        "reset": reset,
        "reset_thumb": bool(reset & 1),
        "reset_addr": reset & ~1,
    }


def decode_tim1(b: bytes) -> dict:
    cr1 = u16(b, 0x00)
    ccer = u16(b, 0x20)
    psc = u16(b, 0x28)
    arr = u16(b, 0x2C)
    rcr = u16(b, 0x30)
    ccr4 = u16(b, 0x40)
    bdtr = u16(b, 0x44)
    cms = field(cr1, 5, 2)
    ckd = field(cr1, 8, 2)
    return {
        "CR1": cr1,
        "CEN": bit(cr1, 0),
        "DIR": bit(cr1, 4),
        "CMS": cms,
        "center_aligned": cms != 0,
        "CKD": ckd,
        "CKD_div": {0: 1, 1: 2, 2: 4}.get(ckd),
        "CCER": ccer,
        "PSC": psc,
        "ARR": arr,
        "RCR": rcr,
        "CCR4": ccr4,
        "BDTR": bdtr,
        "DTG": field(bdtr, 0, 8),
        "LOCK": field(bdtr, 8, 2),
        "OSSI": bit(bdtr, 10),
        "OSSR": bit(bdtr, 11),
        "BKE": bit(bdtr, 12),
        "BKP": bit(bdtr, 13),
        "AOE": bit(bdtr, 14),
        "MOE": bit(bdtr, 15),
    }


def decode_rcc(b: bytes) -> dict:
    cfgr = u32(b, 0x04)
    return {
        "CFGR": cfgr,
        "SW": field(cfgr, 0, 2),
        "SWS": field(cfgr, 2, 2),
        "HPRE": field(cfgr, 4, 4),
        "PPRE1": field(cfgr, 8, 3),
        "PPRE2": field(cfgr, 11, 3),
        "ADCPRE": field(cfgr, 14, 2),
        "PLLSRC": bit(cfgr, 16),
        "PLLXTPRE": bit(cfgr, 17),
        "PLLMUL": field(cfgr, 18, 4),
        "USBPRE": bit(cfgr, 22),
        "MCO": field(cfgr, 24, 3),
    }


def decode_adc(b: bytes) -> dict:
    cr2 = u32(b, 0x08)
    jsqr = u32(b, 0x38)
    jl = field(jsqr, 20, 2)
    jsq = [
        field(jsqr, 0, 5),
        field(jsqr, 5, 5),
        field(jsqr, 10, 5),
        field(jsqr, 15, 5),
    ]
    # STM32F1 injected sequences are right-aligned in JSQR.
    # JL=0 therefore means one conversion in JSQ4.
    active = jsq[3 - jl:4]
    return {
        "CR2": cr2,
        "ADON": bit(cr2, 0),
        "CONT": bit(cr2, 1),
        "CAL": bit(cr2, 2),
        "RSTCAL": bit(cr2, 3),
        "DMA": bit(cr2, 8),
        "ALIGN": bit(cr2, 11),
        "JEXTSEL": field(cr2, 12, 3),
        "JEXTTRIG": bit(cr2, 15),
        "EXTSEL": field(cr2, 17, 3),
        "EXTTRIG": bit(cr2, 20),
        "JSWSTART": bit(cr2, 21),
        "SWSTART": bit(cr2, 22),
        "TSVREFE": bit(cr2, 23),
        "JSQR": jsqr,
        "JL": jl,
        "injected_count": jl + 1,
        "JSQ_fields": jsq,
        "active_injected_channels": active,
    }


def decode_gpio(b: bytes) -> dict:
    crl = u32(b, 0x00)
    crh = u32(b, 0x04)
    idr = u32(b, 0x08)
    odr = u32(b, 0x0C)
    pins = {}
    for pin in range(16):
        reg = crl if pin < 8 else crh
        shift = (pin % 8) * 4
        nib = field(reg, shift, 4)
        pins[str(pin)] = {
            "cfg": nib,
            "MODE": field(nib, 0, 2),
            "CNF": field(nib, 2, 2),
            "IDR": bit(idr, pin),
            "ODR": bit(odr, pin),
        }
    return {"CRL": crl, "CRH": crh, "IDR": idr, "ODR": odr, "pins": pins}


def decode_usart2_cfg(b: bytes) -> dict:
    # Capture begins at USART2 BRR (base + 0x08) to avoid reading DR.
    return {
        "BRR": u32(b, 0x00),
        "CR1": u32(b, 0x04),
        "CR2": u32(b, 0x08),
        "CR3": u32(b, 0x0C),
    }


DECODERS: dict[str, Callable[[bytes], dict]] = {
    "VECTORS.bin": decode_vectors,
    "TIM1.bin": decode_tim1,
    "RCC.bin": decode_rcc,
    "ADC1.bin": decode_adc,
    "ADC2.bin": decode_adc,
    "GPIOA.bin": decode_gpio,
    "GPIOB.bin": decode_gpio,
    "GPIOC.bin": decode_gpio,
    "AFIO_MAPR.bin": lambda b: {"MAPR": u32(b, 0)},
    "USART2_CFG.bin": decode_usart2_cfg,
}


def decode(src: dict[str, bytes]) -> dict:
    return {name: DECODERS[name](data) for name, data in src.items()}


def h(v) -> str:
    return f"0x{v:08X}" if isinstance(v, int) else str(v)


def summary(d: dict) -> str:
    lines = []
    if "VECTORS.bin" in d:
        v = d["VECTORS.bin"]
        lines.append(f"VECTORS SP={h(v['sp'])} RESET={h(v['reset'])}")

    if "TIM1.bin" in d:
        t = d["TIM1.bin"]
        lines.append(
            f"TIM1 CR1={h(t['CR1'])} CMS={t['CMS']} CKD={t['CKD']}(/ {t['CKD_div']}) "
            f"ARR={t['ARR']} RCR={t['RCR']} CCR4={t['CCR4']} "
            f"BDTR={h(t['BDTR'])} DTG=0x{t['DTG']:02X} "
            f"AOE={t['AOE']} BKE={t['BKE']} MOE={t['MOE']}"
        )

    if "RCC.bin" in d:
        r = d["RCC.bin"]
        lines.append(
            f"RCC CFGR={h(r['CFGR'])} SWS={r['SWS']} PPRE1={r['PPRE1']} "
            f"PPRE2={r['PPRE2']} ADCPRE={r['ADCPRE']} PLLMUL={r['PLLMUL']}"
        )

    for name in ("ADC1.bin", "ADC2.bin"):
        if name in d:
            a = d[name]
            lines.append(
                f"{name[:-4]} CR2={h(a['CR2'])} JSQR={h(a['JSQR'])} "
                f"count={a['injected_count']} active={a['active_injected_channels']} "
                f"JEXTSEL={a['JEXTSEL']} JEXTTRIG={a['JEXTTRIG']}"
            )

    for name, selected in (("GPIOA.bin", (8, 9, 10)), ("GPIOB.bin", (13, 14, 15))):
        if name in d:
            g = d[name]
            bits = []
            for pin in selected:
                q = g["pins"][str(pin)]
                bits.append(f"P{pin}:cfg={q['cfg']:X},ODR={q['ODR']},IDR={q['IDR']}")
            lines.append(name[:-4] + " " + " ".join(bits))

    return "\n".join(lines)


def diff(a: dict, b: dict) -> list[str]:
    keys = [
        ("TIM1.bin", "CR1"),
        ("TIM1.bin", "CCER"),
        ("TIM1.bin", "PSC"),
        ("TIM1.bin", "ARR"),
        ("TIM1.bin", "RCR"),
        ("TIM1.bin", "CCR4"),
        ("TIM1.bin", "BDTR"),
        ("RCC.bin", "CFGR"),
        ("ADC1.bin", "CR2"),
        ("ADC1.bin", "JSQR"),
        ("ADC2.bin", "CR2"),
        ("ADC2.bin", "JSQR"),
        ("GPIOA.bin", "CRH"),
        ("GPIOA.bin", "ODR"),
        ("GPIOB.bin", "CRH"),
        ("GPIOB.bin", "ODR"),
        ("AFIO_MAPR.bin", "MAPR"),
        ("USART2_CFG.bin", "BRR"),
        ("USART2_CFG.bin", "CR1"),
        ("USART2_CFG.bin", "CR2"),
        ("USART2_CFG.bin", "CR3"),
    ]
    out = []
    for filename, key in keys:
        if filename in a and filename in b and a[filename].get(key) != b[filename].get(key):
            out.append(
                f"{filename[:-4]}.{key}: "
                f"{h(a[filename].get(key))} -> {h(b[filename].get(key))}"
            )
    return out


def self_test() -> None:
    tim = bytearray(0x48)
    struct.pack_into("<H", tim, 0x00, 0x20)
    struct.pack_into("<H", tim, 0x2C, 4000)
    struct.pack_into("<H", tim, 0x30, 1)
    struct.pack_into("<H", tim, 0x44, 0x4D40)
    t = decode_tim1(bytes(tim))
    assert t["CMS"] == 1
    assert t["ARR"] == 4000
    assert t["DTG"] == 0x40
    assert t["AOE"] == 1
    assert t["MOE"] == 0

    adc = bytearray(0x3C)
    struct.pack_into("<I", adc, 0x38, 3 << 15)
    a = decode_adc(bytes(adc))
    assert a["injected_count"] == 1
    assert a["active_injected_channels"] == [3]

    gpio = bytearray(0x10)
    struct.pack_into("<I", gpio, 0x04, 0x33333333)
    g = decode_gpio(bytes(gpio))
    assert g["pins"]["8"]["cfg"] == 3
    assert g["pins"]["15"]["cfg"] == 3

    print("PASS: G30 SWD capture decoder self-test")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("capture", nargs="?", type=Path)
    ap.add_argument("--compare", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return 0
    if not args.capture:
        ap.error("capture directory/zip required unless --self-test is used")

    first = decode(load_source(args.capture))
    if args.json:
        print(json.dumps(first, indent=2, sort_keys=True))
    else:
        print(summary(first))

    if args.compare:
        second = decode(load_source(args.compare))
        changes = diff(first, second)
        print("\nCHANGES:")
        print("\n".join(changes) if changes else "(none in selected registers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
