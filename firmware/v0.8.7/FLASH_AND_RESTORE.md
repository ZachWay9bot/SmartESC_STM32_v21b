# Flash, Recovery and Restore

Current firmware: **SmartESC G30 NativeDash v0.8.7**

Files in this directory:

- `SmartESC_G30_NativeDash_v0.8.7_SHU.zip` — ScooterHacking ZIPv3 package
- `SmartESC_G30_NativeDash_v0.8.7_IAP_Driver.bin` — encrypted IAP payload, identical to `FIRM.bin.enc`
- `SHA256SUMS.txt` — hashes for the published files

Recovery host tools are in `tools/recovery/`.

## 1. Normal flash with ScooterHacking Utility

Use the SHU ZIP when the controller is still reachable through a compatible stock Ninebot flash path.

1. Power the controller from a stable battery or bench supply.
2. Keep the motor/wheel free and do not touch throttle or brake during flashing.
3. Open ScooterHacking Utility.
4. Choose the G30 / MAX DRV flash function.
5. Select `SmartESC_G30_NativeDash_v0.8.7_SHU.zip`.
6. Let the flash finish completely and power-cycle the controller.

The package preserves the stock 4 KiB Ninebot bootloader and installs the SmartESC application at `0x08001000`.

**Important:** the current SmartESC NativeDash build does not yet implement the complete stock BLE 5B/5C/5D pairing/pass-through path. A first flash from stock through the original dashboard/BLE can work, but do not depend on the stock BLE route for later updates. For subsequent development use the direct IAP path or the 3-second recovery path below.

## 2. Direct IAP flash

The published `*_IAP_Driver.bin` is the encrypted Ninebot-IAP payload. It is **not** the raw application binary.

Use it with the existing WebDev/RemoteLab IAP uploader or another compatible XBOT/Ninebot IAP sender.

Protocol:

```text
Host source: 0x3D
ESC target:  0x20
UART:        115200 8N1
BEGIN:       0x07
WRITE:       0x08, 128-byte blocks
FINALIZE:    0x09
RESET:       0x0A
```

Stock staging starts at `0x0800E800`. The active application begins at `0x08001000`.

Do not send the raw `FIRM.bin` to this encrypted-IAP path.

## 3. Three-second recovery

This is the preferred recovery method when SmartESC still starts far enough to enter its early boot recovery handler.

Wiring:

```text
USB-UART TX -> ESC PB7
USB-UART RX -> ESC PB6
USB-UART GND -> ESC GND
115200 baud, 8N1, 3.3 V logic
```

Power the controller normally from its own supply. Do not power the ESC from the USB-UART adapter.

Procedure:

1. Turn the controller fully off.
2. Connect PB6/PB7/GND.
3. Hold the scooter power button.
4. Apply controller power while continuing to hold the button.
5. Hold for at least 3 seconds.
6. Release the button.
7. Recovery should identify as `XBOTRCV1V00001`.
8. Install pyserial if needed:

   ```text
   py -m pip install pyserial
   ```

9. From the repository root run:

   ```text
   py tools/recovery/recovery_iap_flash.py COM9 firmware/v0.8.7/SmartESC_G30_NativeDash_v0.8.7_SHU.zip
   ```

   or use the encrypted IAP file directly:

   ```text
   py tools/recovery/recovery_iap_flash.py COM9 firmware/v0.8.7/SmartESC_G30_NativeDash_v0.8.7_IAP_Driver.bin
   ```

On Windows you can also drag the SHU ZIP or IAP Driver.bin onto:

```text
tools/recovery/RECOVERY_FLASH_COM9.cmd
```

The recovery loader writes to staging first. Only a successful FINALIZE sets the stock pending-update control block. RESET is refused before successful FINALIZE, so an interrupted BEGIN/WRITE does not deliberately replace the active application.

## 4. Restore this SmartESC version

To recover back to the known v0.8.7 image, use either the SHU ZIP or the IAP Driver.bin from this directory with the 3-second recovery process above.

This is the normal **custom-firmware restore** path.

## 5. Restore original Ninebot DRV126

Original Ninebot firmware is not distributed in this repository.

To return to stock, use a known-good, model-correct **G30 STM32F103 DRV126 SHU package** from a source you trust.

Two possible routes:

### If the stock-compatible dashboard/BLE flash path is available

Flash the stock DRV ZIP with ScooterHacking Utility using its normal DRV restore/flash process.

### If SmartESC 3-second recovery is available

The recovery flasher can also accept a compatible stock SHU ZIP containing `FIRM.bin.enc`:

```text
py tools/recovery/recovery_iap_flash.py COM9 STOCK_G30_DRV126_SHU.zip
```

The recovery code validates the decrypted application vector before committing the pending update. After the stock application is installed, the SmartESC application-level 3-second recovery feature is naturally gone, because stock DRV126 does not contain it.

## 6. Last-resort recovery boundary

The 3-second recovery lives inside the SmartESC application. If the application cannot execute at all, that recovery mode cannot start.

The stock Ninebot bootloader at `0x08000000..0x08000FFF` is intentionally left untouched. At that point recovery must use an available stock IAP path, or ST-Link/SWD where physically accessible.

## Flash map

```text
0x08000000..0x08000FFF  stock Ninebot bootloader
0x08001000..0x0800E7FF  SmartESC application window, 54 KiB
0x0800E800..0x0801BFFF  stock IAP staging
0x0801C400                 SmartESC app config
0x0801C800                 SmartESC motor config
0x0801F800..0x0801FBFF  stock update control
0x0801FC00..0x0801FFFF  intentionally untouched
```

## First boot after flash

For the current development setup:

- use 24 V with current limiting
- keep the motor/wheel free
- connect VESC Tool 6.06 over PB6/PB7 if configuration is required
- use **Setup Motors FOC -> Run Detection (no CAN)** for an unknown Gen1/Gen2 G30 motor
- verify R/L/Flux before any high-power test

A successful flash is not the same thing as a road-qualified controller. Firmware, apparently, still refuses to obey optimism as an electrical specification.
