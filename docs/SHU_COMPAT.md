# G30 SHU-compatible SmartESC build

This branch is an experimental SHU/stock-IAP variant of the G30 SmartESC
Coast + no-regen + STAR/DELTA build.

## Flash layout

The original SmartESC G30 target was linked at `0x08000000`, which replaces
the stock Ninebot bootloader. This branch instead uses:

```
0x08000000..0x08000FFF  stock Ninebot IAP bootloader (must already be present)
0x08001000..0x0800D7FF  DeltaESC application, max 50 KiB
0x0800D800..0x0800DBFF  DeltaESC app configuration (page 54)
0x0800DC00..0x0800DFFF  DeltaESC motor configuration (page 55)
0x0800E000..0x0801BFFF  stock update staging area, preserved
0x0801C000..0x0801F7FF  stock configuration/calibration region, preserved
0x0801F800..0x0801FFFF  stock update-control region, preserved
```

DeltaESC's emulated configuration pages are kept inside the stock application
window on pages 54/55 (`0x0800D800` and `0x0800DC00`). The linker is capped
at 50 KiB so firmware code cannot overlap those pages.

This replaces the earlier pages-56/57 layout. A real 128 KiB stock G30
DRV 1.2.6 full-flash dump has a normal application vector at `0x08001000`
and a second firmware image in the upper-flash OTA staging area beginning at
`0x0800E800`. Independent reverse-engineering also maps the staging region
from `0x0800E000` through `0x0801BFFF`. DeltaESC therefore treats the
entire upper staging region as untouchable.

The stock G30 application window itself is 52 KiB, ending at `0x0800DFFF`.
Reserving its final two pages leaves a 50 KiB executable ceiling. If DeltaESC
does not link below `0x0800D800`, the SHU build must be slimmed down rather
than consuming configuration or stock OTA staging space.

## Stock G30 BMS integration

The reversible G30 build keeps the factory BMS on its dedicated USART3 link
(PB10 TX / PB11 RX, 115200 8N1).

To avoid the stock BMS no-communication current fallback, the firmware sends
the byte sequence demonstrated by `rasil1127/Ninebot-BMS-Activator` every
200 ms:

```
5A A5 06 20 22 30 00 00 87 FF FF
```

The final `FF` is intentionally retained for byte-for-byte compatibility with
the public activator implementation.

The same task also performs read-only stock-protocol polling for:

- `0x32` state of charge
- `0x33` pack current
- `0x34` pack voltage
- `0x35` temperature
- `0x30` status

When valid BMS telemetry is present, the stock dashboard battery percentage is
fed from BMS SOC. If BMS telemetry is absent, the existing voltage-derived
battery estimate remains as fallback.

This does not rewrite BMS current/protection settings and does not disable the
BMS hardware protection paths.

## SHU package

`tools/make_shu_zip.py` creates a ZIPv3 package containing:

- `FIRM.bin`
- `FIRM.bin.enc` using NinebotTEA
- `info.json` for model `max`, type `DRV`,
  `max_DRV_STM32F103CxT6`
- `params.txt`

The script refuses a binary whose vector table is not linked for
`0x08001000` or whose size exceeds the reserved application area.

## Returning to the stock bootloader

A second stock Ninebot `5A A5` sniffer runs alongside the existing
SmartESC dashboard parser. It does **not** treat generic extended opcodes as an
update request. It only accepts a checksum-valid ESC IAP-start write to
register `0x07` with the expected four-byte `firmware-size + version`
payload and a plausible firmware size. To tolerate the split in public tooling,
it accepts both `LEN=4` (payload-byte convention) and `LEN=8` (older tools
that include the four routing bytes).

At standstill the handoff then:

1. commands zero motor current,
2. waits for low measured Iq,
3. forces the STAR relay state,
4. disables motor PWM,
5. programs only the upper half-word of the SmartESC initial stack pointer to
   zero, intentionally making the application vector invalid,
6. resets the MCU so the preserved stock bootloader must take the recovery/IAP
   path.

A successful SHU flash writes a fresh application vector and restores normal
boot. The same recovery entry is available manually by holding the power button
for more than five seconds while stationary.

The vector invalidation is intentionally one-way until another firmware is
flashed. That makes the recovery trigger robust, but it is also why the first
hardware validation must be done with an ST-Link and a verified full-flash
backup within reach.

## Validation status

This branch is intentionally separate from the normal SmartESC build.

The linker/vector relocation and ZIPv3/NinebotTEA package generation are
deterministic and can be checked in CI. The exact hand-off behavior of every
G30 stock bootloader revision still needs a real-controller test before this is
treated as a no-ST-Link recovery guarantee.

For the first hardware test, keep a verified full flash backup and an ST-Link
available. Test with the wheel unloaded and low current before road use.
