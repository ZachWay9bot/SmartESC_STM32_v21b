#!/usr/bin/env python3
"""G30 Detect All source contract checks.

These checks target the historical failure mode where PWM was requested
before the detector entered open-loop mode. The board remains untested.
Run: python3 -m unittest discover -s tools/tests -p 'test_g30_detect_contract.py' -v
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TUNE = (ROOT / "common_files/src/tune.c").read_text()
SL = (ROOT / "common_files/src/g30_sensorless.c").read_text()
COMMANDS = (ROOT / "common_files/src/VescCommand.c").read_text()


def body(text, marker):
    pos = text.index(marker)
    begin = text.index("{", pos)
    depth = 0
    for i in range(begin, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[begin + 1:i]
    raise AssertionError("unclosed function: " + marker)


class G30DetectAllContract(unittest.TestCase):
    def test_stationary_detection_enters_open_loop_before_pwm(self):
        for marker in (
            "float tune_foc_measure_resistance(",
            "float tune_foc_measure_inductance(",
            "bool tune_foc_measure_flux_linkage_openloop(",
        ):
            with self.subTest(function=marker):
                code = body(TUNE, marker)
                g30_before_pwm = code[:code.index("VescToSTM_pwm_force(true, true);")]
                self.assertIn("#ifdef G30P", g30_before_pwm)
                self.assertIn("VescToSTM_set_open_loop(true, 0, 0);",
                              g30_before_pwm)
                self.assertLess(g30_before_pwm.index("VescToSTM_set_open_loop(true, 0, 0);"),
                                len(g30_before_pwm))

    def test_flux_cleanup_restores_normal_push_start_state(self):
        code = body(TUNE, "bool tune_foc_measure_flux_linkage_openloop(")
        cleanup = code.split("g30_detect_cleanup:", 1)[1].split("#else", 1)[0]
        self.assertIn("#ifdef G30P", cleanup)
        ordered = (
            "VescToSTM_set_current(0.0f, 0.0f);",
            "VescToSTM_pwm_force(false, false);",
            "VescToSTM_set_open_loop(false, 0, 0);",
        )
        positions = [cleanup.index(text) for text in ordered]
        self.assertEqual(positions, sorted(positions))

    def test_normal_motor_start_still_requires_roll_lock(self):
        code = body(SL, "bool G30SL_PreparePwmStart(")
        self.assertIn("if (h->_Super.open_loop) return true;", code)
        self.assertIn("if (!g30sl_core_roll_ready(&h->core, DWT->CYCCNT)) return false;", code)
        self.assertLess(code.index("if (h->_Super.open_loop) return true;"),
                        code.index("if (!g30sl_core_roll_ready("))

    def test_detect_all_reports_vesc_reply_and_does_not_modify_flux_scale(self):
        worker = body(COMMANDS, "static void g30_detect_worker(")
        self.assertIn("buffer[ind++] = COMM_DETECT_APPLY_ALL_FOC;", worker)
        self.assertIn("buffer_append_int16(buffer, res, &ind);", worker)
        self.assertIn("if (tune_abort_requested)", worker)
        detect_flux = body(COMMANDS, "static bool g30_detect_flux(")
        self.assertIn("lambda *= 2.0f;", detect_flux)


if __name__ == "__main__":
    unittest.main()
