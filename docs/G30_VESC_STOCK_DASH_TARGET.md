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

## Implemented in development branch (2026-10-21, unbuilt)
- Compact G30 VESC dispatcher now replies to `COMM_GET_MCCONF_DEFAULT`, `COMM_GET_APPCONF`, `COMM_GET_APPCONF_DEFAULT` using existing upstream serialization and defaults.
- Added minimum length checks before reading 4-byte `COMM_SET_CURRENT` / `COMM_SET_CURRENT_BRAKE` and `COMM_GET_VALUES_SELECTIVE` data and the 4-byte `COMM_SET_MCCONF` signature. **This does not make deserialization fully bounded.**
- `COMM_SET_APPCONF` is *not* implemented in G30 compact dispatch yet: existing `confgenerator_deserialize_appconf()` has no input length and writing full app settings needs dashboard-control preservation and packet-bound checks before use.
- Stock dashboard parser, status response, CMD64 timing/ACK, IAP, bootloader, recovery and motor control remain **unchanged**.
- No CI build or bench validation performed for these changes. There must be no candidate flash image until compile/link and regression tests have passed.

## Point 1: VESC Tool application configuration write (2026-10-21)
- G30 compact dispatcher now implements `COMM_SET_APPCONF`, alongside GET_APPCONF and default configuration reads.
- VESC 6.06 generated serializer and decoder each use **476 bytes** including reserved fields. Reject payloads with any other length before invoking the legacy length-unaware decoder.
- Decode into a separate allocated copy and preserve the original stock dashboard app selection, ADC control mode, VESC service-UART baud rate and shutdown mode. Check ADC mapping and update rate before applying and storing. Send ACK only on a successful store.
- Static regression test: `python3 -m unittest discover -s tools/tests -p 'test_g30_appconf_contract.py'`.
- **Status:** Implemented and source-reviewed on development branch. Full firmware build and actual VESC Tool write/readback still untested. No BIN issued. Dashboard framing and FO7x IAP/recovery untouched.

## Point 2: stock G30 dashboard / ACK / heartbeat (2026-10-21)
- Historical stock-capture analysis (October 18) recorded approximately 199 dashboard CMD64 requests and 199 matching ESC CMD64 replies across ~20 seconds, plus ~797 dashboard CMD65 packets. Historical CMD65 payload example: `04 29 23 02 00` (throttle `0x29` and brake `0x23` at offsets 1/2). Historical notes are evidence of the frame families, but **not** a live test of this firmware.
- The existing implementation already replies **once to each valid CMD64 frame** with **CMD64**, using source ESC `0x20` and destination dash `0x21`, and its six status bytes: mode, battery, light, beep, speed, fault. CMD65 lever packets do not trigger a separate extra response.
- ACK clarification: the CMD64 status response acknowledges the dashboard's CMD64 heartbeat/round trip in the known traces. **A distinct ACK opcode is not confirmed**; do not invent CMD65 reply or periodic unsolicited frames based on the generic G30DashLib demonstration, which is explicitly a simplified simulator and not stock-accurate.
- Frame integrity is validated using 16-bit **ones-complement additive checksum** over bytes beginning with LENGTH (not CRC-CCITT). Header `5A A5`.
- **Change on branch:** before populating the existing CMD64 response, sanitize non-finite speed and battery estimates and clamp to documented display-byte ranges. Ordinary finite behavior, layout, checksum, original throttle/brake mapping and CMD64 timing are unchanged.
- **Host regression test:** `python3 -m unittest discover -s tools/tests -p 'test_g30_dash_protocol.py'`. Compiles and runs the actual `ninebot.c` parser/CRC code (requires a C compiler), tests a historical CMD65 payload, malformed checksum, and a native CMD64 request and status reply.
- **Not yet verified:** live Dash↔SmartESC UART trace, acknowledgement latency, display reaction, original dashboard variants, and BMS-based battery SOC. Battery percentage currently uses the VESC controller battery-voltage estimate, not a proven Ninebot BMS SoC feed. No new heartbeat watchdog or link lockouts introduced.
- No changes to IAP, flash layout, bootloader, recovery, FOC motor control, or start conditions.
