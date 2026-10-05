#!/usr/bin/env python3
"""
Build a ScooterHacking ZIPv3 package for the G30 STM32 DeltaESC image.

The G30 SHU build is linked as an application at 0x08001000 so the stock
4 KiB Ninebot IAP bootloader at 0x08000000 is not part of FIRM.bin.

Package:
  - FIRM.bin      plaintext application image
  - FIRM.bin.enc  NinebotTEA encrypted application image
  - info.json     ZIPv3 schema 1 metadata
  - params.txt    human-readable build notes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path

APP_BASE = 0x08001000
APP_LIMIT = 0x0800D800
MAX_APP_SIZE = APP_LIMIT - APP_BASE

DEFAULT_KEY = bytes([
    0xFE, 0x80, 0x1C, 0xB2, 0xD1, 0xEF, 0x41, 0xA6,
    0xA4, 0x17, 0x31, 0xF5, 0xA0, 0x68, 0x24, 0xF0,
])

DELTA = 0x9E3779B9
MASK32 = 0xFFFFFFFF


def _u32(v: int) -> int:
    return v & MASK32


def _key_words(key: bytes) -> list[int]:
    if len(key) != 16:
        raise ValueError("NinebotTEA key must be 16 bytes")
    return list(struct.unpack("<4I", key))


def _update_key(words: list[int]) -> list[int]:
    raw = bytearray(struct.pack("<4I", *words))
    for i in range(16):
        raw[i] = (raw[i] + i) & 0xFF
    return list(struct.unpack("<4I", raw))


def _encrypt_block(y: int, z: int, key: list[int]) -> tuple[int, int]:
    total = 0
    for _ in range(32):
        total = _u32(total + DELTA)
        y = _u32(
            y + (((_u32(z << 4) + key[0]) ^ (z + total) ^ ((z >> 5) + key[1])))
        )
        z = _u32(
            z + (((_u32(y << 4) + key[2]) ^ (y + total) ^ ((y >> 5) + key[3])))
        )
    return y, z


def _checksum(body: bytes) -> int:
    if len(body) % 4:
        raise ValueError("checksum body must be 32-bit aligned")
    total = 0
    for off in range(0, len(body), 4):
        (word,) = struct.unpack_from("<I", body, off)
        total = _u32(total + word)
    total = ((total >> 16) & 0xFFFF) | ((total & 0xFFFF) << 16)
    return _u32(total ^ MASK32)


def ninebot_tea_encrypt(plain: bytes, key: bytes = DEFAULT_KEY) -> bytes:
    body = bytearray(plain)

    # NinebotTEA checksum/padding convention.
    while len(body) % 4:
        body.append(0)
    if len(body) % 8 == 0:
        body.extend(b"\x00" * 4)
    body.extend(struct.pack("<I", _checksum(body)))

    if len(body) % 8:
        raise AssertionError("NinebotTEA padded size is not 8-byte aligned")

    out = bytearray(len(body))
    key_words = _key_words(key)
    iv_lo = 0
    iv_hi = 0
    processed = 0

    for off in range(0, len(body), 8):
        if processed == 1024:
            key_words = _update_key(key_words)
            processed = 0

        y, z = struct.unpack_from("<II", body, off)
        y ^= iv_lo
        z ^= iv_hi
        ey, ez = _encrypt_block(y, z, key_words)
        struct.pack_into("<II", out, off, ey, ez)
        iv_lo, iv_hi = ey, ez
        processed += 8

    return bytes(out)


def validate_app_image(data: bytes) -> tuple[int, int]:
    if len(data) < 8:
        raise ValueError("firmware image is too short")
    if len(data) > MAX_APP_SIZE:
        raise ValueError(
            f"firmware is {len(data)} bytes, but SHU layout allows at most "
            f"{MAX_APP_SIZE} bytes (0x{MAX_APP_SIZE:X})"
        )

    sp, reset = struct.unpack_from("<II", data, 0)
    reset_addr = reset & ~1

    if not (0x20000000 <= sp <= 0x20005000):
        raise ValueError(f"invalid initial SP 0x{sp:08X}")
    if not (reset & 1):
        raise ValueError(f"reset handler is not Thumb: 0x{reset:08X}")
    if not (APP_BASE <= reset_addr < APP_LIMIT):
        raise ValueError(
            f"reset handler 0x{reset_addr:08X} is outside SHU app region "
            f"0x{APP_BASE:08X}..0x{APP_LIMIT - 1:08X}"
        )

    return sp, reset


def md5hex(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("firmware", type=Path, help="G30P application .bin")
    ap.add_argument("output", type=Path, help="output SHU ZIP")
    ap.add_argument(
        "--name",
        default="DeltaESC G30D v0.2",
        help="displayName stored in info.json",
    )
    args = ap.parse_args()

    plain = args.firmware.read_bytes()
    sp, reset = validate_app_image(plain)
    encrypted = ninebot_tea_encrypt(plain)

    info = {
        "schemaVersion": 1,
        "firmware": {
            "displayName": args.name,
            "model": "max",
            "enforceModel": True,
            "type": "DRV",
            "compatible": ["max_DRV_STM32F103CxT6"],
            "encryption": "both",
            "md5": {
                "bin": md5hex(plain),
                "enc": md5hex(encrypted),
            },
        },
    }

    notes = (
        "DeltaESC G30D v0.2 + dual STAR/DELTA profile candidate\n"
        "Application base: 0x08001000 (stock 4 KiB IAP bootloader preserved)\n"
        "Application limit: 0x0800D7FF (50 KiB; pages 54/55 reserved for DeltaESC config)\n"
        "Stock OTA staging from 0x0800E000 upward is preserved\n"
        "Throttle release: coast\n"
        "Brake: motor cut, no regenerative braking\n"
        "STAR/DELTA: rear-light output, DELTA >= 32 km/h, STAR <= 26 km/h\n"
        "Relay switching: wait for |Iq| <= 2 A, then 100 ms settle\n"
        "Stock BMS: USART3 heartbeat/activator every 200 ms + read-only telemetry\n"
        "Config: companion-app protocol 0x7D; STAR/DELTA R/L/flux/current profiles\n"
        "Motor setup: R/L + flux + Hall detect, with DELTA Hall verification\n"
        f"Image size: {len(plain)} bytes\n"
        f"Initial SP: 0x{sp:08X}\n"
        f"Reset handler: 0x{reset:08X}\n"
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("FIRM.bin", plain)
        zf.writestr("FIRM.bin.enc", encrypted)
        zf.writestr("info.json", json.dumps(info, indent=4) + "\n")
        zf.writestr("params.txt", notes)

    print(f"Wrote {args.output}")
    print(f"FIRM.bin:     {len(plain)} bytes  md5={md5hex(plain)}")
    print(f"FIRM.bin.enc: {len(encrypted)} bytes  md5={md5hex(encrypted)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
