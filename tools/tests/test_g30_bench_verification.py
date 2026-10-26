#!/usr/bin/env python3
"""No-device regression for offline G30 application/Driver/manifest verification."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from verify_g30_bench_artifacts import verify


class G30BenchVerification(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.raw = base / "g30p.bin"
        self.driver = base / "Driver.bin"
        self.manifest = base / "manifest.json"
        self.raw.write_bytes(struct.pack("<II", 0x20004FF0, 0x08001009) + bytes(56))
        cmd = [
            sys.executable, str(ROOT / "tools/make_bench_iap.py"),
            str(self.raw), str(self.driver), "--manifest", str(self.manifest)
        ]
        run = subprocess.run(cmd, text=True, capture_output=True)
        if run.returncode:
            raise AssertionError(run.stderr)

    def tearDown(self):
        self.tmp.cleanup()

    def test_clean_offline_manifest_and_encoding(self):
        result = verify(self.raw, self.driver, self.manifest)
        self.assertEqual(result["result"], "PASS")
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["verified_offline_only"])
        self.assertFalse(result["hardware_validated"])

    def test_rejects_corrupted_uart_driver(self):
        data = bytearray(self.driver.read_bytes())
        data[12] ^= 1
        self.driver.write_bytes(data)
        errors = verify(self.raw, self.driver, self.manifest)["errors"]
        self.assertTrue(any("NinebotTEA" in e for e in errors))
        self.assertTrue(any("iap_driver_sha256" in e for e in errors))

    def test_rejects_misidentified_or_swapped_application(self):
        data = bytearray(self.raw.read_bytes())
        data[20] ^= 1
        self.raw.write_bytes(data)
        errors = verify(self.raw, self.driver, self.manifest)["errors"]
        self.assertTrue(any("NinebotTEA" in e for e in errors))
        self.assertTrue(any("application_sha256" in e for e in errors))

    def test_rejects_false_manifest_and_invalid_vector(self):
        data = json.loads(self.manifest.read_text())
        data["packaging"] = "shufile"
        data["initial_stack_pointer"] = "0x00000000"
        self.manifest.write_text(json.dumps(data))
        errors = verify(self.raw, self.driver, self.manifest)["errors"]
        self.assertTrue(any("packaging" in e for e in errors))
        self.assertTrue(any("initial_stack_pointer" in e for e in errors))
        raw = bytearray(self.raw.read_bytes())
        raw[:4] = bytes(4)
        self.raw.write_bytes(raw)
        errors = verify(self.raw, self.driver, self.manifest)["errors"]
        self.assertTrue(any("Invalid plain application" in e for e in errors))

    def test_cli_exits_nonzero_on_mismatch_and_writes_json(self):
        output = Path(self.tmp.name) / "verification.json"
        run = subprocess.run([
            sys.executable, str(ROOT / "tools/verify_g30_bench_artifacts.py"),
            str(self.raw), str(self.driver), str(self.manifest),
            "--json-out", str(output)
        ], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(output.read_text())["result"], "PASS")

        self.driver.write_bytes(self.driver.read_bytes()[:-1])
        run = subprocess.run([
            sys.executable, str(ROOT / "tools/verify_g30_bench_artifacts.py"),
            str(self.raw), str(self.driver), str(self.manifest)
        ], capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        self.assertEqual(json.loads(run.stdout)["result"], "FAIL")


if __name__ == "__main__":
    unittest.main()
