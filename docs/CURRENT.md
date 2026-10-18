# Current G30 build

## SmartESC G30 NativeDash v0.8.7

This is the current primary firmware in this repository.

Firmware implementation merged by commit:

`b71510a994d88ebcf7395c459798327e9f20e01f`

Validated CI source head:

`194e62de7c93766d8e8d79131bbd6df3c9073bcd`

GitHub Actions reference:

**G30 SHU build #87 — 0 errors, 0 warnings**

Build outputs:

```text
FIRM.bin      55240 bytes
FIRM.bin.enc  55248 bytes

FIRM.bin MD5      11220d97b17f93580f7718ef6b1e2460
FIRM.bin.enc MD5  9d00d3c999c35f290315c555eec082f6
```

Known packaged test files from build #87:

```text
SHU ZIP SHA-256
ca0a3e16b6089425160c867c3e259ae314158f6218acf20f110f8b3b2d809a8f

IAP Driver.bin SHA-256
0fb3bc6d6800ed676c3a39845c8787a896b706e2b9fe1ef56815a651c24e584e
```

## Current feature set

- G30 sensorless FOC
- VESC Tool 6.06 connection over PB6/PB7
- R/L/Flux detection
- one-click FOC Detect All without CAN
- current-controller / observer parameter application
- native G30 `5A A5` dashboard framing
- original dashboard throttle and brake
- brake priority
- speed / battery / mode / light / beep / fault status reply
- 3-second application recovery path
- stock bootloader preserved

## Current validation target

Use the 24 V current-limited bench setup with the wheel free.

The exact v0.8.7 integration is still a bench candidate. Do not interpret CI success as road validation.

## Historical material

Old M365 targets, old serial-throttle experiments and the previous reference-document collection are in `legacy/`.
