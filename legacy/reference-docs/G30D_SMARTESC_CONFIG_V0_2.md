# G30D SmartESC Config v0.2

Status: **current hardware-test candidate**

## Pinned candidate

```
branch: candidate/g30-config-app-v0.2
commit: f7c22f4859ef28fa3ce29499b5d79cd8aa3267df
```

PR:

https://github.com/ZachWay9bot/SmartESC_STM32_v21b/pull/3

The candidate branch is intentionally pinned to the CI-tested commit above.
Later development belongs on `feature/g30-config-app`.

## What v0.2 contains

### Core G30D behavior

- stock G30 dashboard on PA2 / USART2 half-duplex
- throttle, speed and Eco / Drive / Sport
- brake input = motor cut
- no regenerative braking
- true coast after throttle release
- Hall-sensored FOC
- stock BMS communication on USART3 PB10/PB11
- BMS activator heartbeat plus read-only telemetry
- dashboard battery percentage from BMS SOC when valid
- stock 4 KiB Ninebot IAP bootloader preserved
- SHU-compatible ZIPv3 package with plain + NinebotTEA-encrypted firmware
- stationary handoff to the preserved stock IAP bootloader for SHU update/revert

### Automatic STAR / DELTA

The former rear-light output is used for an external STAR/DELTA relay driver.

Configurable values:

- DELTA entry speed
- STAR return speed
- maximum |Iq| allowed before changing topology
- relay contact-settle time

The switch sequence is:

```
requested torque -> 0
wait for low |Iq|
PWM OFF
wait 20 ms
switch relay
load matching STAR/DELTA electrical profile
clear Id/Iq controller integrators
wait relay-settle time
allow normal throttle ramp again
```

The relay-deenergized fail-safe state is STAR.

The MCU output must drive an external MOSFET/transistor/opto driver. Relay coils
must not be driven directly from the controller GPIO.

## Why there is a dedicated Android app

The compact SHU image is limited to the stock 52 KiB application window.
The full VESC Tool communications stack is therefore intentionally disabled via
`SESC_SHU_LITE`.

ScooterHacking Utility also exposes its configuration UI only for SHFW.

v0.2 solves both problems with a separate **SmartESC Config** Android app.
SHU remains responsible for firmware flashing/recovery. SmartESC Config handles
motor setup, current limits, persistent settings and telemetry.

Android source:

https://github.com/ZachWay9bot/SmartESC_STM32_v21b/tree/candidate/g30-config-app-v0.2/android/SmartESCConfig

## SmartESC Config protocol

The companion protocol is deliberately independent from SHFW.

Private SmartESC command:

```
CMD = 0x7D
```

It is transported through the normal stock G30 BLE/dashboard path.

Functions include:

- HELLO / protocol version
- live telemetry
- GET/SET common configuration
- GET/SET STAR profile
- GET/SET DELTA profile
- SAVE FLASH
- START motor detection
- detection status/progress

Critical writes and detection commands are accepted only while the scooter is
stationary.

## Android BLE path

The app uses the stock Nordic-UART BLE service and implements the legacy
NinebotCrypto 5B/5C/5D authentication used by the relevant G30 dashboard/BLE
lineage.

The initial checksum-free inner Ninebot frame is:

```
5A A5 00 3E 21 5B 00
```

Known-vector regression test:

```
plain:
5A A5 00 3E 21 5B 00

encrypted:
5A A5 00 A1 61 6A 44 00 00 45 FF 00 00
```

The Android CI runs this vector before building the APK.

## Motor setup

The setup order is intentionally fixed.

### 1. Detect STAR

The scooter must be stationary and the drive wheel must be free in the air.

The firmware:

1. disables normal throttle output
2. commands zero torque
3. waits for low Iq
4. ensures STAR topology
5. measures motor resistance R
6. measures motor inductance L
7. calculates controller gains from measured R/L
8. runs a controlled open-loop spin for flux-linkage measurement
9. performs Hall detection
10. stores the resulting STAR profile in RAM

STAR profile:

```
R_star
L_star
Flux_star
phase_current_star
Kp_star
Ki_star
Hall table
```

### 2. Detect DELTA

DELTA detection is rejected until a valid STAR profile exists.

