#!/usr/bin/env python3
"""Read-only negative tests for G30 sealed-board release qualification.

These tests NEVER claim that passing metadata proves stock recovery. Real
independent rescue requires physical evidence; no serial ports are accessed.
"""
from pathlib import Path
import hashlib
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/recovery"))
import release_qualification as gate


class G30ReleaseEvidenceAudit(unittest.TestCase):
    def test_source_recovery_audit_remains_intact(self):
        self.assertEqual(gate.static_check(), [])

    def test_missing_hardware_evidence_still_blocks(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(gate.check_hardware(Path(d) / "absent.json", None))

    def test_missing_witness_or_images_still_blocks(self):
        candidate = b"sample-image-not-a-real-firmware"
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            image = folder / "candidate.bin"
            image.write_bytes(candidate)
            data = {
                "board_profile": "G30_STM32F103_3CAP",
                "bootloader_sha256": "0" * 64,
                "physical_flash_geometry": "UNKNOWN",
                "image_sha256": "0" * 64,
                "stock_image_sha256": "0" * 64,
                "restore_log_sha256": "0" * 64,
                "entrypoint": "not validated",
                "uart_wiring": "not validated",
                "independent_rescue": False,
                "actual_restore_to_stock": False,
                "witness": "",
                "test_date": "",
            }
            evidence = folder / "evidence.json"
            evidence.write_text(json.dumps(data))
            errors = gate.check_hardware(evidence, image)
            self.assertTrue(any("witness" in item for item in errors))
            self.assertTrue(any("image" in item.lower() for item in errors))
            self.assertTrue(any("128KiB" in item for item in errors))
            self.assertTrue(any("independent" in item.lower() for item in errors))
            self.assertTrue(any("stock DRV" in item for item in errors))

    def test_exact_image_binding_required(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            firmware = folder / "candidate.bin"
            firmware.write_bytes(b"image A")
            payload = {
                k: "not witnessed" for k in gate.FIELDS
            }
            payload.update({
                "board_profile": "G30_STM32F103_3CAP",
                "bootloader_sha256": hashlib.sha256(b"boot").hexdigest(),
                "image_sha256": hashlib.sha256(b"different candidate").hexdigest(),
                "stock_image_sha256": hashlib.sha256(b"stock").hexdigest(),
                "restore_log_sha256": hashlib.sha256(b"no real log").hexdigest(),
                "physical_flash_geometry": "UNKNOWN",
                "independent_rescue": False,
                "actual_restore_to_stock": False,
            })
            manifest = folder / "evidence.json"
            manifest.write_text(json.dumps(payload))
            errors = gate.check_hardware(manifest, firmware)
            self.assertIn("No proven restore for EXACT candidate image", errors)

    def test_template_is_not_accidentally_release_qualified(self):
        template = ROOT / "docs/G30_UART_RESTORE_EVIDENCE_TEMPLATE.json"
        data = json.loads(template.read_text())
        self.assertIs(data["independent_rescue"], False)
        self.assertIs(data["actual_restore_to_stock"], False)
        self.assertNotEqual(data["physical_flash_geometry"], "128K_VERIFIED")
        self.assertTrue(gate.check_hardware(template, None))


if __name__ == "__main__":
    unittest.main()
