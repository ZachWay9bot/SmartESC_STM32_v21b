# DeltaESC Config (Android)

Companion app for the compact G30D DeltaESC SHU build.

**DeltaESC is based heavily on SmartESC by Koxx3:**
https://github.com/Koxx3/SmartESC_STM32_v2

It does **not** emulate SHFW and does not depend on SHU's SHFW-only configuration UI. The app talks to DeltaESC through a small private `0x7D` command set carried over the stock G30 BLE/dashboard link.

## Current functions

- connect to stock G30 BLE/Nordic-UART service
- legacy Ninebot encrypted session support for the G30 BLE110/113/114 family
- plain/legacy fallback for unlocked dashboards
- live speed, bus voltage, Iq, battery input current, SOC, BMS status and STAR/DELTA state
- read/apply/save common current and STAR/DELTA settings
- separate STAR and DELTA R/L/flux/current profiles
- STAR motor detection
- DELTA motor detection after a PWM-off relay change
- setup progress/error display
- RAM-first editing; flash is written only with **SAVE FLASH**

## Safety behavior

The ESC, not the phone, enforces the important rules. Critical writes and setup are accepted only at standstill. Motor detection disables normal throttle control, waits for low Iq, disables PWM before changing topology, and always returns the relay output to STAR when setup ends.

The wheel must be free in the air for motor detection.

## Protocol

Ninebot transport frame:

```
5A A5 LEN SRC DST CMD ARG payload... CK_LO CK_HI
```

DeltaESC Config uses `CMD=0x7D`, phone/app source `0x3E`, ESC destination `0x20`.

The protocol is intentionally independent from SHFW so firmware updates can still be handled by ScooterHacking Utility while this app handles DeltaESC setup and telemetry.

## Build

```
gradle :app:assembleDebug
```

The GitHub Actions workflow `Build DeltaESC Config APK` uploads the debug APK as an artifact.
