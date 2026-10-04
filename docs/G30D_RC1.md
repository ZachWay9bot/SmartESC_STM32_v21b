# DeltaESC G30D v0.3 RC1

This branch is the first release-candidate hardening pass built from the frozen
G30 Gen1 hardware-fix revision `dca30bcbe48d2b3aec9ec3301c1b9abd39783373`.

> **Hardware status:** software/build release candidate, not yet road validated.
> Keep ST-Link/SWD recovery available and preserve a verified full 128 KiB flash
> backup until the complete motor and rollback test matrix has passed.

## RC1 invariants

- G30 Gen1 power button: PA12, input pull-up, active-low.
- Power hold: PA11.
- STAR/DELTA interface: PA15, low = STAR, high = DELTA request.
- PB9 is not used for STAR/DELTA.
- Boot topology is STAR.
- Automatic STAR/DELTA starts disabled and is only allowed after valid STAR and
  DELTA electrical profiles exist.
- G30 motor control remains Hall-sensored only.
- Stock dashboard remains on PA2 / USART2 half-duplex.
- Stock BMS remains on PB10/PB11 / USART3.
- Throttle release is true coast. Brake requests motor cut/coast; regenerative
  braking is disabled in this G30 build.
- Stock 4 KiB IAP bootloader is preserved. The application is linked at
  0x08001000 with a 52 KiB maximum image region.

## RC1 hardening

RC1 additionally fixes two inherited paths that were not covered by v0.3:

1. Automatic SHU/IAP handoff now forces STAR using PA15 before PWM is disabled
   and the application vector is invalidated.
2. G30 shutdown no longer waits for an active-low PA12 button press before
   dropping PA11. Inactivity shutdown now deasserts the power-hold line
   immediately.

The source preflight asserts these mappings and also rejects regression to the
old PB9 recovery output. CI must build both G30P and the M365 regression target,
run the SHU packaging tests, and build/test the Android companion app.

## Hardware validation gate

Perform the first test with the driven wheel clear of the ground and the
STAR/DELTA hardware physically held in STAR.

1. Verify the full 128 KiB stock backup can be read back and compared.
2. Flash RC1 while keeping SWD recovery available.
3. Verify stable boot, PA11 power hold, PA12 short/long press behavior, dashboard
   communication, and BMS telemetry before commanding motor torque.
4. Verify all three Hall states/sequences and correct wheel direction at very
   low current.
5. Verify throttle release produces coast and the brake input does not request
   regenerative torque.
6. Run STAR motor detection and review R/L/flux/Hall results before saving.
7. Only after STAR operation is stable, connect/enable the external PA15
   STAR/DELTA interface and perform DELTA detection with the wheel unloaded.
8. Validate SHU rollback/recovery while stationary before any road test.
9. Enable automatic STAR/DELTA only after both profiles and the relay transition
   have been verified on hardware.

Do not raise current limits or enable field weakening during the initial RC
validation. The purpose of RC1 is to prove the hardware mapping, control path,
configuration path, and recovery path before performance tuning.

## CI release gate

The RC is publishable only when the G30P build, M365 regression build, SHU
preflight/package validation, and Android protocol tests/APK build all pass from
the same source revision.
