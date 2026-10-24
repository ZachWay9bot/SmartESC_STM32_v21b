#!/usr/bin/env python3
"""Regression tests of the read-only G30 FreeRTOS heap-path inventory."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "g30_heap_inventory", ROOT / "tools/audit_g30_heap_paths.py")
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)


class G30HeapPathAudit(unittest.TestCase):
    def test_guard_detector_understands_both_existing_c_forms(self):
        self.assertTrue(audit_module.has_null_guard(
            ";\n if (buffer == NULL) { return; }\n", "buffer"))
        self.assertTrue(audit_module.has_null_guard(
            ";\n if (!buffer) return;\n", "buffer"))
        self.assertFalse(audit_module.has_null_guard(
            ";\n memset(buffer, 0, 64);\n", "buffer"))

    def test_reports_known_risks_without_claiming_runtime_failure(self):
        report = audit_module.audit()
        paths = {path["id"]: path for path in report["paths"]}
        self.assertEqual(report["known_paths_examined"], 7)
        self.assertTrue(report["not_runtime_measurement"])
        for ident in ("dashboard_uart_rx", "dashboard_task_create"):
            with self.subTest(ident=ident):
                self.assertIn(ident, paths)
                self.assertFalse(paths[ident]["guarded_before_use"])
                self.assertIn(ident, report["unguarded_paths"])
                self.assertGreater(paths[ident]["line"], 0)
        for ident in ("packet_state", "packet_rx_buffer",
                      "vesc_send_mcconf", "vesc_send_appconf",
                      "detect_task_create"):
            with self.subTest(ident=ident):
                self.assertTrue(paths[ident]["guarded_before_use"])
                self.assertNotIn(ident, report["unguarded_paths"])

    def test_report_paths_remain_within_common_files_only(self):
        report = audit_module.audit()
        self.assertTrue(all(item["source"].startswith("common_files/src/")
                            for item in report["paths"]))
        self.assertTrue(all(item["function"] and item["description"]
                            for item in report["paths"]))


if __name__ == "__main__":
    unittest.main()
