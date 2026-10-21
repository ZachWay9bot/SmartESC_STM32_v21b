# SmartESC G30: native VESC behavior + stock Ninebot dashboard (agreed 2026-10-21)

## Target
Use original VESC firmware behavior as the functional reference for motor control, VESC Tool motor setup/configuration, telemetry, and command semantics, subject to hardware support and firmware-size constraints. The stock G30 dashboard is an input/output adapter, NOT a replacement for VESC FOC control.

## Dataflow
- Original stock dashboard --> ESC: throttle, brake, heartbeat/connection messages; valid frame/CRC and source/destination checks.
- ESC --> stock dashboard: current speed in km/h and battery state, plus expected status (mode/light/fault) and protocol-specific replies, ACK and heartbeat as evidenced by captures from the stock firmware.
- UART service --> VESC Tool: normal VESC protocol semantics; motor R/L/flux Detect All may actively spin at rest.
- Normal driving: passive BEMF and rolling lock from ~3 km/h push, then throttle engages; **not** self-start from standstill.

## Confirmed in current source
- `common_files/src/app_uartcomm.c` uses `ninebot_parse`; accepts 0x61 / 0x64 / 0x65 dashboard lever frames (len >= 3), reads payload[1] throttle and payload[2] brake, resets command timeout.
- The same file replies to dashboard CMD64 with CMD64, containing mode, battery, light, beep, speed, fault code and checksum. This is *existing behavior*, not evidence that every required stock ACK/heartbeat is implemented.
- `common_files/src/ninebot.c` parses 5A A5 frames and validates complemented 16-bit additive checksum, not CRC16-CCITT.
- `common_files/src/VescCommand.c` G30 compact dispatcher omits VESC application configuration commands (GET_APPCONF/SET_APPCONF), default configuration and other standard VESC commands. This must be reconciled with VESC Tool compatibility.
- `common_files/src/app_uartcomm.c` uses `ADC_CTRL_TYPE_CURRENT_NOREV_BRAKE_ADC` to prioritize braking.

## Implementation / validation checklist
1. **VESC command parity**: enumerate required standard VESC Tool commands and check exact wire replies; implement only missing required messages with bounded packet processing and monitor binary size.
2. **Stock dashboard direction**: verify 0x61 / 0x64 / 0x65 command identities and throttle/brake payload offsets against captured original G30 traffic, Gen1/Gen2 where relevant.
3. **ACK and heartbeat**: capture stock controller ACK/heartbeat timing, frame types, command/argument and response behavior. Do not fabricate or blindly echo packets; distinguish a protocol ACK from the periodic CMD64 status response.
4. **ESC status**: validate km/h unit/scaling and zero speed, battery percent/source, light/mode/fault payload and checksum. Prefer real battery data, no invented SOC from raw voltage unless clearly specified.
5. **Link watchdog**: define and test throttle handling after dashboard silence and recovery when traffic resumes; braking priority unaffected.
6. **FOC setup**: motor parameter Detect All self-spins only within requested setup; normal ride start requires ~3 km/h push and throttle.
7. **Regression**: tests for valid/invalid dashboard frames, length/CRC, collision/half-duplex turnaround, heartbeat timeout/ACK behavior, disconnect; host VESC Tool 6.06 handshake and motor setup.
8. **Release**: controlled hardware tests; preserve FO7x-established IAP concept and leave bootloader/flash/recovery mechanisms unchanged absent separately approved change.

## Not assumed
No claim of full stock dashboard ACK coverage, no claim of full VESC Tool parity, no claim of a hardware-tested new firmware. The current source indicates CMD64 status response, but exact stock ACK requirements need captured traffic before changing behavior.
