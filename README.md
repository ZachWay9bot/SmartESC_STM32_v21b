# DeltaESC

> [!CAUTION]
> ## UNVALIDATED G30 HARDWARE TEST BUILD
>
> **The G30/DeltaESC motor-control firmware is NOT yet 100% validated on real G30 power hardware. Do not blindly install or flash this firmware on a controller that you cannot recover with ST-Link/SWD.**
>
> A successful compile, CI run, BLE connection, stock-ESC diagnostic or bench test does **not** count as complete validation of the motor-control firmware. Real-controller validation is still required for sensored FOC startup and running under load, current measurement/scaling, fault handling, SHU rollback/recovery, BMS behavior and any STAR/DELTA functionality.
>
> Until these tests have been completed successfully on real hardware, this repository must be treated as **experimental / hardware-test only**. Keep **ST-Link/SWD access and a verified full 128 KiB flash backup** available.
>
> **Blind installation on a daily-use or non-recoverable G30 controller is explicitly discouraged.**

> ## Current conservative candidate: G30 sensored hwtest v0.1
>
> Branch: `candidate/g30-sensored-hwtest-v0.1`
>
> This candidate is deliberately limited to **stock STAR + Hall-sensored FOC**. Automatic STAR/DELTA, sensorless/HFI and automatic motor detection are disabled. Hardware limits are capped at **12 A phase, 8 A battery and 15 A absolute current**.
>
> Additional bring-up fixes included after auditing active SmartESC v2 forks:
> - 13 KiB G30 RTOS heap for usable SRAM link margin
> - Hall electrical-angle + compensation-angle re-sync after true coast
> - corrected q-axis battery-current scaling (3/2 Clarke/Park power factor)
> - G30 current-PI SI-to-ST-count scaling, checked against the original Workbench gain order
> - APP_ADC fall-through fix so a live config write cannot replace the dashboard/ADC task
>
> **This is still an unvalidated hardware-test candidate, not a release. First validation is wheel-off-ground with ST-Link/SWD recovery available.**

**DeltaESC is a G30D-focused motor-controller firmware based heavily on SmartESC by Koxx3.**

Upstream project: [Koxx3/SmartESC_STM32_v2](https://github.com/Koxx3/SmartESC_STM32_v2)

DeltaESC keeps the SmartESC motor-control foundation while focusing this fork on the Ninebot G30D: reversible SHU flashing, stock IAP preservation, true coast/no-regen, stock G30 BMS support, automatic STAR/DELTA switching and a dedicated Android configuration app.

> **Attribution:** DeltaESC is a heavily modified derivative of **SmartESC by Koxx3**. Existing upstream copyright and license headers in the source files are retained.


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
- lightweight SmartESC command protocol (`CMD 0x7D`)
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
SmartESC G30D
      ↓
preserved stock IAP bootloader
      ↓
new DeltaESC / stock / SHFW DRV
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

# VESC Tool

The compact DeltaESC G30D build intentionally does **not** include the full VESC Tool interface. That stack is disabled to keep the reversible SHU application inside the stock 52 KiB G30 application window.

Motor setup, current limits, STAR/DELTA profiles and live telemetry are handled by the dedicated **DeltaESC Config** Android app instead.

The original VESC Tool and M365 documentation belongs to upstream SmartESC and remains available in the upstream project linked above.
