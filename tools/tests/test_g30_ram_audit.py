#!/usr/bin/env python3
"""Validate read-only ELF32 SRAM-audit parser with synthetic ARM ELF images.

Never contacts the controller or produces a firmware image.
"""
from pathlib import Path
import importlib.util
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "g30_memory_audit", ROOT / "tools/audit_g30_ram.py")
MEM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEM)


def fixture(last_size=0x500):
    names = b"\0.shstrtab\0.data\0.bss\0._user_heap_stack\0"
    positions = {name: names.index(name.encode())
                 for name in (".shstrtab", ".data", ".bss",
                              "._user_heap_stack")}
    data = bytearray(0x400)
    ident = b"\x7fELF" + bytes((1, 1, 1)) + bytes(9)
    struct.pack_into("<16sHHIIIIIHHHHHH", data, 0,
                     ident, 2, 40, 1, 0, 0, 0x200, 0,
                     52, 0, 0, 40, 5, 1)
    data[0x100:0x100+len(names)] = names
    for idx, name, typ, flags, addr, off, size in (
        (1, ".shstrtab", 3, 0, 0, 0x100, len(names)),
        (2, ".data", 1, 3, 0x20000000, 0x350, 0x100),
        (3, ".bss", 8, 3, 0x20000100, 0, 0x200),
        (4, "._user_heap_stack", 8, 3, 0x20000300, 0, last_size),
    ):
        struct.pack_into("<IIIIIIIIII", data, 0x200+idx*40,
                         positions[name], typ, flags, addr, off, size,
                         0, 0, 4, 0)
    return bytes(data)


class SRAMAuditTests(unittest.TestCase):
    def test_g30_heap_includes_14k_reserved_in_bss(self):
        self.assertEqual(MEM.config_budget(), 14336)
        config = (ROOT / "common_files/inc/FreeRTOSConfig.h").read_text()
        self.assertIn("#define configSUPPORT_DYNAMIC_ALLOCATION         1", config)
        self.assertIn("#define USE_FreeRTOS_HEAP_4", config)

    def test_elf_parser_counts_nobits_stack_reservations(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "mock.elf"
            path.write_bytes(fixture())
            report = MEM.audit(path)
            self.assertEqual(
                report["sram_allocated_including_startup_reservations_bytes"],
                0x800)
            self.assertEqual(report["unallocated_sram_bytes"], 20480 - 0x800)
            self.assertIsNone(report["freertos_heap_runtime_free_bytes"])
            self.assertIsNone(report["freertos_task_stack_min_free_bytes"])
            self.assertEqual([s["name"] for s in report["allocated_sections"]],
                             [".data", ".bss", "._user_heap_stack"])

    def test_elf_rejects_sram_section_beyond_physical_memory(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "overflow.elf"
            path.write_bytes(fixture(0x6000))
            with self.assertRaisesRegex(ValueError, "overflows physical SRAM"):
                MEM.audit(path)

    def test_not_arm_or_not_elf_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "invalid.elf"
            path.write_bytes(b"not ELF")
            with self.assertRaisesRegex(ValueError, "Expected 32-bit"):
                MEM.elf_sram_sections(path)


if __name__ == "__main__":
    unittest.main()
