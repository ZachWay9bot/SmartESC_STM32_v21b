# SmartESC G30 fork audit — 2026-10-14

Status: **research/audit only**. This document does not validate DeltaESC motor operation.

## Question

Is there a publicly visible SmartESC fork that provides convincing evidence of a working,
hardware-validated Ninebot G30 motor-control implementation which could be used as a known-good base?

## Result

**No convincing known-good G30 SmartESC fork was found.**

Several forks build, change pin definitions, change motor settings, or update CI, but none of the
audited forks currently demonstrates the complete combination needed to call the G30 motor path
validated:

- correct G30 hardware constants and pinout
- stock-compatible flash/application layout
- DRV126-compatible PWM/current-feedback timing
- correct three-phase current protection/reconstruction
- real G30 motor operation evidence
- recoverability / rollback evidence

A green build is not treated as motor-validation evidence.

## Upstream Koxx3/SmartESC_STM32_v2

The G30-related upstream head is commit
`272bdb99d75484dcc377e1cf3e6a20e53a6fd8de` ("fix g30 project", 2022-11-19).

That commit only adds the missing rear/brake-light aliases in `common_files/inc/product.h`.
It fixes a compile problem; it does not repair or validate the G30 PWM/current-feedback path.

Upstream issue #51 ("Help with building the G30 variant?") documents that the G30 target was not
building for a user. The follow-up says the latest commit patched the build, while the Docker build
still failed and STM32CubeMX was required. The issue provides build evidence, not evidence of a
motor running correctly on a G30.

Reference:
- https://github.com/Koxx3/SmartESC_STM32_v2/issues/51

## TheRealBoss/SmartESC_STM32_v2

This is one of the few forks with G30-specific commits after the upstream G30 compile fix.

Head audited:
`df252838ea52975d86c0841a2d82cd14ca1db2f9`.

Compared with upstream G30 commit `272bdb99...`, the substantive changes are limited mainly to:
- `g30p/Inc/main.h`
- `common_files/inc/product.h`
- build workflow / unrelated M365 header changes

Notable changes:
- G30 `PWR_BTN_Pin` moved to PA12.
- The G30 motor definition still uses **14 pole pairs**.

Our stock/hardware evidence currently uses **15 pole pairs / 30 poles** for the G30 motor, and real
SWD tests did not validate PA12 as the ESC-local dashboard power-button input. Therefore these
changes are not a known-good hardware baseline.

The fork also does not fix the concrete shared MCSDK bug where phase A was checked twice and phase B
was skipped in the software overcurrent test, nor does it supply DRV126 PWM/current-path validation.

Conclusion: useful historical fork, **not evidence of a validated G30 motor implementation**.

## Blezz87/SmartESC_STM32_v2

The 2026 commits audited are CI/workflow updates on top of the same upstream G30 source. No
substantive G30 motor-control changes were found.

Conclusion: no known-good G30 motor evidence.

## CamiAlfa/SmartESC_STM32_v2

Default branch remains at the upstream G30 commit `272bdb99...`.

Conclusion: no later G30 motor-control fix or validation.

## Fradpl/SmartESC_STM32_v2

Contains older changes to motor settings, ADC calibration and voltage gain, but its branch diverged
before the later upstream G30 compile-fix history and is substantially behind it.

No G30-specific real-hardware validation was found.

Conclusion: potentially useful historical tuning reference, not a known-good G30 base.

## SmartESC v3 / sensorless branches

TheRealBoss/Koxx3 SmartESC v3 does not present itself as a G30-specific replacement in the audited
tree. It cannot be assumed to be a drop-in G30 solution.

The public `sensorless` branch in SmartESC v2 is shared upstream history rather than evidence of a
later independently validated G30 fork. Previous source review found Hall-dependent paths still
present and no G30 stock-layout/recovery proof.

Conclusion: do not substitute either branch for hardware validation.

## What the stock DRV126 dump changed

The owner's exact 128 KiB stock DRV 1.2.6 full dump is now the stronger hardware reference where
SmartESC forks disagree.

Current recovered evidence includes:
- stock application vector at `0x08001000`
- TIM1 center-aligned setup
- ARR `4000`
- sector-dependent ADC1/ADC2 injected-channel selection
- stock flash/OTA staging boundaries used to keep DeltaESC config out of stock staging space

The exact stock dump SHA-256 is:
`9235b466a2f7449b8184560dbef9012d7c12b099e4076100a223ef68d204bb68`.

## Current DeltaESC decision

Do **not** abandon the SmartESC-derived tree merely because public G30 forks lack validation.
The reusable MCSDK/Hall-FOC framework remains valuable.

Do **not** trust the inherited G30 target merely because it compiles either.

The current development path is therefore:
1. use DRV126 as the hardware source of truth,
2. retain the SmartESC-derived Hall-FOC framework,
3. reconcile timer/current-feedback/pin assumptions against real hardware,
4. keep gates inhibited until the remaining register/electrical facts are measured,
5. only then perform a controlled motor test.

Until that point the G30 motor firmware remains explicitly **UNVALIDATED**.
