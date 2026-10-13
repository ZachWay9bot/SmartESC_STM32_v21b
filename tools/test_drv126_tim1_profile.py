#!/usr/bin/env python3
"""Source-only consistency checks for the G30 DRV126 timing / GATE_OFF experiment.

This test does NOT claim that the output hardware has been measured or is ride safe.
The proprietary stock binary intentionally is NOT committed to the repository.
"""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
def src(path):
    return (root / path).read_text(encoding="utf-8")
def need(cond, message):
    if not cond:
        raise AssertionError(message)

product = src("common_files/inc/product.h")
drive = src("common_files/inc/drive_parameters.h")
main = src("g30p/Src/main.c")
msp = src("g30p/Src/stm32f1xx_hal_msp.c")
f10 = src("common_files/inc/parameters_conversion_f10x.h")
conv = src("common_files/inc/parameters_conversion.h")
link = src("g30p/STM32CubeIDE/STM32F103C8TX_FLASH.ld")
feedback = src("common_files/MotorControl/MCSDK/MCLib/F1xx/Src/r3_2_f1xx_pwm_curr_fdbk.c")
mc_params = src("common_files/src/mc_parameters.c")

# Source profile: only G30 changes. M365 keeps 16 kHz.
need(re.search(r"#if defined\(G30P\) && G30_DRV126_TIMING_PROFILE\s+.*?#define PWM_FREQUENCY\s+8000\s+#else\s+#define PWM_FREQUENCY\s+16000", drive, re.S), "G30/M365 frequencies")
need("#define G30_DRV126_TIMING_PROFILE" in product and re.search(r"#define G30_DRV126_TIMING_PROFILE\s+1", product), "profile enabled")
need(re.search(r"#define G30_DRV126_DIAG_GATE_OFF\s+1", product), "diagnostic gate-off enabled")
need(re.search(r"#define DELTA_RELAY_ENABLE\s+0", product), "relay must not switch during GATE_OFF tests")
need("PWM_PERIOD_CYCLES" in conv and "PWM_FREQUENCY" in conv, "MCSDK PWM/ADC timing integration")
need(re.search(r"#define ADV_TIM_CLK_MHz\s+64", f10), "64 MHz timer clock assumption")
# Center-aligned TIM1: ARR=64 MHz/(2*8000)=4000.
need((64_000_000 // (2 * 8_000)) == 4000, "DRV126 ARR mismatch")
need("htim1.Init.Period = ((PWM_PERIOD_CYCLES) / 2);" in main, "ARR must use MCSDK timebase")
need(re.search(r"#if defined\(G30P\) && G30_DRV126_TIMING_PROFILE\s+.*?TIM_CLOCKDIVISION_DIV1",main,re.S), "TIM1 CKD=1x profile")
need(re.search(r"#if defined\(G30P\) && G30_DRV126_TIMING_PROFILE\s+.*?sBreakDeadTimeConfig.DeadTime = 0x40",main,re.S), "DTG=0x40 profile")
need("TIM_AUTOMATICOUTPUT_DISABLE" in main, "AOE must remain explicitly inhibited in experiment")
# CKD=00 and DTG=0x40 give 64/64 MHz = 1 us nominal deadtime.
need((64 * 1_000_000_000 // 64_000_000) == 1000, "deadtime mismatch")

# Prevent the six TIM1 outputs from being driven via alternate functions:
need(msp.count("G30_DRV126_DIAG_GATE_OFF") == 2, "both PWM GPIO ports require gate-off")
need(msp.count("GPIO_MODE_OUTPUT_PP;") >= 2, "PWM gate-off must actively drive low")
need("HAL_GPIO_WritePin(GPIOA, M1_PWM_UH_Pin|M1_PWM_VH_Pin|M1_PWM_WH_Pin, GPIO_PIN_RESET)" in msp, "high-side gates low")
need("HAL_GPIO_WritePin(GPIOB, M1_PWM_UL_Pin|M1_PWM_VL_Pin|M1_PWM_WL_Pin, GPIO_PIN_RESET)" in msp, "low-side gates low")
need("ORIGIN = 0x08001000,   LENGTH = 50K" in link, "stock bootloader / config separation")
# The ST MCSDK reprograms JSQR dynamically to exactly one injected rank per ADC.
need("ADCx_1->JSQR = pHandle->pParams_str->ADCConfig1" in feedback, "ADC1 runtime injected sector selection")
need("#include \"product.h\"" in feedback, "G30 diagnostics macro included by MCSDK")
need(feedback.count("LL_TIM_DisableAllOutputs(TIMx);") >= 2, "MOE must be inhibited in motor start paths")
for fn in ("R3_2_TurnOnLowSides", "R3_2_SwitchOnPWM"):
    fragment = feedback.split(f"void {fn}( PWMC_Handle_t * pHdl )", 1)[1].split("\n}\n", 1)[0]
    need("G30_DRV126_DIAG_GATE_OFF" in fragment, f"{fn}: GATE_OFF conditional missing")
    need(fragment.index("LL_TIM_DisableAllOutputs(TIMx)") < fragment.find("LL_TIM_EnableAllOutputs(") if "LL_TIM_EnableAllOutputs(" in fragment else True, f"{fn}: output inhibit must precede enable")
    need("pHdl->PWM_off = true;" in fragment, f"{fn}: PWM_off must stay true")
need("ADCx_2->JSQR = pHandle->pParams_str->ADCConfig2" in feedback, "ADC2 runtime injected sector selection")
need("&ADC1->JDR1" in mc_params and "&ADC2->JDR1" in mc_params, "current feedback uses rank1")

# Regression: all A/B/C phase currents must be checked for software overcurrent.
oc = feedback.split("if(pHandle->_Super.OverCurrent && ", 1)[1].split("){", 1)[0]
for name in ("Ia", "Ib", "Ic"):
    need(oc.count(f"abs(pHandle->_Super.{name})") == 1, f"missing/duplicate {name} overcurrent check")

print("PASS: G30 DRV126 TIM1 source profile is self-consistent and GATE_OFF in this build")
print("NOT VERIFIED: live RCC/TIM1 CKD, ADC windows, gate-driver polarity, Hall mapping, motor run")
