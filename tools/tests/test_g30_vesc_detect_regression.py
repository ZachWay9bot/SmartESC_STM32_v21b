#!/usr/bin/env python3
"""Active G30 VESC dispatcher and Detect All source contracts (no hardware).

The G30P compact dispatcher is distinct from the legacy generic dispatcher.
Static assertions cover guard ordering and known response contracts; they
cannot reproduce FreeRTOS scheduling or guarantee physical motor behavior.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
COMMANDS = (ROOT / "common_files/src/VescCommand.c").read_text()
ACTIVE = COMMANDS.split("static void commands_process_packet_g30(", 1)[1].split(
    "\n#endif", 1)[0]


def routine(name):
    found = re.search(r"\b" + re.escape(name) + r"\s*\([^;]*?\)\s*\{",
                      COMMANDS, re.S)
    if not found:
        raise AssertionError("Missing C function " + name)
    start = found.end() - 1
    depth = 0
    for pos in range(start, len(COMMANDS)):
        if COMMANDS[pos] == "{":
            depth += 1
        elif COMMANDS[pos] == "}":
            depth -= 1
            if not depth:
                return COMMANDS[start:pos + 1]
    raise AssertionError("Unterminated C function " + name)


def case_body(marker, next_marker):
    return ACTIVE.split("case " + marker + ":", 1)[1].split(
        "case " + next_marker + ":", 1)[0]


class G30VescDetectRegression(unittest.TestCase):
    def test_compact_dispatcher_is_reachable_on_g30(self):
        entry = COMMANDS.split("void commands_process_packet(", 1)[1]
        self.assertIn("#ifdef G30P", entry)
        self.assertIn("commands_process_packet_g30(data, len, reply_func, phandle);", entry)
        self.assertIn("if (!len || !reply_func) return;", ACTIVE)

    def test_current_and_brake_commands_are_length_guarded(self):
        torque = case_body("COMM_SET_CURRENT", "COMM_SET_CURRENT_BRAKE")
        brake = case_body("COMM_SET_CURRENT_BRAKE", "COMM_SET_MCCONF")
        for section in (torque, brake):
            self.assertLess(section.index("if (len < 4u) break;"),
                            section.index("buffer_get_int32(data, &ind)"))
            self.assertIn("VescToSTM_timeout_reset();", section)

    def test_telemetry_selective_reads_mask_after_four_byte_guard(self):
        values = case_body("COMM_GET_VALUES", "COMM_SET_CURRENT")
        self.assertLess(values.index("if (len < 4u) break;"),
                        values.index("buffer_get_uint32(data, &ri)"))
        fields = set(int(i) for i in re.findall(r"if \(mask & \(1u << (\d+)\)\)", values))
        self.assertEqual(fields, set(range(22)), "Selective telemetry bit layout changed")
        self.assertIn("reply_func(send_buffer, ind, phandle);", values)

    def test_detect_does_not_block_serial_task_and_can_be_aborted(self):
        cmd = case_body("COMM_DETECT_APPLY_ALL_FOC", "COMM_APP_DISABLE_OUTPUT")
        self.assertIn("if (!g30_detect_active)", cmd)
        self.assertIn('xTaskCreate(g30_detect_worker, "g30det", 320, NULL,', cmd)
        self.assertIn("!= pdPASS", cmd)
        self.assertIn("g30_detect_active = false;", cmd)
        self.assertIn("buffer_append_int16(buffer, -100, &ind);", cmd)
        guard = ACTIVE.split("switch (packet_id)", 1)[0]
        self.assertIn("g30_detect_active &&", guard)
        self.assertIn("packet_id != COMM_ALIVE", guard)
        self.assertIn("packet_id != COMM_APP_DISABLE_OUTPUT", guard)
        abort = case_body("COMM_APP_DISABLE_OUTPUT", "COMM_ALIVE")
        self.assertIn("if (g30_detect_active) tune_abort_requested = true;", abort)
        self.assertIn("VescToSTM_pwm_stop();", abort)

    def test_detect_parameter_bounds_and_result_write_order(self):
        rl = routine("g30_detect_rl")
        flux = routine("g30_detect_flux")
        worker = routine("g30_detect_worker")
        for item in ("*r > 0.05f", "*r < 2.5f",
                     "*l_h > 0.00005f", "*l_h < 0.003f"):
            self.assertIn(item, rl)
        for item in ("lambda *= 2.0f;", "!(lambda > 0.002f)",
                     "!(lambda < 0.04f)"):
            self.assertIn(item, flux)
        steps = (
            "g30_detect_rl(&r, &l_h)",
            "g30_detect_flux(r, l_h, &flux)",
            "cfg->foc_motor_r = r;",
            "cfg->foc_motor_l = l_h;",
            "cfg->foc_motor_flux_linkage = flux;",
            "conf_general_setup_mc(cfg);",
            "conf_general_store_mc_configuration(cfg, false)",
            "commands_send_mcconf(COMM_GET_MCCONF, cfg, g30_detect_phandle);",
            "res = 0;",
            "buffer_append_int16(buffer, res, &ind);",
            "g30_detect_active = false;",
        )
        # Verify the established Detect All path on its own. The new manual
        # detect branches intentionally exit before the original path begins.
        detect_all = worker.split("int16_t res = -100;", 1)[1]
        positions = [detect_all.index(item) for item in steps]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("res = -11;", worker)  # abort
        self.assertIn("res = -10;", worker)  # flux failure
        self.assertIn("res = -100;", worker)  # initial error

    def test_manual_rl_and_flux_use_existing_async_g30_detector(self):
        for cmd in ("COMM_DETECT_APPLY_ALL_FOC", "COMM_DETECT_MOTOR_R_L",
                    "COMM_DETECT_MOTOR_FLUX_LINKAGE_OPENLOOP"):
            self.assertIn("case " + cmd + ":", ACTIVE)
        worker = routine("g30_detect_worker")
        self.assertIn("if (g30_detect_command != COMM_DETECT_APPLY_ALL_FOC)", worker)
        self.assertIn("g30_detect_rl(&r, &l_h)", worker)
        self.assertIn("g30_detect_flux(r, l_h, &flux)", worker)
        self.assertIn("ok ? l_h * 1e6f : 0.0f, 1e3f", worker)
        self.assertIn("ok ? flux : 0.0f, 1e7f", worker)
        self.assertIn("packet_id == COMM_DETECT_MOTOR_FLUX_LINKAGE_OPENLOOP && len < 16u", ACTIVE)
        self.assertIn('xTaskCreate(g30_detect_worker, "g30det", 320, NULL,', ACTIVE)

    def test_manual_detection_never_stores_motor_configuration(self):
        worker = routine("g30_detect_worker")
        manual = worker.split("if (g30_detect_command != COMM_DETECT_APPLY_ALL_FOC)", 1)[1].split(
            "int16_t res = -100;", 1)[0]
        self.assertNotIn("conf_general_store_mc_configuration(", manual)
        self.assertNotIn("conf_general_setup_mc(", manual)
        self.assertIn("g30_detect_active = false;", manual)


if __name__ == "__main__":
    unittest.main()
