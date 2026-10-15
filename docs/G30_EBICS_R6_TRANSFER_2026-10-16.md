# G30D EBiCS r6 evidence transfer — 2026-10-16

Status: **UNVALIDATED / GATE OFF / READ-ONLY DIAGNOSTICS**.

This branch applies the useful real-hardware lessons from the EBiCS G30D bring-up
to the SmartESC-derived DeltaESC tree without pretending that the two motor-control
architectures are interchangeable.

## Evidence transferred

- Real G30D Legacy NinebotCrypto 5B/5C/5D is proven on hardware.
- App -> BLE/dashboard -> ESC register reads are proven on hardware.
- PA2 / USART2 uses alternate-function open-drain for the stock yellow-wire link.
- The inherited ESC-local power-button assumptions are not trusted. No destructive
  action is triggered from the unproven PC14/PA12 inputs.
- The owner-supplied DRV126 full dump remains the peripheral reference. The file supplied again on 2026-10-16 was re-hashed locally and is byte-identical to the existing reference:
  `esc126_fulldump.bin`, 131072 bytes,
  SHA-256 `9235b466a2f7449b8184560dbef9012d7c12b099e4076100a223ef68d204bb68`.
- EBiCS r6 demonstrated that ADC/current-processing timing can fail even when the
  communications path is healthy. Its observed fault combination `0x0011`
  and ~257 us worst processing time against a ~172 us budget are treated as a
  warning to measure first, not as values to copy into SmartESC.

## What this branch adds

The existing private DeltaESC config protocol `CMD 0x7D` gains read-only
`ARG 0x20` hardware diagnostics. The payload reports:

- ADC1 injected result JDR1
- ADC2 injected result JDR1
- TIM1 CNT / ARR / CR1 / BDTR / CCER
- current MCSDK fault bits
- ADC1 / ADC2 status registers
- a capability bit indicating that the build is physically GATE_OFF

The Android app displays these values over the already proven NinebotCrypto
transport. When the firmware reports `GATE_OFF`, all configuration writes and
motor-detect buttons stay disabled.

## Safety boundary

This branch does **not** enable the six TIM1 gate outputs. The G30 diagnostic
build keeps the gate pins GPIO LOW and forces TIM1 MOE off in motor-enable paths.

It also does not copy the standalone EBiCS/VESC observer, sensorless state machine
or motor-ID implementation into the SmartESC MCSDK controller. Those remain
reference material until the SmartESC current-feedback and FOC timing are measured
on the real controller.

## Next evidence

Flash only as a recoverable diagnostic build. Capture the new ADC/TIM1 panel at
idle and compare it with the stock DRV126 SWD register capture. The first goal is
to reconcile current-sampling and timer state while the power stage is still
electrically unable to switch.
