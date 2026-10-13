# G30D real-hardware evidence integration v2 — 2026-10-14

Status: **UNVALIDATED / GATE OFF / NOT FOR RIDING OR MOTOR POWER TEST**.

This branch combines the already transferred real-hardware evidence from
`integration/g30-realhw-evidence-2026-10-13` with the isolated DRV126 TIM1/current-path
experiment from `experiment/g30-drv126-tim1-profile-2026-10-13`.

## Owner-supplied stock reference

- file: `esc126_fulldump.bin`
- size: 131072 bytes
- SHA-256: `9235b466a2f7449b8184560dbef9012d7c12b099e4076100a223ef68d204bb68`
- stock application vector at `0x08001000`
- application reset handler `0x08001101`

Independent re-check on the supplied dump confirms:
- TIM1 base `0x40012C00`
- center-aligned mode value `0x20` is prepared for TIM1
- ARR `4000` is prepared and written to TIM1 ARR
- runtime current-path code writes sector-dependent single-rank JSQR selections to
  ADC1 `0x40012438` and ADC2 `0x40012838`
- static stock CKD cannot be proven safely from the binary alone, so CKD=DIV1 remains
  an explicit diagnostic hypothesis rather than a claimed stock fact

## Integrated diagnostic changes

- G30-only DRV126 timing profile: 8 kHz nominal / ARR 4000 at the current 64 MHz assumption
- DTG `0x40`
- AOE deliberately remains OFF
- STAR/DELTA relay disabled and fixed STAR
- all six PWM pins configured GPIO output LOW instead of TIM1 alternate-function outputs
- both MCSDK motor-enable paths explicitly force TIM1 MOE off
- concrete MCSDK overcurrent bug fixed: Ia/Ib/Ic are each checked once
- M365 compile regression remains part of the dedicated CI
- stock 50 KiB executable window and pages 54/55 DeltaESC config separation retained
- existing 15 pole-pair G30 correction retained

## Deliberately not integrated

The EBiCS/standalone observer and sensorless state machine are not copied into the
SmartESC-derived MCSDK control architecture. The latest EBiCS timing/ADC findings remain
reference evidence only until the Hall-FOC/current-feedback chain here is measured.

## Gate to the next step

Do not enable TIM1 alternate-function gate outputs yet. The next useful evidence is a
read-only stock SWD capture of RCC/TIM1/ADC registers, followed by the same register capture
on this GATE_OFF build. Only after those values are reconciled should the power stage be
considered for a controlled motor test.
