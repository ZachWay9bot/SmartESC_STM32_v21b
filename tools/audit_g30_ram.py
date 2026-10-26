#!/usr/bin/env python3
"""Read-only G30 STM32F103 SRAM allocation audit from a linked ELF32 image.

This analyzes ELF SHF_ALLOC sections using their linked addresses, including
NO-BITS reservations such as the startup stack. It does not touch a controller,
flash image, bootloader, release gate or motor-control state.

Usage:
  python3 tools/audit_g30_ram.py --elf g30p/STM32CubeIDE/Debug/g30p.elf \
      --json-out g30p/STM32CubeIDE/Debug/g30-ram-audit.json
"""
import argparse
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAM_BASE = 0x20000000
RAM_LENGTH = 20 * 1024
ALLOC = 2


def elf_sram_sections(filename: Path):
    data = filename.read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        raise ValueError("Expected 32-bit little-endian ELF")
    hdr = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
    if hdr[1] != 40:  # EM_ARM
        raise ValueError("Expected ARM target")
    offset, shentsize, shnum, names_id = hdr[5], hdr[10], hdr[11], hdr[12]
    if shentsize < 40 or not 0 < names_id < shnum:
        raise ValueError("Invalid ELF section header table")
    if offset + shentsize * shnum > len(data):
        raise ValueError("ELF section table is truncated")

    def sh(idx):
        return struct.unpack_from("<IIIIIIIIII", data, offset + idx * shentsize)

    names = sh(names_id)
    namebytes = data[names[4]:names[4] + names[5]]
    if len(namebytes) != names[5]:
        raise ValueError("ELF section names truncated")
    result = []
    for i in range(shnum):
        rec = sh(i)
        nameoff, typ, flags, addr, _, size = rec[:6]
        if not (flags & ALLOC) or size == 0:
            continue
        if RAM_BASE <= addr < RAM_BASE + RAM_LENGTH:
            end = namebytes.find(b"\x00", nameoff)
            if not 0 <= nameoff < len(namebytes) or end < nameoff:
                raise ValueError("Invalid ELF section name")
            name = namebytes[nameoff:end].decode("ascii", "replace")
            if addr + size > RAM_BASE + RAM_LENGTH:
                raise ValueError(f"RAM section {name} overflows physical SRAM")
            result.append({"name": name, "address": addr,
                           "size": size, "end": addr + size, "type": typ})
    if not result:
        raise ValueError("No allocated SRAM sections found")
    return sorted(result, key=lambda s: s["address"])


def config_budget(root=ROOT):
    p = (root / "common_files/inc/product.h").read_text()
    match = re.search(r"#ifdef\s+G30P(.*?)#endif", p, re.S)
    if not match:
        raise ValueError("G30P product config missing")
    size = re.search(r"#define\s+HEAP_SIZE_KB\s+(\d+)", match.group(1))
    if not size:
        raise ValueError("G30P heap size missing")
    conf = (root / "common_files/inc/FreeRTOSConfig.h").read_text()
    if "configTOTAL_HEAP_SIZE" not in conf or "HEAP_SIZE_KB*1024" not in conf:
        raise ValueError("FreeRTOS heap allocation changed")
    linker = (root / "g30p/STM32CubeIDE/STM32F103C8TX_FLASH.ld").read_text()
    if "ORIGIN = 0x20000000,   LENGTH = 20K" not in linker:
        raise ValueError("G30 SRAM layout changed: re-audit")
    return int(size.group(1)) * 1024


def audit(filename: Path, root=ROOT):
    sections = elf_sram_sections(filename)
    high = max(s["end"] for s in sections)
    configured_heap = config_budget(root)
    allocated = high - RAM_BASE
    reserved_free = RAM_LENGTH - allocated
    return {
        "report_type": "static_elf_sram_only_not_runtime_heap",
        "elf": str(filename),
        "ram_base": f"0x{RAM_BASE:08X}",
        "physical_sram_bytes": RAM_LENGTH,
        "sram_allocated_including_startup_reservations_bytes": allocated,
        "unallocated_sram_bytes": reserved_free,
        "freertos_heap4_configured_bytes": configured_heap,
        "freertos_heap_runtime_free_bytes": None,
        "freertos_task_stack_min_free_bytes": None,
        "allocated_sections": sections,
        "note": (
            "14-KiB FreeRTOS heap_4 is already inside SRAM .bss. "
            "Unallocated SRAM is NOT task heap. Stack high-water marks and "
            "heap low watermark require live firmware instrumentation."
        ),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--json-out", type=Path)
    opts = parser.parse_args()
    report = audit(opts.elf)
    payload = json.dumps(report, indent=2) + "\n"
    print(payload, end="")
    if opts.json_out:
        opts.json_out.parent.mkdir(parents=True, exist_ok=True)
        opts.json_out.write_text(payload)


if __name__ == "__main__":
    main()
