# DeltaESC G30D v0.4 RC2

RC2 is a software-hardened release candidate built from the hardware-unvalidated
but CI-tested RC1 source.

> **Hardware status:** not yet validated on a real G30D motor controller.
> First motor test remains wheel-off-ground with ST-Link/SWD recovery and a
> verified full 128 KiB backup.

## Why RC2 exists

A deeper audit found several issues that a normal compile cannot detect:

1. The inherited SmartESC dashboard parser is an M365-style `55 AA` parser
   with a single address byte. G30 uses native Ninebot framing:
   `5A A5 LEN SRC DST CMD ARG payload[LEN] CRC16-LE`.
2. G30 configuration writes used pages 56/57, while inherited read paths and
   the G30 profile tail still used hard-coded pages 126/127.
3. SHU/manual recovery could request STAR before PWM was disabled.
4. The motor bridge could be re-enabled after boot/fault without requiring a
   fresh dashboard stream and neutral throttle.
5. A normal five-second button hold could enter destructive IAP recovery.

RC2 fixes all five classes.

## Native G30 dashboard path

RC2 keeps the legacy M365 parser untouched for M365 builds and adds a G30-only
stream parser on PA2/USART2.

Validated wire format:

```
5A A5 LEN SRC DST CMD ARG payload[LEN] CK_LO CK_HI
```

Properties:

- header: `5A A5`
- ESC address: `0x20`
- dashboard/BLE address: `0x21`
- checksum: inverted 16-bit sum from LEN through final payload byte
- parser expected body size: `LEN + 7`
- `0x64`: Ninebot head-I/O/display path
- `0x65`: G30 VESC-style throttle/brake control path
- established leading-control + throttle + brake layout is accepted
- compact two-byte throttle/brake payload is accepted as a compatibility path
- source, destination and checksum must all be valid before control data is used

Golden regression vectors are embedded in `tools/test_shu_preflight.py`.

## Drive interlock

G30 now boots with PWM high-Z. Propulsion is not armed until:

1. a checksum-valid G30 dashboard control frame has been received,
2. the stream is fresh,
3. there is no active motor-control fault, and
4. throttle has returned to neutral.

Link loss, a stale control stream or a fault disarms propulsion. Reconnection
requires neutral throttle again before PWM can resume.

## Configuration flash fix

Target-specific flash addresses are now derived from `APP_PAGE`,
`CONF_PAGE` and `PAGE_SIZE` for both reads and writes.

For G30:

- application config/profile page: 56 / `0x0800E000`
- motor config page: 57 / `0x0800E400`
- upper stock calibration/update-control flash is not used by DeltaESC config

Pages 56/57 are part of stock OTA staging/scratch space. Settings survive normal
reboots but may be erased by a firmware update, which is intentional and safer
than writing stock-reserved upper flash.

Flash erase/program return values are now checked. Compile-time assertions ensure
both configuration structs fit their pages.

## Recovery hardening

Automatic SHU handoff:

```
stationary + throttle neutral
-> torque zero
-> wait low Iq
-> PWM OFF
-> 20 ms
-> force STAR on PA15
-> relay settle
-> invalidate app vector
-> reset into preserved stock IAP
```

Manual recovery is deliberately harder to trigger:

- power button held for more than 10 seconds
- scooter stationary
- low Iq
- throttle neutral
- brake at least 80%

An ordinary very-long hold without that chord powers the scooter off instead of
invalidating the application vector.

## Deliberately unchanged

- Hall-sensored-only motor path
- no regenerative braking
- throttle release = true coast
- PA15 low = STAR, high = DELTA request
- PA12 active-low power button, PA11 power hold
- automatic STAR/DELTA disabled until both profiles are valid
- 64 MHz SmartESC motor-control timing
- preserved stock 4 KiB IAP bootloader
- 52 KiB reversible application window
- conservative initial current configuration

## Release gate

RC2 is releasable for bench hardware validation only after the unified gate
passes:

- source/preflight vectors
- G30P build
- binary vector/size validation
- SHU ZIP packaging
- M365 regression build
- Android protocol unit tests
- Android v0.4.0-rc2 APK build
- SHA-256 manifest for all deliverables

Road use remains out of scope until the real-controller validation matrix passes.
