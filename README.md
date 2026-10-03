# DeltaESC

**Custom G30D motor-controller firmware.**

> **Based heavily on [SmartESC by Koxx3](https://github.com/Koxx3/SmartESC_STM32_v2).**
> DeltaESC is a heavily modified G30D-focused derivative. Existing upstream
> copyright and license headers in the source are intentionally preserved.


> ## G30D SHU Coast + Delta + Stock BMS — frozen hardware-test candidate
>
> This fork contains a G30D-specific SmartESC build that preserves the stock Ninebot IAP bootloader and is packaged for ScooterHacking Utility (SHU).
>
> **Frozen source:** `freeze/g30-shu-coast-delta-bms-2026-09-30`  
> **Frozen commit:** `b4e7bbb38c9738b0f58bdbd1ff28c61c5d0b279e`
>
> Main G30D changes:
> - stock G30 dashboard remains on PA2 / USART2 half-duplex
> - throttle and Eco / Drive / Sport support
> - brake input = motor cut, no regenerative braking
> - true coast on throttle release
> - automatic STAR/DELTA control on the former rear-light output
> - DELTA at >= 32 km/h, STAR at <= 26 km/h
> - relay change only after low torque/current, PWM off, then 100 ms contact-settle time
> - stock G30 BMS remains on USART3 (PB10/PB11)
> - Ninebot BMS activator heartbeat every 200 ms
> - read-only BMS SOC/current/voltage/temperature/status telemetry
> - dashboard battery percentage uses BMS SOC when valid
> - stock 4 KiB IAP bootloader preserved
> - SHU ZIPv3 package with plain + NinebotTEA encrypted firmware
> - stationary recovery/revert handoff back to the stock IAP bootloader
>
> CI for the frozen candidate is green. The first real-controller test is still required for the complete SHU -> stock/SHFW rollback path and for BMS current-limit behavior. Keep an ST-Link and a verified full 128 KiB ESC flash backup available for the first hardware test.
>
> **Project documentation:** [G30D SHU Coast + Delta + Stock BMS](docs/G30D_SHU_COAST_DELTA_BMS.md)  
> **Frozen branch:** [freeze/g30-shu-coast-delta-bms-2026-09-30](../../tree/freeze/g30-shu-coast-delta-bms-2026-09-30)  
> **Development PR:** [#2 — G30 SHU Coast + Delta + Stock BMS](../../pull/2)


## Current development: DeltaESC Config app + dual STAR/DELTA profiles

The next G30D candidate is developed on `feature/g30-config-app` in [PR #3](../../pull/3).

Because SHU exposes its configuration UI only for SHFW, this branch adds a dedicated Android companion app instead of restoring the full VESC Tool stack to the 52 KiB SHU image.

The current candidate adds:

- Android **DeltaESC Config** companion app over the stock G30 BLE/dashboard path
- lightweight DeltaESC command protocol (`CMD 0x7D`)
- live speed, bus voltage, Iq, battery input current, SOC, BMS state and STAR/DELTA state
- RAM-first configuration with explicit persistent save
- configurable battery current, wheel size, pole count and relay switching thresholds
- independent STAR and DELTA electrical profiles
- automatic R/L, flux and Hall detection for STAR
- safe PWM-off relay change followed by DELTA R/L and flux detection
- DELTA Hall verification against the STAR Hall table
- automatic STAR/DELTA disabled until both profiles are valid
- failed motor setup restores the previous controller configuration

The companion app intentionally does **not** impersonate SHFW. SHU remains responsible for firmware flashing/recovery; DeltaESC Config handles setup and telemetry.

Android source and build instructions: [android/SmartESCConfig](android/SmartESCConfig)



# Overview

## This fork: G30D SHU build

The G30D build in this fork is intentionally different from the original upstream SmartESC firmware.

### What is retained / supported

- stock G30 dashboard on the original yellow 1-wire line (PA2 / USART2)
- throttle, speed display and Eco / Drive / Sport
- brake input as **motor cut / coast**, with no regenerative braking
- true coast when throttle is released
- stock G30 BMS communication on USART3 (PB10/PB11)
- BMS activator heartbeat plus read-only SOC/current/voltage/temperature/status telemetry
- dashboard battery percentage from real BMS SOC when available
- automatic STAR/DELTA control using the former rear-light output
- stock 4 KiB Ninebot IAP bootloader preserved
- SHU-compatible ZIPv3 package with plain and NinebotTEA-encrypted firmware
- stationary handoff back to the preserved stock IAP bootloader for future SHU flashing / revert

### Bluetooth / SHU firmware updates

The original upstream SmartESC normally overwrites the stock application/boot layout and therefore loses the normal Ninebot Bluetooth firmware-update path.

**That statement does not apply to this G30D SHU build.**

This fork relocates SmartESC to `0x08001000` and deliberately preserves the stock Ninebot IAP bootloader at `0x08000000..0x08000FFF`. The firmware contains a SHU update handoff so a firmware update initiated through ScooterHacking Utility can reboot into the preserved stock IAP bootloader.

So the intended G30D workflow is:

```
SHU / Bluetooth
      ↓
DeltaESC G30D
      ↓
preserved stock IAP bootloader
      ↓
new SmartESC / stock / SHFW DRV
```

The packaging and handoff code are implemented and CI-tested. The complete **DeltaESC -> SHU -> stock/SHFW** rollback path still needs the first real-controller hardware validation, so keep ST-Link recovery available for that first test.

### Current limitations

- Hall sensors are still required; there is no sensorless mode in this build.
- The first real-controller validation of SHU revert and the BMS no-communication current-limit behavior is still pending.
- The compact SHU build uses `SESC_SHU_LITE`; the full VESC Tool stack remains disabled to stay inside the stock 52 KiB application window. The DeltaESC Config companion app provides the G30D motor/current setup path instead.
- The old upstream M365 BMS limitation applies to M365 support, not to the G30D stock-BMS integration described above.

For the exact frozen G30D behavior and memory layout, see [docs/G30D_SHU_COAST_DELTA_BMS.md](docs/G30D_SHU_COAST_DELTA_BMS.md).

# Download

For the frozen G30D SHU Coast + Delta + Stock BMS candidate, use the **Build G30 SHU candidate** workflow/artifact. For the current Config + dual-profile candidate, use the artifacts from PR #3: the SHU ZIP and the Android APK.

The original upstream M365 release information remains available from the upstream SmartESC project.


# Build

Current Config branch build status: [![Build on commit](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/workflows/build_on_commit.yml/badge.svg?branch=feature%2Fg30-config-app)](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/workflows/build_on_commit.yml)

Android app workflow: [Build DeltaESC Config APK](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/workflows/build_config_app.yml)

G30 SHU candidate workflow: [Build G30 SHU candidate](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/workflows/build_g30_shu.yml)

If you want to build it manually, for an easier build, you need `git` and `docker`.

## Clone the project
`git clone https://github.com/ZachWay9bot/SmartESC_STM32_v21b.git`

## Build on Linux
Launch from terminal:

`chmod +x docker_build*; ./docker_build_m365.sh`

`chmod +x docker_build*; ./docker_build_g30.sh`

## Build on Windows
Double click :

`docker_build_m365.sh`

`docker_build_g30.sh`


# Programming

## G30D SHU build

The intended install/update path for the frozen G30D build is **ScooterHacking Utility (SHU) over Bluetooth**.

For the **first hardware test only**, keep an ST-Link connected or immediately available and save a complete 128 KiB flash backup before flashing. This is the recovery path while the new SHU handoff is being validated on real hardware.

A working SHU package is produced by the **Build G30 SHU candidate** workflow.

## ST-Link recovery / original upstream programming

ST-Link is still useful for recovery, full-flash backups and original upstream/M365 flashing.

Plug the ST-Link following this schematic:

![image](https://user-images.githubusercontent.com/11454444/146688635-b5a1ed07-3482-420f-b324-9e58b0a19dc9.png)

With [STM32 ST-Link Utility](https://www.st.com/en/development-tools/stsw-link004.html), the option bytes/read protection can be inspected when required.

# Configuration

DeltaESC G30D uses the dedicated **DeltaESC Config** Android app for motor
detection, current limits, telemetry and STAR/DELTA profiles.

The full VESC Tool stack is intentionally disabled in the SHU build to keep the
application inside the stock 52 KiB G30 firmware region. VESC Tool instructions
belong to the upstream SmartESC project and are therefore not duplicated here.

# ESP32 test module

M365 connections :
![image](https://user-images.githubusercontent.com/11454444/146688619-c3bc8e6d-6884-4b1c-81d6-9ec456d1e41b.png)

Use ESP32 prototype board with and ESP32-devkit-c module :
![image](https://user-images.githubusercontent.com/11454444/146688428-d8978339-fab1-4a7b-a88f-305298b6b64f.png)

Use the code provided in the [serial-trottle-brake-esp32](/serial-trottle-brake-esp32) folder with Platform.io
