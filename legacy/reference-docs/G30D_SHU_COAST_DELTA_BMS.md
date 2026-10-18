# G30D SHU Coast + Delta + Stock BMS

> **Historical baseline:** this document describes the pre-config v1 freeze.  
> The current hardware-test candidate is **G30D SmartESC Config v0.2**:
> [G30D_SMARTESC_CONFIG_V0_2.md](G30D_SMARTESC_CONFIG_V0_2.md).
>
Status: **frozen hardware-test candidate**

Frozen source branch:

```
freeze/g30-shu-coast-delta-bms-2026-09-30
```

Frozen commit:

```
b4e7bbb38c9738b0f58bdbd1ff28c61c5d0b279e
```

## Purpose

This G30D-specific SmartESC variant keeps the stock Ninebot IAP bootloader,
adds a SHU-compatible application layout, keeps the stock dashboard and stock
BMS links, implements true coast/no-regen behavior, and adds automatic
STAR/DELTA switching using the former rear-light output.

## Frozen feature set

### Stock dashboard

- PA2 / USART2
- 115200 baud
- half-duplex / 1-wire
- throttle input
- brake input
- speed display
- Eco / Drive / Sport
- power-button handling
- dashboard battery percentage

Brake behavior in this build is intentionally changed:

- brake request cuts propulsion
- no regenerative braking is commanded
- throttle release transitions to true coast once measured Iq is low enough

### STAR / DELTA

The former G30 rear-light output is repurposed as the STAR/DELTA control output.

Thresholds:

```
DELTA >= 32 km/h
STAR  <= 26 km/h
```

The 26-32 km/h gap provides hysteresis.

Switch sequence:

1. command torque/current to zero
2. wait until measured |Iq| <= 2 A
3. disable inverter PWM
4. change relay topology
5. wait 100 ms for relay contacts
6. restart PWM/current control
7. resume torque with the normal ramp

Relay-deenergized is intended to be the fail-safe STAR state.

The ESC output must drive an external transistor/MOSFET/opto relay driver.
Do not drive relay coils directly from the MCU/output pin.

### Stock BMS

The factory G30 BMS stays on the stock dedicated link:

```
USART3
PB10 = ESC TX -> BMS RX
PB11 = ESC RX <- BMS TX
115200 8N1
```

The firmware sends the activator/heartbeat sequence every 200 ms:

```
5A A5 06 20 22 30 00 00 87 FF FF
```

It also performs read-only polling for:

- 0x32 SOC
- 0x33 pack current
- 0x34 pack voltage
- 0x35 temperature
- 0x30 status

When valid BMS telemetry is present, the stock dashboard battery percentage
uses BMS SOC. If no valid BMS telemetry is available, the previous
voltage-derived battery estimate is retained as fallback.

This code does not rewrite BMS protection thresholds and does not intentionally
disable stock BMS hardware protections.

## SHU / reversible layout

The frozen G30 application is linked at:

```
0x08001000
```

The stock first 4 KiB bootloader at `0x08000000..0x08000FFF` is preserved.

Application window:

```
0x08001000..0x0800DFFF
52 KiB maximum
```

SmartESC configuration:

```
0x0800E000..0x0800E7FF
```

The stock upper update/calibration/control regions are intentionally preserved.

The SHU packager generates:

- FIRM.bin
- FIRM.bin.enc
- info.json
- params.txt

The encrypted image uses the NinebotTEA packaging path expected by SHU.

## Recovery / revert concept

A checksum-valid SHU firmware-update start request is recognized only while the
scooter is stationary.

The handoff sequence is:

1. zero motor torque
2. require low measured Iq
3. force STAR
4. stop PWM
5. invalidate the SmartESC application vector
6. reset
7. preserved stock IAP bootloader remains available for the replacement flash

A held power-button recovery path is also present.

**Important:** CI/build/package validation is complete, but the complete
SmartESC -> SHU -> stock/SHFW rollback sequence still requires the first real
controller validation.

## Frozen CI result

Frozen source commit:

```
b4e7bbb38c9738b0f58bdbd1ff28c61c5d0b279e
```

Verified workflows:

- Build G30 SHU candidate #13: SUCCESS
- Build on commit #32: SUCCESS

Frozen application size:

```
45,828 bytes
```

The build remains inside the 52 KiB stock application window.

## First hardware test

Use an unloaded wheel and conservative current limits.

Before flashing:

1. connect ST-Link
2. save the complete 128 KiB ESC flash
3. preserve that backup unchanged
4. keep ST-Link available during the entire first test

Recommended validation order:

1. boot and dashboard
2. speed display
3. throttle
4. brake = motor cut
5. true coast
6. BMS communication and SOC
7. verify behavior above the former no-communication current limit gradually
8. SHU revert to a known-good stock/SHFW DRV
9. flash this SmartESC build again
10. only then connect and test the external STAR/DELTA relay stage

Do not begin the first test with the STAR/DELTA relays connected.

## Relevant GitHub locations

- Repository: https://github.com/ZachWay9bot/SmartESC_STM32_v21b
- Frozen branch: https://github.com/ZachWay9bot/SmartESC_STM32_v21b/tree/freeze/g30-shu-coast-delta-bms-2026-09-30
- Development PR: https://github.com/ZachWay9bot/SmartESC_STM32_v21b/pull/2
- SHU workflow: https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/workflows/build_g30_shu.yml

## Upstream

This repository is based on SmartESC. Existing upstream documentation below
the fork-specific README section remains relevant for the original SmartESC
architecture, M365 support and general build information.
