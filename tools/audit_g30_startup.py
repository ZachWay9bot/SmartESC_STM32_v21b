#!/usr/bin/env python3
"""Inspect actual linked G30 exception vectors, without executing firmware."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

APP_BASE = 0x08001000
APP_LIMIT = 0x0800E800


def audit(data: bytes) -> dict:
    if data[:7] != b"\x7fELF\x01\x01\x01" or struct.unpack_from("<H", data, 18)[0] != 40:
        raise ValueError("Expected little-endian ELF32 ARM image")
    phoff, shoff = struct.unpack_from("<II", data, 28)
    phsize, phcount, shsize, shcount = struct.unpack_from("<4H", data, 42)
    sections = [struct.unpack_from("<10I", data, shoff+i*shsize) for i in range(shcount)]
    symbols = {}
    for section in sections:
        if section[1] != 2:
            continue
        strings = sections[section[6]]
        strtab = data[strings[4]:strings[4]+strings[5]]
        for off in range(section[4], section[4]+section[5], section[9]):
            name, value, size, info, other, index = struct.unpack_from("<IIIBBH", data, off)
            end = strtab.find(b"\0", name)
            symbol = strtab[name:end].decode("ascii", "replace")
            if symbol:
                symbols[symbol] = {"address":value,"binding":info >> 4,"section":index}
    vectors = None
    for i in range(phcount):
        typ, off, virtual, physical, filesz, memsz, flags, align = struct.unpack_from("<8I", data, phoff+i*phsize)
        if typ == 1 and physical <= APP_BASE and APP_BASE+64 <= physical+filesz:
            vectors = struct.unpack_from("<16I", data, off+APP_BASE-physical)
            break
    if vectors is None:
        raise ValueError("Application vector table is missing")
    errors = []
    default = symbols.get("Default_Handler", {}).get("address", 0) & ~1
    checked = {}
    for slot, name in [(11,"SVC_Handler"),(14,"PendSV_Handler"),(15,"SysTick_Handler")]:
        symbol = symbols.get(name, {})
        vector = vectors[slot]
        address = symbol.get("address", 0)
        checked[name] = {"vector":f"0x{vector:08X}","symbol":f"0x{address:08X}",
                         "binding":symbol.get("binding")}
        if (not symbol.get("section") or symbol.get("binding") == 2 or
                (vector & ~1) == default or not vector & 1 or
                not APP_BASE <= (vector & ~1) < APP_LIMIT or
                (vector & ~1) != (address & ~1)):
            errors.append(f"{name} is not a strong application handler")
    # LED task's address must survive linking: main must reach task_init().
    # LTO may inline the initializer, so check its task entry, not task_init.
    led_entries = [name for name, symbol in symbols.items()
                   if (name == "task_LED" or name.startswith("task_LED.")) and symbol.get("section")]
    if not led_entries:
        errors.append("LED task entry absent: central task initialization is not linked")
    return {"result":"PASS" if not errors else "FAIL", "offline_only":True,
            "hardware_verified":False,"elf_sha256":hashlib.sha256(data).hexdigest(),
            "vectors":checked,"led_task_entries":led_entries,"errors":errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    result = audit(args.elf.read_bytes())
    encoded = json.dumps(result, indent=2) + "\n"
    print(encoded, end="")
    if args.json_out:
        args.json_out.write_text(encoded, encoding="utf-8")
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
