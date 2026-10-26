# FO76/v0.4.8 to SmartESC v21b: communication restoration gate (2026-10-26)

## Scope
Develop only on the 3-Cap with ST-Link as emergency rollback; NEVER flash the epoxy-potted XBOT without verified IoT rollback. Do not modify bootloader, IAP flash map, current limits, braking, or regeneration without explicit approval.

## User-supplied source of truth
Archive `XBOT_VESC_BRIDGE_v0.4.8_FO76_DRIVE_PROFILE.zip`, specifically `SOURCE/src/main.c`, `SOURCE/src/iap.c`, `SOURCE/DRV126_IAP_REFERENCE.md`, and `README_FIRST.txt`.

The previous implementation reads one USART1 byte and feeds **both** parsers:
```c
int c = uart1_getc();
if (c >= 0) {
    uint8_t ub = (uint8_t)c;
    if (nb_parser_push(ub, &f)) dispatch(&f);
    (void)vesc_parser_push(ub);
}
```
It has live in-app Ninebot IAP, not only boot-time recovery. Reference commands: 0x07 BEGIN, 0x08 WRITE, 0x09 FINALIZE, 0x0A RESET, 0x0B ACK, at 115200 8N1 on IoT PB6/PB7. Auto-detect remains the separate frozen `!vesc_drive_active` path. The FO7x handover is documented near step 195..201, OPEN iq=28 and CLOSED iq=24; v0.4.8 itself is not established as fully driving on hardware.

## Confirmed BENCH-314 regression
- User reports no VESC Tool, no NinebotIAPFlasher and steady green LED after flashing BENCH-314 on the 3-Cap.
- `common_files/src/task_cli.c` G30 RX loop sends bytes **only** to `packet_process_byte`, not to the Ninebot parser.
- `g30p/Src/main.c` runs `G30Recovery_CheckAndRun()` before starting the VESC task.
- `common_files/src/g30_recovery_iap.c` requires a 3-second PWR_BTN high at boot and then runs its own polling loop. This is NOT the previous always-available in-app IAP.
- The green CI (ARM build and host tests) is not hardware proof. BENCH-314 is NOT a valid release.

## Engineering tasks before the next flash
1. Integrate the FO76 Ninebot framing/IAP state machine with the existing VESC UART RX loop, using ONE physical USART1 byte consumer and TWO parsers.
2. Preserve bootloader, application/staging boundaries, persistent pages, and recovery semantics. Do not silently change any IAP behavior; obtain explicit approval before implementing flash-write changes.
3. Add host tests for interleaved VESC and Ninebot traffic, both reply formats, CRC errors, mock-flash IAP begin/write/finalize and rollback.
4. Reuse frozen FO76 auto-detect behavior without substituting an untested MCSDK detection algorithm.
5. Only then review FWD/RWD and sensorless observer, phase order and current sensing.
6. Hardware gate on 3-Cap: VESC connect -> values/config -> Ninebot identification -> detect all -> no-load FWD/RWD -> demonstrated IoT IAP return.

**No new firmware is authorized or declared READY by this document. ST-Link is the rollback path, not a debugging requirement.**
