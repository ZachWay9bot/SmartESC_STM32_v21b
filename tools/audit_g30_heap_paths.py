#!/usr/bin/env python3
"""Read-only G30 FreeRTOS allocation-path inventory.

Reports missing checks in known C paths WITHOUT editing firmware, bootloader,
recovery, motor fault policy, or any UART behavior. Absence of a simple guard
is a review finding, not proof that a specific real heap exhaustion occurs.
This does not measure actual FreeRTOS available heap or stack watermarks.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "packet": "common_files/src/packet.c",
    "dashboard": "common_files/src/app_uartcomm.c",
    "vesc": "common_files/src/VescCommand.c",
}
CHECKS = (
    ("packet_state", "packet", "packet_init", "ret",
     "pvPortMalloc(sizeof(PACKET_STATE_t))", "memset(ret, 0",
     "VESC packet state: dereference after allocation"),
    ("packet_rx_buffer", "packet", "packet_init", "ret->rx_buffer",
     "pvPortMalloc(BUFFER_LEN)", "return ret;",
     "VESC packet receive buffer: returned without allocation check"),
    ("dashboard_uart_rx", "dashboard", "task_app", "usart_rx_dma_buffer",
     "pvPortMalloc(port->rx_buffer_size)", "HAL_UART_Receive_DMA(",
     "Dashboard UART DMA target: allocation used by HAL"),
    ("vesc_send_mcconf", "vesc", "commands_send_mcconf", "send_buffer",
     "pvPortMalloc(512 + PACKET_HEADER)", "memset(send_buffer,0",
     "VESC MCCONF response buffer"),
    ("vesc_send_appconf", "vesc", "commands_send_appconf", "send_buffer",
     "pvPortMalloc(512 + PACKET_HEADER)", "memset(send_buffer,0",
     "VESC APPCONF response buffer"),
)
TASK_CHECKS = (
    ("dashboard_task_create", "dashboard", "task_app_init",
     "xTaskCreate(task_app", "task creation result used by dashboard"),
    ("detect_task_create", "vesc", "commands_process_packet_g30",
     "xTaskCreate(g30_detect_worker", "Detect All worker task creation"),
)


def function_span(source: str, name: str) -> tuple[int, int]:
    pattern = r"\b" + re.escape(name) + r"\s*\([^;]*?\)\s*\{"
    match = re.search(pattern, source, re.S)
    if not match:
        raise ValueError(f"Expected function missing: {name}")
    pos = match.end() - 1
    level = 0
    for index in range(pos, len(source)):
        if source[index] == "{":
            level += 1
        elif source[index] == "}":
            level -= 1
            if not level:
                return pos, index + 1
    raise ValueError(f"Expected function unterminated: {name}")


def has_null_guard(snippet: str, var: str) -> bool:
    escaped = re.escape(var)
    pattern = r"\bif\s*\(\s*(?:!\s*" + escaped + r"\b|" + escaped + r"\s*==\s*(?:NULL|0))"
    return re.search(pattern, snippet) is not None


def audit(sources: dict[str, str] | None = None) -> dict:
    if sources is None:
        sources = {k: (ROOT / path).read_text() for k, path in FILES.items()}
    paths = []
    for ident, key, function, var, alloc, first_use, meaning in CHECKS:
        source = sources[key]
        a, b = function_span(source, function)
        body = source[a:b]
        pos = body.find(alloc)
        use = body.find(first_use, pos + len(alloc))
        if pos < 0 or use < 0:
            raise ValueError(f"Expected allocation/use missing: {ident}")
        checked = has_null_guard(body[pos + len(alloc):use], var)
        paths.append({
            "id": ident, "source": FILES[key], "function": function,
            "line": source.count("\n", 0, a + pos) + 1,
            "guarded_before_use": checked, "description": meaning,
        })
    for ident, key, function, call, meaning in TASK_CHECKS:
        source = sources[key]
        a, b = function_span(source, function)
        body = source[a:b]
        pos = body.find(call)
        if pos < 0:
            raise ValueError(f"Expected task creation missing: {ident}")
        # The two known call patterns differ: Detect All checks !=pdPASS
        # immediately, dashboard calls xTaskCreate but ignores the return.
        line = body[pos:body.find(";", pos) + 1]
        checked = "pdPASS" in line or "pdFAIL" in line
        paths.append({
            "id": ident, "source": FILES[key], "function": function,
            "line": source.count("\n", 0, a + pos) + 1,
            "guarded_before_use": checked, "description": meaning,
        })
    return {
        "kind": "source_only_g30_allocation_review",
        "not_runtime_measurement": True,
        "known_paths_examined": len(paths),
        "unguarded_paths": [item["id"] for item in paths if not item["guarded_before_use"]],
        "paths": paths,
        "limitations": (
            "Fixed source-pattern review only; FreeRTOS runtime fragmentation, "
            "heap watermark and task stack high-water marks are unknown. "
            "G30 bench has no dashboard, but dashboard code is retained."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    report = audit()
    rendered = json.dumps(report, indent=2) + "\n"
    print(rendered, end="")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
