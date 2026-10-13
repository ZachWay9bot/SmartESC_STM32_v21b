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

# Source profile: only G30 changes. M365 keeps 16 kHz.
need(re.search(r"#if defined\\(G30P\\) && G30_DRV126_TIMING_PROFILE\\s+.*?#define PWM_FREQUENCY\\s+8000\\s+#else\\s+#define PWM_FREQUENCY\\s+16000", drive, re.S), "G30/M365 frequencies")
need("#define G30_DRV126_TIMING_PROFILE" in product and re.search(r"#define G30_DRV126_TIMING_PROFILE\\s+1", product), "profile enabled")
need(re.search(r"#define G30_DRV126_DIAG_GATE_OFF\\s+1", product), "diagnostic gate-off enabled")
need(re.search(r"#define DELTA_RELAY_ENABLE\\s+0", product), "relay must not switch during GATE_OFF tests")
need("PWM_PERIOD_CYCLES" in conv and "PWM_FREQUENCY" in conv, "MCSDK PWM/ADC timing integration")
need(re.search(r"#define ADV_TIM_CLK_MHz\\s+64", f10), "64 MHz timer clock assumption")
# Center-aligned TIM1: ARR=64 MHz/(2*8000)=4000.
need((64_000_000 // (2 * 8_000)) == 4000, "DRV126 ARR mismatch")
need("htim1.Init.Period = ((PWM_PERIOD_CYCLES) / 2);" in main, "ARR must use MCSDK timebase")
need(re.search(r"#if defined\\(G30P\\) && G30_DRV126_TIMING_PROFILE\\s+.*?TIM_CLOCKDIVISION_DIV1",main,re.S), "TIM1 CKD=1x profile")
need(re.search(r"#if defined\\(G30P\\) && G30_DRV126_TIMING_PROFILE\\s+.*?sBreakDeadTimeConfig.DeadTime = 0x40",main,re.S), "DTG=0x40 profile")
need("TIM_AUTOMATICOUTPUT_DISABLE" in main, "AOE must remain explicitly inhibited in experiment")
# CKD=00 and DTG=0x40 give 64/64 MHz = 1 us nominal deadtime.
need((64 * 1_000_000_000 // 64_000_000) == 1000, "deadtime mismatch")

# Prevent the six TIM1 outputs from being driven via alternate functions:
need(msp.count("G30_DRV126_DIAG_GATE_OFF") == 2, "both PWM GPIO ports require gate-off")
need(msp.count("GPIO_MODE_OUTPUT_PP;") >= 2, "PWM gate-off must actively drive low")
need("HAL_GPIO_WritePin(GPIOA, M1_PWM_UH_Pin|M1_PWM_VH_Pin|M1_PWM_WH_Pin, GPIO_PIN_RESET)" in msp, "high-side gates low")
need("HAL_GPIO_WritePin(GPIOB, M1_PWM_UL_Pin|M1_PWM_VL_Pin|M1_PWM_WL_Pin, GPIO_PIN_RESET)" in msp, "low-side gates low")
need("ORIGIN = 0x08001000,   LENGTH = 50K" in link, "stock bootloader / config separation")
print("PASS: G30 DRV126 TIM1 source profile is self-consistent and GATE_OFF in this build")
print("NOT VERIFIED: live RCC/TIM1 CKD, ADC windows, gate-driver polarity, Hall mapping, motor run")
