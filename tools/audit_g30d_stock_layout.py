#!/usr/bin/env python3
"""Read-only G30P source audit. Never modifies or flashes firmware.
Usage: python3 tools/audit_g30d_stock_layout.py .
Exit 1 on known stock-IAP incompatibility.
"""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
ld = root / "g30p/STM32CubeIDE/STM32F103C8TX_FLASH.ld"
cfg = root / "common_files/inc/product.h"
pins = root / "g30p/Inc/main.h"
mc = root / "common_files/src/mc_tasks.c"
required = (ld, cfg, pins, mc)
missing = [str(p) for p in required if not p.exists()]
if missing:
    print("ERROR: missing source files:", ", ".join(missing))
    sys.exit(2)

linker = ld.read_text(errors="replace")
config = cfg.read_text(errors="replace")
pindefs = pins.read_text(errors="replace")
motor = mc.read_text(errors="replace")
match = re.search(
    r"FLASH\s*\(rx\)\s*:\s*ORIGIN\s*=\s*(0x[0-9a-fA-F]+)\s*,\s*LENGTH\s*=\s*(\d+)K",
    linker,
)
if not match:
    print("ERROR: cannot parse FLASH region")
    sys.exit(2)
origin, capacity = int(match.group(1), 16), int(match.group(2)) * 1024
g30 = config.split("#ifdef G30P", 1)[-1].split("#endif", 1)[0]
pages = {
    name: int(num) for name, num in re.findall(
        r"#define\s+(APP_PAGE|CONF_PAGE)\s+(\d+)", g30
    )
}
print("Origin:", hex(origin), "| flash allocation:", capacity, "bytes")
print("G30P APP_PAGE/CONF_PAGE:", pages)
pwm = all(name in pindefs for name in (
    "M1_PWM_UH_Pin", "M1_PWM_VH_Pin", "M1_PWM_WH_Pin",
    "M1_PWM_UL_Pin", "M1_PWM_VL_Pin", "M1_PWM_WL_Pin",
))
current = all(name in pindefs for name in (
    "M1_CURR_AMPL_U_Pin", "M1_CURR_AMPL_V_Pin", "M1_CURR_AMPL_W_Pin",
))
hall = "HALL_CalcElAngle" in motor
print("G30P PWM pins defined:", pwm)
print("G30P phase-current pins defined:", current)
print("G30P motor task requires Hall:", hall)

stock_unsafe = False
if origin != 0x08001000:
    print("FAIL stock bootloader: linker is NOT relocated to stock app start")
    stock_unsafe = True
if capacity > 55296:
    print("FAIL stock app region: allocation exceeds 55,296-byte slot")
    stock_unsafe = True
if 126 in pages.values() or 127 in pages.values():
    print("FAIL stock update metadata: SmartESC config pages overlap controlblocks")
    stock_unsafe = True
if hall:
    print("FAIL sensorless: current position feedback still uses Hall sensors")
    stock_unsafe = True
print("RESULT:", "INCOMPATIBLE / DO NOT FLASH" if stock_unsafe else
      "PATTERN CHECK ONLY / NOT A FLASH APPROVAL")
sys.exit(1 if stock_unsafe else 0)
