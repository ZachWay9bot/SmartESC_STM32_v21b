#!/usr/bin/env python3
"""G30 Coast-only command routing contract (no hardware simulation)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
VESC = (ROOT / "common_files/src/VescToSTM.c").read_text()
COMMANDS = (ROOT / "common_files/src/VescCommand.c").read_text()
APP = (ROOT / "common_files/src/app_uartcomm.c").read_text()


def function_body(name):
    return VESC.split("void " + name + "(", 1)[1].split("\n}\n", 1)[0]


class G30CoastOnly(unittest.TestCase):
    def test_brake_current_g30_switches_outputs_off_without_speed_ramp(self):
        body = function_body("VescToSTM_set_brake")
        self.assertIn("#ifdef G30P", body)
        g30 = body.split("#ifdef G30P", 1)[1].split("#else", 1)[0]
        self.assertIn("VescToSTM_set_current(0.0f, 0.0f);", g30)
        self.assertIn("VescToSTM_pwm_stop();", g30)
        self.assertNotIn("MCI_ExecSpeedRamp", g30)
        self.assertIn("MCI_ExecSpeedRamp", body.split("#else", 1)[1])

    def test_brake_relative_uses_same_coast_path(self):
        body = function_body("VescToSTM_set_brake_rel_int")
        self.assertIn("VescToSTM_set_brake(0);", body.split("#else", 1)[0])
        self.assertIn("MCI_ExecSpeedRamp", body.split("#else", 1)[1])
        self.assertIn("VescToSTM_set_brake(", function_body("VescToSTM_set_brake_current_rel"))

    def test_dashboard_and_vesc_tool_brake_reach_coast_path(self):
        self.assertIn("case ADC_CTRL_TYPE_CURRENT_NOREV_BRAKE_ADC:", APP)
        self.assertIn("VescToSTM_set_brake_current_rel(brake);", APP)
        g30 = COMMANDS.split("static void commands_process_packet_g30(", 1)[1].split("\n#endif", 1)[0]
        brake = g30.split("case COMM_SET_CURRENT_BRAKE:", 1)[1].split("case COMM_SET_MCCONF:", 1)[0]
        self.assertIn("VescToSTM_set_brake(", brake)
        self.assertIn("case COMM_DETECT_APPLY_ALL_FOC:", g30)
        self.assertIn("VescToSTM_set_current_rel(pwr);", APP)


if __name__ == "__main__":
    unittest.main()
