# G30D cross-project hardware evidence transfer — 2026-10-13

Status: **development evidence only; motor operation remains unvalidated**.

This note records the hardware facts being transferred into the SmartESC-derived
DeltaESC tree from the newer standalone `ZachWay9bot/DeltaESC-G30D` bring-up,
the EBiCS experiments and the owner's original DRV126 full flash.

## Exact stock reference

Owner-supplied full flash:

- file: `esc126_fulldump.bin`
- size: 131072 bytes
- SHA-256: `9235b466a2f7449b8184560dbef9012d7c12b099e4076100a223ef68d204bb68`
- Cortex-M vector table starts at stock flash base; stock application vector is
  present at `0x08001000`.

This is the same stock dump used by the DRV126 TIM1 GATE_OFF experiment in PR #11.

## Findings safe to transfer now

1. **Stock G30 BLE/dashboard transport is real and proven on hardware.**
   Legacy NinebotCrypto and the App -> BLE/dashboard -> ESC read route work on
   the physical G30D. Keep native G30 `5A A5` framing as the transport reference.

2. **G30 stock motor default is 15 pole pairs / 30 poles.**
   The current candidate already carries this correction through the hardware
   audit merged in PR #10.

3. **Do not trust the inherited ESC local power-button pin.**
   Real SWD measurements did not show a pressed/released transition on the
   inherited PC14 input or the earlier PA12 hypothesis. The dashboard has its
   own physical button wiring. Therefore G30 code must not trigger mode changes
   or destructive recovery from either unproven ESC GPIO.

4. **DRV126 timing is a reference, not permission to energize gates.**
   Static analysis of the exact stock dump recovered TIM1 ARR=4000,
   center-aligned operation and initial BDTR DTG=0x40 with AOE set in stock.
   Exact CKD/current-sample timing still needs physical validation. PR #11 keeps
   this work GATE_OFF and intentionally does not claim motor readiness.

5. **The stock current path is dual-ADC / sector dependent.**
   The original DRV126 initializes ADC1 injected CH3 and ADC2 injected CH5;
   SmartESC's MCSDK later changes injected channel selection by sector and reads
   JDR1. The old assumption that the generated three-rank init alone proves the
   runtime current path broken is rejected.

## Findings that are NOT blindly ported

- The standalone sensorless observer/state machine is a different motor-control
  architecture. Its EBiCS/VESC observer, motor-ID and MOE-latched-stop work are
  useful references, not drop-in SmartESC MCSDK patches.
- PA12 and PC14 are not promoted as a confirmed G30 power-button input.
- Stock AOE=1 is not copied into an experimental controller before the shutdown
  and protection chain has been electrically verified.
- No sensorless/hybrid mode is enabled in this SmartESC-derived candidate.
- No real-motor or road-use validation is claimed by a green CI build.

## Source-of-truth split

For continued work:

- **SmartESC-derived tree:** stock dashboard/BMS integration, Android companion,
  SHU packaging/recovery research, Hall-FOC compatibility work.
- **Standalone DeltaESC-G30D tree:** newer ADC/FOC/observer/motor-ID research and
  fail-closed motor-core experiments.
- **DRV126 full dump:** final reference for stock peripheral behavior where the
  source trees disagree.

The frozen branches remain untouched.
