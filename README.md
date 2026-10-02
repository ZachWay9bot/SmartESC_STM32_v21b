# SmartESC

**SmartESC (aka SESC) is an alternative firmware for Xiaomi M365 and Ninebot G30 controller.**

![image](https://user-images.githubusercontent.com/11454444/148704200-e28ee13e-c91b-4aac-8dbf-6021095749a5.png)


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


# Overview

Avantage over other Xiaomi custom firmwares :
- you can put any motor since it can detect all motor parameters and optimize them
- you can use any battery, even 20s (with hardware modifications), change the voltage divider and set the new value in the controller
- you can change the shunts values and set the new value in the controller
- you can setup the controller very easily with VESCTool and make a lot of performance/stability tests
- you can use the controller with any other device, event without any display
- soon, we hope to support multiple linked controller

Cons :
- you loose the ability to monitor M365 BMS for now (work in progress), but don't worry, you still have the voltage ;)
- you loose the ability to update firmwares through bluetooth
- for now, it needs hall sensors (no sensorless mode). [work in progress]

It can interface :
- the stock M365/G30 display
- VESCTool through VESC interface on the BMS UART (full duplex UART).

Nota : this firmware is in beta. 

You'll be able to setup and control the controller/motor from VESCTool interface with a simple USB/Serial adapter.
With any small arduino, use analog acceleration/brake throttles to control any electic moving device like escooter, gokart, electric skateboard without using the stock display.


# Download

For the G30D SHU Coast + Delta + Stock BMS candidate, use the **Build G30 SHU candidate** GitHub Actions workflow/artifact from this fork. The frozen source is pinned above so the tested source revision cannot be confused with later development.

The original upstream M365 release information remains available from the upstream SmartESC project.


# Build

Current fork build status: [![Build on commit](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/workflows/build_on_commit.yml/badge.svg?branch=feature%2Fshu-coast-delta)](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/workflows/build_on_commit.yml)

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

You need a ST-Link device to reprogram the M365/G3O controller.
It costs 3/4€ on Aliexpress.

Plug the st-link following this schematic :
![image](https://user-images.githubusercontent.com/11454444/146688635-b5a1ed07-3482-420f-b324-9e58b0a19dc9.png)

With [STM32 ST-Link Utility](https://www.st.com/en/development-tools/stsw-link004.html), disable Re&d out protection.

Menu "Target" => "Option bytes"
![image](https://user-images.githubusercontent.com/11454444/146688019-3e5122c7-f3fb-4964-a44f-684af023746e.png)


# VescTool

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
