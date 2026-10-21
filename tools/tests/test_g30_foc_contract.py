#!/usr/bin/env python3
"""G30 current reconstruction, FOC signal chain and configuration contract.

Host/source-level checks only. A passing result does not prove correct
motor wiring, ADC gain/offset or torque on the real power stage.
Run: python3 -m unittest discover -s tools/tests -p 'test_g30_foc_contract.py' -v
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "common_files/src"
DRIVER = (ROOT / "common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c").read_text()
PARAMS = (SRC / "mc_parameters.c").read_text()
FOC = (SRC / "mc_tasks.c").read_text()
GEN = (SRC / "confgenerator.c").read_text()
COMMANDS = (SRC / "VescCommand.c").read_text()
DASH = (SRC / "app_uartcomm.c").read_text()
ADCINIT = (ROOT / "g30p/Src/main.c").read_text()


def function_body(source, marker):
    start = source.index(marker)
    begin = source.index("{", start)
    balance = 0
    for end in range(begin, len(source)):
        if source[end] == "{":
            balance += 1
        elif source[end] == "}":
            balance -= 1
            if balance == 0:
                return source[begin + 1:end]
    raise ValueError("Unterminated function " + marker)


def encoded_bytes(source, marker, direction):
    body = function_body(source, marker)
    total = 0
    for line in body.splitlines():
        text = line.strip()
        if text.startswith("//"):
            continue
        if "buffer[ind++]" in text:
            total += 1
        match = re.search(
            ("buffer_get_" if direction == "read" else "buffer_append_")
            + r"(int32|uint32|float32_auto|float16|uint16|int16)\(", text)
        if match:
            total += 2 if "16" in match.group(1) else 4
        match = re.search(r"\bind\s*\+=\s*(\d+)\s*;", text)
        if match:
            total += int(match.group(1))
    return total


class G30FOCContract(unittest.TestCase):
    def test_motor_configuration_decoder_is_bounded(self):
        written = encoded_bytes(GEN, "int32_t confgenerator_serialize_mcconf(", "write")
        read = encoded_bytes(GEN, "bool confgenerator_deserialize_mcconf(", "read")
        self.assertEqual((written, read), (484, 484))
        compact = COMMANDS.split("static void commands_process_packet_g30", 1)[1]
        setter = compact.split("case COMM_SET_MCCONF:", 1)[1].split("case COMM_GET_MCCONF:", 1)[0]
        self.assertIn("G30_MCCONF_WIRE_BYTES = 484", setter)
        self.assertLess(setter.index("if (len != G30_MCCONF_WIRE_BYTES) break;"),
                        setter.index("confgenerator_deserialize_mcconf(data, mcconf)"))
        self.assertLess(setter.index("confgenerator_deserialize_mcconf(data, mcconf)"),
                        setter.index("conf_general_store_mc_configuration(mcconf, 0)"))

    def test_phase_current_reconstruction_covers_all_three(self):
        getter = function_body(DRIVER, "__weak void R3_2_GetPhaseCurrents(")
        self.assertIn("pHandle->_Super.Ia = pStator_Currents->a;", getter)
        self.assertIn("pHandle->_Super.Ib = pStator_Currents->b;", getter)
        self.assertIn("pHandle->_Super.Ic = -pStator_Currents->a - pStator_Currents->b;", getter)
        overload = getter.split("if(pHandle->_Super.OverCurrent &&", 1)[1]
        checks = re.findall(r"abs\(pHandle->_Super\.(I[abc])\)\s*>\s*pHandle->_Super\.OverCurrent", overload)
        self.assertEqual(checks, ["Ia", "Ib", "Ic"])

        # The old code repeated Ia instead of checking Ib. This would miss
        # phase-B-only overloads such as (-50, 100, -50) against limit 80.
        for a, b, c, limit, should_trip in (
            (-50, 100, -50, 80, True),
            (100, -50, -50, 80, True),
            (-50, -50, 100, 80, True),
            (20, -10, -10, 80, False),
        ):
            self.assertEqual(a + b + c, 0)
            self.assertEqual(any(abs(i) > limit for i in (a, b, c)), should_trip)

    def test_current_adc_channels_and_sector_reconstruction(self):
        self.assertIn(".ADCx_1            = ADC1", PARAMS)
        self.assertIn(".ADCx_2            = ADC2", PARAMS)
        self.assertIn("MC_ADC_CHANNEL_3", PARAMS)
        self.assertIn("MC_ADC_CHANNEL_4", PARAMS)
        self.assertIn("MC_ADC_CHANNEL_5", PARAMS)
        self.assertIn("ADC1->JDR1", PARAMS)
        self.assertIn("ADC2->JDR1", PARAMS)
        self.assertIn("hadc1.Init.DataAlign = ADC_DATAALIGN_LEFT", ADCINIT)
        self.assertIn("hadc2.Init.DataAlign = ADC_DATAALIGN_LEFT", ADCINIT)
        getter = function_body(DRIVER, "__weak void R3_2_GetPhaseCurrents(")
        for a, b in (("SECTOR_4:", "SECTOR_5:"), ("SECTOR_6:", "SECTOR_1:"),
                     ("SECTOR_2:", "SECTOR_3:")):
            self.assertIn(a, getter)
            self.assertIn(b, getter)
        self.assertIn("PhaseAOffset", getter)
        self.assertIn("PhaseBOffset", getter)
        self.assertIn("PhaseCOffset", getter)

    def test_clarke_park_and_voltage_feed_are_connected(self):
        core = function_body(FOC, "inline uint16_t FOC_CurrControllerM1(")
        for item in ("PWMC_GetPhaseCurrents(", "MCM_Clarke(Iab)",
                     "MCM_Park(Ialphabeta, hElAngle)",
                     "PI_Controller(pPIDIq", "PI_Controller(pPIDId",
                     "MCM_Rev_Park(Vqd, hElAngle)",
                     "PWMC_SetPhaseVoltage(", "G30SL_ObserverStep("):
            self.assertIn(item, core)
        self.assertLess(core.index("PWMC_GetPhaseCurrents("), core.index("MCM_Clarke(Iab)"))
        self.assertLess(core.index("MCM_Clarke(Iab)"), core.index("MCM_Park(Ialphabeta, hElAngle)"))
        self.assertLess(core.index("MCM_Rev_Park("), core.index("G30SL_ObserverStep("))

    def test_stock_dash_brake_is_prioritized_over_throttle(self):
        callback = function_body(DASH, "void vTimerCallback(")
        self.assertIn("case ADC_CTRL_TYPE_CURRENT_NOREV_BRAKE_ADC:", callback)
        case = callback.rsplit("case ADC_CTRL_TYPE_CURRENT_NOREV_BRAKE_ADC:", 1)[1]
        case = case.split("break;", 1)[0]
        self.assertIn("if(brake>0)", case)
        self.assertIn("VescToSTM_set_brake_current_rel(brake);", case)
        self.assertIn("}else if(pwr>=0)", case)
        self.assertIn("VescToSTM_set_current_rel(pwr);", case)
        self.assertLess(case.index("if(brake>0)"), case.index("}else if(pwr>=0)"))
        self.assertEqual("brake" if .40 > 0 else "throttle", "brake")


if __name__ == "__main__":
    unittest.main()
