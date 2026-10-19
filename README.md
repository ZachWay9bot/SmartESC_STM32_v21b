# SmartESC G30 NativeDash v0.8.7

Current primary target: **Ninebot MAX G30 / G30D 3-cap STM32F103 ESC**.

This fork is now focused on the G30 sensorless branch. The old M365 target, old ESP32 serial-throttle experiment and historical reference documents are kept under `legacy/` so the repository root reflects the firmware that is actually being developed.

> **Status: active hardware-development build.**
> The sensorless startup and motor-parameter detection are based on hardware-validated G30-identical/G30 work, but this exact v0.8.7 integration still needs validation on a current-limited lab PSU before road use.

## Download / flash

Current v0.8.7 files live under [`firmware/v0.8.7/`](firmware/v0.8.7/):

- [SHU ZIP](firmware/v0.8.7/SmartESC_G30_NativeDash_v0.8.7_SHU.zip)
- [IAP Driver.bin](firmware/v0.8.7/SmartESC_G30_NativeDash_v0.8.7_IAP_Driver.bin)
- [Flash / recovery / stock-restore guide](firmware/v0.8.7/FLASH_AND_RESTORE.md)
- [SHA-256 checksums](firmware/v0.8.7/SHA256SUMS.txt)

The SHU ZIP is for the stock-compatible ScooterHacking flash path. The IAP Driver.bin is the encrypted `FIRM.bin.enc` payload for direct IAP / RemoteLab / 3-second recovery.

## Current firmware

**SmartESC G30 NativeDash v0.8.7**

CI reference: **G30 SHU build #87**  
Merged G30 implementation: `b71510a994d88ebcf7395c459798327e9f20e01f`

Main features:

- sensorless FOC for G30-style hub motors
- intended for both G30 **Gen1 (6-prefix)** and **Gen2 (9-prefix)** motors by measuring the connected motor instead of hard-coding a serial-number profile
- VESC Tool 6.06 protocol on the IoT/service UART
- one-click **Setup Motors FOC / Detect All (no CAN)**
- R, L and flux-linkage measurement
- automatic current-controller and observer parameter calculation
- native G30 dashboard protocol on the Yellow Wire
- throttle + brake input from the original dashboard
- brake has priority over throttle
- dashboard speed, battery, light, beep and fault status
- native `5A A5` Ninebot framing
- 3-second application recovery/IAP path
- stock Ninebot bootloader retained

## VESC Tool

Recommended host version: **VESC Tool 6.06 Stable**.

Service connection:

- USART1 remap: **PB6 TX / PB7 RX**
- 115200 baud, 8N1
- USB-UART at 3.3 V logic level
- connect directly to the controller service/IoT UART

For a new motor:

1. connect VESC Tool
2. open **Setup Motors FOC / Detect All**
3. use **Run Detection (no CAN)**
4. keep the wheel/motor free
5. validate the measured values before any high-power test

The G30 detector deliberately uses conservative bench limits and does not run CAN or Hall detection.

For the currently measured reference motor, a useful plausibility region is around:

```text
R phase  ~ 0.58 ohm
Ld       ~ 0.64 mH
Flux     ~ 0.012 Wb
```

These are reference values only. The whole point of Detect All is to measure the actual connected Gen1/Gen2 motor.

## Native G30 dashboard

The original G30 dashboard uses **USART2 / PA2**, 115200 baud, half duplex.

Implemented native framing:

```text
5A A5 | LEN | SRC | DST | CMD | ARG | DATA... | CRC16
```

Relevant dashboard traffic:

- `0x61`, `0x64`, `0x65`: lever/control frames can carry throttle and brake
- only incoming dashboard `CMD64` is answered with the normal ESC status heartbeat
- ESC -> dashboard `CMD64` status payload:
  `[Mode, Battery, Light, Beep, Speed, Fault]`

Register reads are a different protocol layer. In particular:

- `0x26` = speed register
- `0x29 / 0x2A` = odometer low/high

A raw byte such as `0x29` inside a lever heartbeat is therefore not automatically the speed register.

## Safety / control behaviour

The default ADC control type is **Current No Reverse Brake ADC**. When brake is active, braking is commanded and throttle is not applied in that control cycle.

Normal sensorless drive is kick-start/flying-start oriented. A valid rolling/BEMF lock is required before ordinary torque is accepted. The Detect All open-loop measurement path is separate and can intentionally rotate the motor from standstill during detection.

Start testing at low bus voltage with current limiting and a free wheel. Do not jump directly from a successful software build to a 14S road test. Silicon is notoriously bad at reading GitHub badges.

## Recovery / flash layout

The stock Ninebot bootloader is preserved.

```text
0x08000000 .. 0x08000FFF   stock bootloader
0x08001000 .. 0x0800E7FF   SmartESC application window (54 KiB)
0x0800E800 ..              stock OTA staging
0x0801C400                 SmartESC APP config
0x0801C800                 SmartESC motor config
0x0801F800                 stock update control
```

Application-level recovery:

- hold the power button for at least **3 seconds during power-up**
- recovery UART: PB6/PB7, 115200
- command family: `0x07 BEGIN -> 0x08 WRITE -> 0x09 FINALIZE -> 0x0A RESET`

The application recovery cannot help if the application itself is completely unable to execute. The untouched stock bootloader remains the lower-level recovery boundary.

## Build

G30 build:

```bash
./docker_build_g30p.sh
```

The application binary is generated under:

```text
g30p/STM32CubeIDE/Debug/g30p.bin
```

Build a ScooterHacking ZIPv3 package with:

```bash
python3 tools/make_shu_zip.py \
  g30p/STM32CubeIDE/Debug/g30p.bin \
  SmartESC_G30_NativeDash_v0.8.7_SHU.zip \
  --name "SmartESC G30 NativeDash v0.8.7"
```

GitHub Actions workflow **Build G30 SHU candidate** performs the same G30 build, validates the app window/vector table and uploads the BIN/ELF/MAP plus SHU package.

## Repository layout

```text
g30p/          current G30 STM32CubeIDE target
common_files/  current shared motor-control / VESC / dashboard code
tools/         SHU packaging and project tools
Hardware/      hardware reference material
docs/          current project notes
legacy/        historical M365 target, old experiments and reference docs
```

The `legacy/` tree is retained for archaeology and upstream history. It is not the current product target.

## Current development priorities

1. validate v0.8.7 Detect All on a current-limited lab PSU setup
2. verify Gen1 and Gen2 motor detection ranges
3. validate native dashboard throttle/brake plus speed/battery display on hardware
4. audit pole-count semantics before high-speed/road qualification
5. qualify limits and fault handling before 14S operation

## Credits

This repository is derived from SmartESC STM32 work and ST Motor Control SDK components, with additional G30-identical sensorless, VESC Tool, recovery and native dashboard integration in this fork. Existing upstream copyright/license notices remain with their respective source files.
