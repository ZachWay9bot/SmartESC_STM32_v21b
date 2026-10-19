# Firmware builds

> **DO NOT FLASH THESE HISTORICAL ARTIFACTS ON POTTED CONTROLLERS.** No independently verified serial restore exists for this exact SmartESC integration. All future SHU packaging is blocked pending test evidence.\n\n
Current firmware: **SmartESC G30 NativeDash v0.8.7**

The authoritative source is the default branch. GitHub Actions builds the G30 target and publishes BIN/ELF/MAP plus a ScooterHacking ZIPv3 package as workflow artifacts.

Reference CI build #87:

- FIRM.bin: 55240 bytes
- FIRM.bin.enc: 55248 bytes
- SHU ZIP SHA-256: `84e8e3187992a88046a75d519e64ed7cb27962605bffbe5a877a33652a6457c9`
- IAP Driver.bin SHA-256: `0fb3bc6d6800ed676c3a39845c8787a896b706e2b9fe1ef56815a651c24e584e`

Use the **Build G30 NativeDash on commit** or **Build G30 SHU candidate** workflow for reproducible current binaries.


## Published repository files

The versioned v0.8.7 binaries are committed directly under `firmware/v0.8.7/`.

Current repository-published hashes:

```text
84e8e3187992a88046a75d519e64ed7cb27962605bffbe5a877a33652a6457c9  SmartESC_G30_NativeDash_v0.8.7_SHU.zip
0fb3bc6d6800ed676c3a39845c8787a896b706e2b9fe1ef56815a651c24e584e  SmartESC_G30_NativeDash_v0.8.7_IAP_Driver.bin
```

The encrypted IAP payload is byte-identical to the validated build #87 payload. The ZIP hash changed when the SHU archive was reproducibly regenerated and committed because ZIP container metadata differs; firmware payload hashes remain the meaningful binary identity.
