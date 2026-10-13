# G30D Gen1 DRV126 timing comparison: experimental GATE_OFF build
Status: **UNVALIDATED / NOT FOR RIDING OR MOTOR POWER TEST**. 2026-10-13.

This branch starts at `candidate/g30-config-app-v0.2` commit
`48db9896a96b308923e22e9af123a8b02cfcd365`.
The freeze branches, stock DRV126, and EBiCS are not modified.

## Original binary reference (supplied by owner, not committed)

- SHA-256: `9235b466a2f7449b8184560dbef9012d7c12b099e4076100a223ef68d204bb68`
- Stock app reset handler 0x08001101; entry vectors at 0x08001000
- At 0x080048bc: 0x0FA0 (=4000) prepared for TIM1 ARR, written by routine 0x08006580 at 0x080065c6 to TIM1+0x2c
- Stock TIM1 center-aligned mode: CR1.CMS=01 from 0x080048b8 (0x20).
- Stock BDTR: 0x4D40 (DTG 0x40, LOCK1, OSSI, OSSR, AOE1, BKE0; MOE initially 0)
- Stock PWM GPIO group PA8/9/10, PB13/14/15
- Stock dashboard USART2 PA2 AF open-drain; Stock PC14 read
- Stock TIM1 CKD is **not conclusively recovered from this binary**. The source profile's CKD=DIV1 is a test hypothesis, not confirmed parity.

## Experimental source changes (only G30P)

| Parameter | Prior candidate | This experiment | Stock evidence |
|---|---|---|---|
| FOC/PWM reference rate | 16 kHz | 8 kHz | ARR 4000 and center alignment; assumes TIM1=64 MHz |
| TIM1 ARR | 2000 | 4000 | 4000 |
| TIM1 CKD | DIV2 | DIV1 | Unknown |
| BDTR DTG | 0x19 | 0x40 | 0x40 |
| Nominal deadtime @ 64 MHz | 781.25 ns | 1000 ns | DTG known, CKD not verified |
| BDTR AOE | 0 | 0 | 1 |
| TIM1 Break BKE | 0 | 0 | 0 |
| Physical gate GPIOs | TIM1 AF push-pull | GPIO output push-pull LOW on all six lines | Intended power outputs disabled |
| Delta relay | Enabled | Disabled; kept in STAR position | No relay actuation during diagnostics |

`PWM_FREQUENCY` is changed *within the ST motor-control parameter family*, rather than hardcoding ARR alone. This propagates the frequency change to regulation rates, trigger calculations, current-sensing timing, and speed-loop constants. It does not prove the resulting sampling window or control gains are correct.

In the diagnostic build, the six PWM pins are explicitly written LOW and initialized as ordinary GPIO output pins in `HAL_TIM_MspPostInit`. Timer MOE no longer routes to these pins **by that initializer**. This is source-level protection, not an electrically verified gate-driver inhibit. No live motor, drivetrain, or high-voltage testing should use this build until the pin-level logic has been inspected.

AOE intentionally stays OFF because enabling automatic reassertion of MOE before characterizing protections is unjustified. We are **not** claiming register-for-register stock equivalence.

## CI and tests

`python3 tools/test_drv126_tim1_profile.py` checks parameter propagation, static pin inhibit, and stock flash window. The GitHub workflow builds the G30 target and, if it succeeds, uploads a diagnostic-only BIN and SHU ZIPv3. These are not released motor firmware images. No changes to M365 target.

## First physical verification needed (before any powered motor test)

Use ST-Link and stock DRV126 with scooter powered normally and wheel off ground to capture:
- `TIM1_CR1` @ `0x40012C00` (especially CKD, CMS, CEN)
- `TIM1_ARR` @ `0x40012C2C`
- `TIM1_RCR` @ `0x40012C30`
- `TIM1_CCR4` @ `0x40012C40`
- `TIM1_BDTR` @ `0x40012C44` (especially MOE, DTG, AOE)
- `ADC1_JSQR` @ `0x40012438`, `ADC2_JSQR` @ `0x40012838`; injected trigger bits in ADCx_CR2 @ base+0x08
- `RCC_CFGR` @ `0x40021004` and `RCC_CFGR2` if available (STM32F1 variant dependent)

For a **GATE_OFF image** inspect PA8/PA9/PA10/PB13/PB14/PB15 GPIO configurations in CRH and check each pin LOW electrically. Do not issue start motor commands.

## Why this does not finish DeltaESC

The SmartESC v2 upstream requires Hall sensors; it is **not sensorless**. Firmware compilation and SHU packaging are not a motor-spin proof. The functional ADC/current reconstruction, Hall-to-phase relation, hardware gate-driver polarity and motor behavior remain to be checked with physical readings. Stock BLE/NinebotCrypto compatibility also remains separate.
