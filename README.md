# SmartESC

**SmartESC (aka SESC) is an alternative firmware for Xiaomi M365 and Ninebot G30 controller.**

![image](https://user-images.githubusercontent.com/11454444/148704200-e28ee13e-c91b-4aac-8dbf-6021095749a5.png)


> ## G30D SmartESC Config v0.2 — current hardware-test candidate
>
> This fork contains a G30D-specific SmartESC build with SHU flashing/recovery, stock dashboard + BMS support, true coast/no-regen, automatic STAR/DELTA switching and a dedicated Android configuration app.
>
> **Candidate branch:** `candidate/g30-config-app-v0.2`  
> **Candidate commit:** `f7c22f4859ef28fa3ce29499b5d79cd8aa3267df`
>
> Current v0.2 feature set:
> - stock G30 dashboard on PA2 / USART2 half-duplex
> - throttle, speed display and Eco / Drive / Sport
> - brake input = motor cut; no regenerative braking
> - true coast on throttle release
> - stock G30 BMS on USART3 (PB10/PB11)
> - BMS activator heartbeat + SOC/current/voltage/temperature/status telemetry
> - dashboard battery percentage from BMS SOC when valid
> - automatic STAR/DELTA using the former rear-light output
> - configurable DELTA/STAR thresholds, max switch Iq and relay settle time
> - separate STAR and DELTA R/L/flux/current profiles
> - VESC-style motor setup: R/L measurement, open-loop flux measurement and Hall detection
> - DELTA setup only after a valid STAR profile; Hall result is cross-checked
> - profile swap while PWM is off; FOC Kp/Ki is recalculated per topology
> - stock 4 KiB Ninebot IAP bootloader preserved
> - SHU ZIPv3 package with plain + NinebotTEA-encrypted firmware
> - dedicated Android **SmartESC Config** app instead of the SHFW-only SHU Config UI
> - Android BLE transport includes legacy NinebotCrypto 5B/5C/5D authentication
>
> Current CI for the candidate commit is green:
> - **Build G30 SHU candidate #36:** success
> - **Build on commit #69:** success
> - **Build SmartESC Config APK #23:** success
> - Android protocol/NinebotCrypto unit tests: success
> - G30 firmware: **0 errors / 0 warnings**
> - `g30p.bin`: **48,864 bytes** inside the stock 52 KiB application window
>
> **Important:** this is a hardware-test candidate. The code/build/package path is validated, but real G30D validation is still required for BLE forwarding of the private config protocol, motor detection in both topologies, relay switching under load, BMS current-limit behavior and SHU → stock/SHFW rollback. Keep ST-Link and a verified 128 KiB full-flash backup available for the first test.
>
> **Candidate branch:** [candidate/g30-config-app-v0.2](../../tree/candidate/g30-config-app-v0.2)  
> **Candidate PR:** [#3 — G30 SmartESC Config v0.2](../../pull/3)  
> **v0.2 documentation:** [docs/G30D_SMARTESC_CONFIG_V0_2.md](docs/G30D_SMARTESC_CONFIG_V0_2.md)  
> **Android source:** [android/SmartESCConfig on the candidate branch](../../tree/candidate/g30-config-app-v0.2/android/SmartESCConfig)
>
> The older pre-config freeze remains available for reference:
> [freeze/g30-shu-coast-delta-bms-2026-09-30](../../tree/freeze/g30-shu-coast-delta-bms-2026-09-30)

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
new SmartESC / stock / SHFW DRV
```

The packaging and handoff code are implemented and CI-tested. The complete **SmartESC -> SHU -> stock/SHFW** rollback path still needs the first real-controller hardware validation, so keep ST-Link recovery available for that first test.

### Current limitations

- Hall sensors are still required; there is no sensorless mode in this build.
- The first real-controller validation of SHU revert and the BMS no-communication current-limit behavior is still pending.
- The compact SHU build uses `SESC_SHU_LITE`; the full VESC Tool stack is disabled to stay inside the stock 52 KiB application window.
- Motor/current setup for this G30D build is handled by the dedicated **SmartESC Config** Android app.
- The old upstream M365 BMS limitation applies to M365 support, not to the G30D stock-BMS integration described above.

For the current v0.2 motor/configuration workflow, see [docs/G30D_SMARTESC_CONFIG_V0_2.md](docs/G30D_SMARTESC_CONFIG_V0_2.md). The older frozen base is documented in [docs/G30D_SHU_COAST_DELTA_BMS.md](docs/G30D_SHU_COAST_DELTA_BMS.md).

# Download

The current G30D hardware-test candidate is pinned to:

```
branch: candidate/g30-config-app-v0.2
commit: f7c22f4859ef28fa3ce29499b5d79cd8aa3267df
```

GitHub Actions artifacts for that exact commit:

- firmware: **SmartESC-G30-Config-SHU-36**
- Android app: **SmartESC-Config-Android-23**
- full build/regression: **Build on commit #69**

Use PR #3 and the candidate branch links above to avoid accidentally testing a later development commit.

The original upstream M365 release information remains available from the upstream SmartESC project.


# Build

Current development build status: [![Build on commit](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/workflows/build_on_commit.yml/badge.svg?branch=feature%2Fg30-config-app)](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/workflows/build_on_commit.yml)

Android app workflow: [Build SmartESC Config APK](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/workflows/build_config_app.yml)

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

The intended install/update path for the G30D candidate is **ScooterHacking Utility (SHU) over Bluetooth**. Configuration and motor setup are then performed with the dedicated **SmartESC Config** Android app.

For the **first hardware test**, keep an ST-Link connected or immediately available and save a complete 128 KiB flash backup before flashing. This remains the recovery path while the SHU handoff and BLE configuration path are being validated on real hardware.

A SHU package is produced by the **Build G30 SHU candidate** workflow and the APK by **Build SmartESC Config APK**.

## ST-Link recovery / original upstream programming

ST-Link is still useful for recovery, full-flash backups and original upstream/M365 flashing.

Plug the ST-Link following this schematic:

![image](https://user-images.githubusercontent.com/11454444/146688635-b5a1ed07-3482-420f-b324-9e58b0a19dc9.png)

With [STM32 ST-Link Utility](https://www.st.com/en/development-tools/stsw-link004.html), the option bytes/read protection can be inspected when required.

# VescTool

The **G30D SHU v0.2** candidate uses `SESC_SHU_LITE` to fit inside the stock 52 KiB application region, so the full VESC Tool stack is intentionally disabled.

For this G30D build, the replacement setup path is the dedicated **SmartESC Config** Android app. It provides current limits, live telemetry, persistent configuration, STAR/DELTA profiles and the R/L/flux/Hall motor-detection workflow.

The information below applies only to the original/full SmartESC builds that include the VESC interface.

Use [VescTool](https://vesc-project.com/vesc_tool) to setup the motor and input properties.

Use a serial USB adapter to connect the Xiaomi controller as an USB VESC :
![image](https://user-images.githubusercontent.com/11454444/146688647-e3e4d833-7c93-4b4b-a297-cc61ba52071e.png)

Launch VESCTool and connect with COM port.
![image](https://user-images.githubusercontent.com/11454444/146687240-e393ea2e-dfd9-4fac-870e-4cf526a61187.png)

Launcher Motor setup wizzard.
![image](https://user-images.githubusercontent.com/11454444/146688494-b4a6c183-a89f-4517-af1f-61b5358aad40.png)

Enter all your settings in the different windows.

Enable the keyboard control :

![image](https://user-images.githubusercontent.com/11454444/146688470-adf8a8f7-e3b4-43f4-9038-479d3d5585c5.png)

You're ready to test your M365 controller with your keyboard !


# ESP32 test module

M365 connections :
![image](https://user-images.githubusercontent.com/11454444/146688619-c3bc8e6d-6884-4b1c-81d6-9ec456d1e41b.png)

Use ESP32 prototype board with and ESP32-devkit-c module :
![image](https://user-images.githubusercontent.com/11454444/146688428-d8978339-fab1-4a7b-a88f-305298b6b64f.png)

Use the code provided in the [serial-trottle-brake-esp32](/serial-trottle-brake-esp32) folder with Platform.io

# Error Code SESC (Smart ESC) in VESC Tool

Can read it in "VESC Terminal" (or others Serial Terminal)

- 0 = MC_NO_ERROR     (No error)
- 0= MC_NO_FAULTS     (No error)
- 1 = MC_FOC_DURATION (FOC rate to high)
- 2 = MC_OVER_VOLT    (Software over voltage)
- 4 = MC_UNDER_VOLT   (Software under voltage)
- 8 = MC_OVER_TEMP    (Software over temperature)
- 16 = MC_START_UP    (Startup failed)
- 32 = MC_SPEED_FDBK  (Speed feedback)
- 64 = MC_BREAK_IN    (Emergency input (Over current))
- 128 = MC_SW_ERROR

# Command available in VESCTool terminal

- help (see all available commands)
- foc_openloop [current] [erpm]  (Exemple : foc_openloop 10 500)
- ... (lot of other commands)
