#!/usr/bin/env python3
"""Read-only/on-disk regression for BENCH UART-IAP packaging, never flash.

Verify memory vectors, encrypted staging-size boundaries, hash provenance and
absence of SHU from the development packaging path. This is not a stock-
restore test, and does not claim the new application runs on hardware.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from make_shu_zip import APP_BASE, APP_LIMIT, MAX_APP_SIZE, validate_app_image, ninebot_tea_encrypt
from make_bench_iap import make_driver


def app(size=32, sp=0x20004FF0, reset=0x08001009):
    return struct.pack("<II", sp, reset) + bytes(size - 8)


class G30BenchIAPContract(unittest.TestCase):
    def test_valid_vectors_and_unchanged_ninebot_tea(self):
        raw = app()
        encrypted, sp, reset = make_driver(raw)
        self.assertEqual(sp, 0x20004FF0)
        self.assertEqual(reset, 0x08001009)
        self.assertEqual(encrypted, ninebot_tea_encrypt(raw))
        self.assertEqual(len(encrypted) % 8, 0)
        self.assertEqual(len(raw), 32)
        self.assertEqual(len(encrypted), 40)
        self.assertEqual(raw, app(), "packager modified caller input")

    def test_rejects_invalid_stack_and_reset_vectors(self):
        cases = (
            (0x1FFFFFFC, 0x08001009),
            (0x20005004, 0x08001009),
            (0x20004FF0, 0x08000009),  # bootloader region
            (0x20004FF0, APP_LIMIT | 1),  # outside application
            (0x20004FF0, APP_BASE + 8),   # reset not Thumb
        )
        for sp, reset in cases:
            with self.subTest(sp=hex(sp), reset=hex(reset)):
                with self.assertRaises(ValueError):
                    make_driver(app(sp=sp, reset=reset))

    def test_bounds_include_encryption_checksum_padding(self):
        with self.assertRaisesRegex(ValueError, "too short"):
            validate_app_image(b"1234567")
        with self.assertRaisesRegex(ValueError, "allows at most"):
            validate_app_image(app(MAX_APP_SIZE + 1))
        near_limit, _, _ = make_driver(app(MAX_APP_SIZE - 4))
        self.assertEqual(len(near_limit), MAX_APP_SIZE)
        with self.assertRaisesRegex(ValueError, "staging supports at most"):
            make_driver(app(MAX_APP_SIZE))
        with self.assertRaisesRegex(ValueError, "staging supports at most"):
            make_driver(app(MAX_APP_SIZE - 3))

    def test_cli_writes_matching_manifest_and_no_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "input.bin"
            driver = root / "BENCH_IAP_Driver.bin"
            manifest = root / "BENCH_MANIFEST.json"
            image.write_bytes(app(36))
            run = subprocess.run([
                sys.executable, str(ROOT / "tools/make_bench_iap.py"),
                str(image), str(driver), "--manifest", str(manifest)
            ], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            data = json.loads(manifest.read_text())
            self.assertEqual(data["status"], "BENCH_TEST_CANDIDATE_NOT_HARDWARE_VERIFIED")
            self.assertEqual(data["packaging"], "direct_encrypted_uart_iap_not_shu")
            self.assertEqual(data["application_sha256"],
                             hashlib.sha256(image.read_bytes()).hexdigest())
            self.assertEqual(data["iap_driver_sha256"],
                             hashlib.sha256(driver.read_bytes()).hexdigest())
            self.assertEqual(data["iap_driver_size_bytes"], len(driver.read_bytes()))
            self.assertEqual(set(p.suffix for p in root.iterdir()), {".bin", ".json"})

    def test_cli_refuses_to_overwrite_plain_application(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "input.bin"
            image.write_bytes(app())
            run = subprocess.run([
                sys.executable, str(ROOT / "tools/make_bench_iap.py"),
                str(image), str(image)
            ], capture_output=True, text=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("must not overwrite", run.stderr)
            self.assertEqual(image.read_bytes(), app())


if __name__ == "__main__":
    unittest.main()
