# G30 SHU-compatible SmartESC build

This branch is an experimental SHU/stock-IAP variant of the G30 SmartESC
Coast + no-regen + STAR/DELTA build.

## Flash layout

The original SmartESC G30 target was linked at `0x08000000`, which replaces
the stock Ninebot bootloader. This branch instead uses:

```
0x08000000..0x08000FFF  stock Ninebot IAP bootloader (must already be present)
0x08001000..0x0800DFFF  SmartESC application, max 52 KiB
0x0800E000..0x0800E7FF  SmartESC app/motor configuration (pages 56/57)
0x0800E800..0x0801BFFF  stock update staging area
0x0801C000..0x0801F7FF  stock configuration/calibration region, preserved
0x0801F800..0x0801FFFF  stock update-control region, preserved
```

SmartESC's emulated configuration pages are moved to flash pages 56/57
(`0x0800E000` and `0x0800E400`). The documented stock staging area begins
at `0x0800E800`, and the stock calibration/update-control region is deliberately
not touched.

The 52 KiB application ceiling is also deliberate. The stock G30 IAP start
packet carries firmware size as a 16-bit value, and the documented ESC app
region ends at `0x0800DFFF`. If SmartESC does not link inside this region,
the SHU build must be slimmed down rather than silently consuming the stock
staging area.

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

A second, checksum-validated stock Ninebot `5A A5` parser runs alongside the
existing SmartESC dashboard parser. At standstill it watches for conservative
stock IAP/update-entry commands and then:

1. commands zero motor current,
2. waits for low measured Iq,
3. forces the STAR relay state,
4. disables motor PWM,
5. resets the MCU so the preserved stock bootloader gets control.

There is also a manual recovery path: holding the power button for more than
five seconds while stationary resets the controller while the button is still
physically held.

## Validation status

This branch is intentionally separate from the normal SmartESC build.

The linker/vector relocation and ZIPv3/NinebotTEA package generation are
deterministic and can be checked in CI. The exact hand-off behavior of every
G30 stock bootloader revision still needs a real-controller test before this is
treated as a no-ST-Link recovery guarantee.

For the first hardware test, keep a verified full flash backup and an ST-Link
available. Test with the wheel unloaded and low current before road use.