The firmware:

1. commands zero torque
2. waits for low Iq
3. disables PWM
4. changes the relay to DELTA
5. waits for the configured contact-settle time
6. measures R and L again
7. measures DELTA flux linkage
8. performs Hall detection again
9. compares the Hall result with the STAR result
10. rejects a large Hall-angle mismatch as a relay/phase wiring error
11. stores the DELTA profile in RAM
12. returns to STAR on success or failure

DELTA profile:

```
R_delta
L_delta
Flux_delta
phase_current_delta
Kp_delta
Ki_delta
```

### 3. Review current limits

The app exposes at least:

- battery/input current limit
- STAR phase-current limit
- DELTA phase-current limit
- wheel diameter
- motor pole count
- DELTA entry speed
- STAR return speed
- max switch Iq
- relay settle time

Edits use this workflow:

```
READ
  -> edit
  -> APPLY RAM
  -> test
  -> SAVE FLASH
```

Flash is not written continuously while sliders/fields are edited.

## Persistent configuration

STAR and DELTA profile data is stored alongside the compact G30 application
configuration in the SmartESC-owned configuration area.

Automatic STAR/DELTA remains disabled until both STAR and DELTA profiles are
valid.

The runtime topology switch reads profiles from RAM. It does not perform Flash
reads/writes while riding.

## Current CI result

Pinned commit:

```
f7c22f4859ef28fa3ce29499b5d79cd8aa3267df
```

Verified workflows:

- Build G30 SHU candidate #36: SUCCESS
- Build on commit #69: SUCCESS
- Build SmartESC Config APK #23: SUCCESS
- Android protocol/NinebotCrypto unit tests: SUCCESS
- M365 regression build: SUCCESS

G30 firmware:

```
g30p.bin: 48,864 bytes
initial SP: 0x20005000
reset handler: 0x0800B338
build: 0 errors / 0 warnings
```

The image remains inside the stock 52 KiB application window.

## First hardware test order

Do not start with a full-power STAR/DELTA road test.

Before flashing:

1. connect ST-Link
2. save the complete 128 KiB ESC flash
3. verify and preserve that backup
4. keep ST-Link immediately available

Recommended order:

1. flash v0.2 through SHU
2. confirm normal boot and stock dashboard
3. install SmartESC Config APK
4. confirm BLE authentication
5. confirm HELLO and live telemetry
6. confirm BMS online / SOC
7. read configuration
8. test APPLY RAM with a harmless setting
9. test SAVE FLASH and reboot/readback
10. with wheel safely unloaded, run DETECT STAR
11. inspect measured STAR R/L/flux/Hall values
12. only after STAR succeeds, connect/validate the DELTA relay stage
13. run DETECT DELTA unloaded
14. verify return to STAR
15. only then enable automatic STAR/DELTA
16. gradually test current and relay transitions
17. separately verify SHU -> known-good stock/SHFW rollback

## Still requiring real hardware validation

The following are implemented and CI-tested but not yet considered proven on a
real G30D controller:

- custom `0x7D` command forwarding through the actual dashboard/BLE firmware
- Android BLE authentication on the specific installed dashboard firmware
- measured STAR/DELTA parameter quality
- real relay transition under motor load
- BMS behavior above the no-communication current fallback
- complete SHU -> stock/SHFW revert

## Relevant links

- repository: https://github.com/ZachWay9bot/SmartESC_STM32_v21b
- v0.2 candidate: https://github.com/ZachWay9bot/SmartESC_STM32_v21b/tree/candidate/g30-config-app-v0.2
- PR #3: https://github.com/ZachWay9bot/SmartESC_STM32_v21b/pull/3
- Android source: https://github.com/ZachWay9bot/SmartESC_STM32_v21b/tree/candidate/g30-config-app-v0.2/android/SmartESCConfig
- firmware workflow: https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/workflows/build_g30_shu.yml
- Android workflow: https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/workflows/build_config_app.yml

## Previous freeze

The pre-configuration base remains preserved at:

```
freeze/g30-shu-coast-delta-bms-2026-09-30
b4e7bbb38c9738b0f58bdbd1ff28c61c5d0b279e
```

That branch is kept as a reference point and should not be modified.
