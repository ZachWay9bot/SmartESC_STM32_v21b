#!/usr/bin/env python3
"""G30 FOC / dashboard integration contracts, hardware-independent only.

These tests bind known-working interfaces without modifying runtime startup
interlocks or flash/recovery behavior. A passing test does NOT verify measured
phase polarity, calibration, power stage, or the live observer transition.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2] / "common_files/src"
SOURCE = {n: (ROOT / n).read_text() for n in (
    "mc_tasks.c", "mc_config.c", "g30_sensorless.c",
    "g30_sensorless_core.c", "VescToSTM.c", "app_uartcomm.c",
    "VescCommand.c", "tune.c", "conf_general.c"
)}

def func(name, code):
    match = re.search(r"\b" + re.escape(name) + r"\s*\([^;]*?\)\s*\{", code, re.S)
    if not match:
        raise AssertionError("missing function " + name)
    depth, start = 0, match.end() - 1
    for index in range(start, len(code)):
        if code[index] == "{":
            depth += 1
        elif code[index] == "}":
            depth -= 1
            if depth == 0:
                return code[start:index + 1]
    raise AssertionError("unterminated " + name)


class G30FOCIntegration(unittest.TestCase):
    def test_current_path_clarke_park_pi_reverse_park_pwm(self):
        body = func("FOC_CurrControllerM1", SOURCE["mc_tasks.c"])
        ordered = (
            "PWMC_GetPhaseCurrents(",
            "MCM_Clarke(Iab)",
            "MCM_Park(Ialphabeta, hElAngle)",
            "PI_Controller(pPIDIq",
            "PI_Controller(pPIDId",
            "MCM_Rev_Park(Vqd, hElAngle)",
            "PWMC_SetPhaseVoltage(pwmcHandle[M1], Valphabeta)",
            "G30SL_ObserverStep(&G30Sensorless_M1, Ialphabeta, Valphabeta, vbus_mv)",
        )
        offsets = [body.index(x) for x in ordered]
        self.assertEqual(offsets, sorted(offsets))
        pwm = SOURCE["mc_config.c"]
        self.assertIn(".pFctGetPhaseCurrents              = &R3_2_GetPhaseCurrents", pwm)
        self.assertIn(".pFctCurrReadingCalib              = &R3_2_CurrentReadingPolarization", pwm)

    def test_observer_input_units_and_runtime_gate(self):
        sensor = SOURCE["g30_sensorless.c"]
        core = SOURCE["g30_sensorless_core.c"]
        step = func("G30SL_ObserverStep", sensor)
        self.assertIn("!h->active || h->_Super.open_loop || PWM_Handle_M1._Super.PWM_off", step)
        self.assertIn("i_counts_to_ma(i_ab.alpha)", step)
        self.assertIn("i_counts_to_ma(i_ab.beta)", step)
        self.assertIn("v_ab.alpha * (int32_t)vbus_mv) / 32768", step)
        self.assertIn("v_ab.beta * (int32_t)vbus_mv) / 32768", step)
        observer = func("g30sl_core_observer_step", core)
        self.assertIn("s->cfg.r_mohm * i_alpha_ma) / 1000", observer)
        self.assertIn("s->cfg.l_uh * i_alpha_ma) / 1000", observer)
        self.assertIn("s->cfg.observer_hz", observer)

    def test_normal_pwm_start_requires_rolling_lock(self):
        pwm = func("VescToSTM_pwm_start", SOURCE["VescToSTM.c"])
        gate = func("G30SL_PreparePwmStart", SOURCE["g30_sensorless.c"])
        self.assertLess(pwm.index("G30SL_PreparePwmStart("),
                        pwm.index("PWMC_SwitchOnPWM("))
        self.assertIn("if (h->_Super.open_loop) return true;", gate)
        self.assertIn("g30sl_core_roll_ready(&h->core, DWT->CYCCNT)", gate)
        self.assertIn("g30sl_core_seed_observer_from_roll(&h->core, 0, 0)", gate)

    def test_stock_dashboard_brake_priority_and_frame_contract(self):
        uart = SOURCE["app_uartcomm.c"]
        adc = func("app_adc_sample", uart) if "app_adc_sample(" in uart else uart
        self.assertIn("if(brake>0)", adc)
        self.assertIn("VescToSTM_set_brake_current_rel(brake);", adc)
        self.assertIn("else if(pwr>=0)", adc)
        self.assertLess(adc.index("if(brake>0)"), adc.index("else if(pwr>=0)"))
        self.assertIn("frame.cmd == 0x61 || frame.cmd == 0x64 || frame.cmd == 0x65", uart)
        self.assertIn("frame.len >= 3", uart)
        self.assertIn("if(frame.cmd == 0x64)", uart)
        self.assertIn("addCRC((uint8_t*)&m365_to_display", uart)

    def test_detect_all_keeps_rl_flux_and_store_sequence(self):
        detect = SOURCE["VescCommand.c"]
        worker = func("g30_detect_worker", detect)
        for part in ("g30_detect_rl(&r, &l_h)",
                     "g30_detect_flux(r, l_h, &flux)",
                     "cfg->foc_motor_r = r",
                     "cfg->foc_motor_l = l_h",
                     "cfg->foc_motor_flux_linkage = flux",
                     "conf_general_setup_mc(cfg)",
                     "conf_general_store_mc_configuration(cfg, false)"):
            self.assertIn(part, worker)
        self.assertLess(worker.index("g30_detect_rl(&r, &l_h)"),
                        worker.index("g30_detect_flux(r, l_h, &flux)"))
        self.assertLess(worker.index("conf_general_setup_mc(cfg)"),
                        worker.index("conf_general_store_mc_configuration(cfg, false)"))

    def test_no_open_loop_exception_is_added_to_regular_drive(self):
        tune = SOURCE["tune.c"]
        for name in ("tune_foc_measure_resistance", "tune_foc_measure_inductance",
                     "tune_foc_measure_flux_linkage_openloop"):
            self.assertIn("VescToSTM_set_open_loop(true, 0, 0)", func(name, tune))


if __name__ == "__main__":
    unittest.main()
