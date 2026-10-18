# Firmware builds

Current firmware: **SmartESC G30 NativeDash v0.8.7**

The authoritative source is the default branch. GitHub Actions builds the G30 target and publishes BIN/ELF/MAP plus a ScooterHacking ZIPv3 package as workflow artifacts.

Reference CI build #87:

- FIRM.bin: 55240 bytes
- FIRM.bin.enc: 55248 bytes
- SHU ZIP SHA-256: `ca0a3e16b6089425160c867c3e259ae314158f6218acf20f110f8b3b2d809a8f`
- IAP Driver.bin SHA-256: `0fb3bc6d6800ed676c3a39845c8787a896b706e2b9fe1ef56815a651c24e584e`

Use the **Build G30 NativeDash on commit** or **Build G30 SHU candidate** workflow for reproducible current binaries.
