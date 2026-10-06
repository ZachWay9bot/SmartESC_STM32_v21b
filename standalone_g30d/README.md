# Clean standalone G30D line

> [!CAUTION]
> **UNVALIDATED HARDWARE BRING-UP.** This branch is not for blind installation or road use. The first binary keeps the power stage physically disarmed.

This directory imports the clean no-SmartESC STM32F103 work from the parallel development chat and keeps it separate from the older SmartESC-derived DeltaESC line.

Current package: **v0.4.1 PWM/ADC sync bring-up**.

Important corrections included in v0.4.1:
- USART1 debug is explicitly remapped to PB6/PB7. PA9/PA10 remain reserved for TIM1 motor PWM.
- the active-capable zero-vector build refuses to arm unless the latest ADC trigger interval matches the expected 16 kHz cadence.
- the executable remains linked at 0x08001000 and capped to 50 KiB, preserving the stock bootloader and upper stock flash regions observed in the real 128 KiB DRV 1.2.6 full dump.
- the supplied full dump is **not** committed.

The source package contains:
- minimal STM32F103 register layer
- TIM1 complementary PWM setup with dead-time
- TIM1 CH4 synchronized ADC injected conversions
- PA3/PA4/PA5 phase-current acquisition and PA1 bus sense
- fixed-point observer/current-control/SVPWM timing path
- DWT timing diagnostics
- sync-safe and active-capable zero-vector variants
- preflight checks and bench checklist

The observer/current-control output is **not connected to bridge CCRs** in v0.4.1. No rotating vector is commanded.

Source archive: `DeltaESC_G30D_clean_v0_4_1_SOURCE.zip`
