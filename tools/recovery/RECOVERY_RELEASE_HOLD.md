# SmartESC G30 v0.8.7: firmware release HOLD

The app includes a 3-second power-held UART recovery handler `G30Recovery_CheckAndRun()` before ADC, PWM and motor initialization. It supports CMD07/08/09/0A and does not contain FO91's hard-coded boot CRC or 128-KiB equality gate.

**But this recovery handler is stored in the replaceable application.** If the reset vector or early initialization fails, the service UART may not run. It is not an independent bootloader. The known potted G30-identical controller cannot be recovered with SWD.

The active IAP memory map assumes staging at `0x0800E800` and metadata at `0x0801F800`. ST factory-reported 64 KiB does not prove physically writable 128 KiB. Do not infer capacity from the device label.

## Fix in this branch

- `tools/recovery/release_qualification.py` verifies early recovery is before ADC/PWM, IAP frame guards remain, and no boot CRC/128-KiB hard lockout is introduced.
- `tools/make_shu_zip.py` runs that qualification in **release mode** before writing any flashable SHU; it fails closed if no real board-specific hardware evidence is supplied.
- `tools/recovery/test_release_qualification.py` runs negative tests including a missing real recovery log.
- `.github/workflows/g30-uart-recovery-audit.yml` executes these checks on PRs and the main SmartESC development branch.

**No qualification evidence has been supplied. This means no new SHU package is authorized or generated.**

The existing v0.8.7 BIN/ZIP are historical artifacts, NOT a qualified release for potted hardware. A successful model test or CI build does not establish an independent UART rescue route. Full stock-DRV restoration must be tested on the exact target board first.
