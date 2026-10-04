# G30 sensored hardware-test candidate v0.1

Branch: `candidate/g30-sensored-hwtest-v0.1`

Status: **UNVALIDATED ON REAL G30 POWER HARDWARE**

This branch is a deliberately conservative first motor-control validation target. It is not a release and it must not be treated as proof that DeltaESC/SmartESC is safe for normal riding.

## Scope

Enabled:
- stock G30 STM32F103C8T6 controller target (`g30p`)
- Hall-sensored FOC only
- stock STAR motor topology only
- stock three-shunt phase-current measurement
- stock dashboard path
- stock BMS support
- true coast
- motor cut on brake
- SHU/IAP recovery support retained

Disabled for first validation:
- automatic STAR/DELTA switching
- forced DELTA setup
- sensorless observer as rotor-position source
- HFI
- automatic R/L/flux/Hall motor-detection task
- regenerative braking
- field weakening by default

Hard bring-up current limits:
- phase current: +/-12 A
- battery current: +/-8 A
- absolute phase-current fault: 15 A

## Hardware audit

The G30 schematic was checked against the firmware target.

Relevant mappings:
- Hall A: PB4
- Hall B: PB5
- Hall C: PB0
- phase-current ADC inputs: PA3 / PA4 / PA5
- bridge high-side PWM: PA8 / PA9 / PA10
- bridge low-side PWM: PB13 / PB14 / PB15
- battery voltage: ADC channel 1

The controller uses three 2 mOhm phase shunts and real three-shunt current sensing.

The original SmartESC `g30p.wb_def` specifies **15 pole pairs**. The shared
`product.h` / setup default had drifted to 14, which skews mechanical speed and
odometer conversion. v0.1 pins the live G30 configuration to 15 pole pairs and
rejects a different pole-pair setting during bring-up.

The schematic's nominal current-amplifier resistor ratio is 1 + 24k/3k = 9.0.
Upstream SmartESC uses `AMPLIFICATION_GAIN = 9.4336`. v0.1 deliberately keeps
9.4336 because it may be an empirical calibration. The value must be verified
against a controlled real-current measurement before normal-current operation.

## Incorporated fixes

### 1. G30 SRAM margin

The previous sensored candidate linked at:
- text: 42,900 B
- data: 1,364 B
- bss: 19,072 B
- data + bss: 20,436 B

On a 20 KiB STM32F103 RAM target that leaves only 44 bytes of static link margin.

Several independent SmartESC forks reduced the G30/RTOS heap to 13 KiB. v0.1
does the same, adding 1 KiB static margin while G30 scope capture and automatic
motor detection are disabled.

### 2. Hall-angle re-sync after true coast

SmartESC can switch PWM off while coasting. During that interval the
high-frequency FOC task no longer advances the interpolated electrical angle.

Before PWM is enabled again, v0.1:
- reads `MeasuredElAngle` once
- copies it to `hElAngle`
- copies the same sample to `CompAngle`
- preserves the live Hall speed state while the wheel is moving
- clears compensation/speed state only at actual standstill

This prevents restarting FOC from a stale electrical angle after a coast period.

### 3. Battery-current limiter scale

The ST Clarke/Park path is amplitude invariant, so with Id approximately zero:

`P = 3/2 * Vq * Iq`

The legacy limiter used 32768 as its conversion divisor. The corrected q-axis
conversion uses:

`65536 / 1.5 = 43690.7 -> 43691`

The legacy scale overestimated battery current by 4/3 and therefore could begin
limiting at about 75% of the configured battery-current limit.

The correction is gated to the G30 sensored bring-up path in this candidate.

### 4. FOC current-PI domain conversion

SmartESC stores the detected/configured current gains in SI units while the ST
current regulator consumes ADC-current-count to s16-voltage-count gains.

v0.1 applies:

`gain_scale = 65536 / (Vbus_nominal * CURRENT_FACTOR_A)`

before loading the ST PI registers.

With the stock G30 constants the scale is approximately 4.86. As a useful
cross-check, the default SmartESC `foc_current_kp = 0.09` then produces an ST
Kp of about 448 counts, close to the original generated
`PID_TORQUE_KP_DEFAULT = 500`. The unscaled path gives only about 92.

The correction is G30-bring-up-only in v0.1.

### 5. APP_ADC fall-through

The `APP_ADC` switch case previously fell through into `APP_ADC_UART`.
During a live configuration change this could kill the newly started ADC/display
task and replace it with the CLI task on the shared UART. v0.1 adds the missing
`break`.

### 6. Drive-mode current-scale persistence

SmartESC resets the runtime `lo_current_max_scale` to 1.0 while applying a motor
configuration. v0.1 immediately restores the current scale for the selected
ECO/Drive/Sport dashboard mode, so a configuration write cannot silently turn a
reduced-current mode into full-current behavior.

### 7. STAR-only runtime interlocks

In addition to disabling the relay state machine, v0.1 makes
`g30_config_auto_delta_enabled()` return false during sensored bring-up and
rejects any attempt to apply a DELTA runtime profile. The runtime-profile PI path
uses the same corrected SI-to-ST-count gain conversion as the normal setup path.

## First hardware-validation sequence

Use ST-Link/SWD recovery and keep a verified full 128 KiB flash backup.

1. Power controller with motor unloaded / wheel off the ground.
2. Confirm no unexpected motor movement at boot.
3. Confirm dashboard and BMS communication.
4. Rotate wheel by hand and verify only six legal Hall states occur.
5. Confirm reported phase current is near zero with PWM off.
6. Apply the smallest practical throttle command.
7. Verify correct rotation without reverse kick, harsh cogging or sustained buzz.
8. Increase only through low unloaded speeds.
9. Test throttle release into true coast.
10. Re-apply light throttle while wheel is still moving and verify smooth Hall re-sync.
11. Compare reported battery/phase current with an independent current measurement.
12. Stop immediately on abnormal current, repeated Hall fault, unexpected braking,
    reverse torque, MOSFET heating, or current-sense disagreement.

Do not enable DELTA, regen, field weakening or automatic motor detection during
this validation stage.

## Pass criteria for v0.1

The branch may only be promoted beyond "unvalidated" after a real G30 controller
demonstrates:
- repeatable standstill start in the intended direction
- stable Hall-FOC at low and moderate unloaded speed
- clean coast and clean torque re-engagement
- believable current scaling
- no unexplained FOC/Hall/overcurrent faults
- controlled stop/cut behavior

A successful CI build is necessary but is **not** hardware validation.
