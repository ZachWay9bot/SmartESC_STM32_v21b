#!/usr/bin/env python3
"""Fail-closed release gate for G30 SmartESC UART/SHU firmware.

Static inspection does not qualify hardware. For potted boards, a recovery
function inside the replaceable app is NOT an independent rescue path.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
GATE_PATTERNS = [
    r"boot_crc\s*==\s*0x5e597808",
    r"flash_kib\s*==\s*128\b",
    r"!\s*s->io\.compatible_boot\b",
]
REQUIRED = [
    "G30Recovery_CheckAndRun();",
    "MX_ADC1_Init();",
    "MX_TIM1_Init();",
]
FIELDS = ["board_profile", "bootloader_sha256", "physical_flash_geometry",
          "image_sha256", "stock_image_sha256", "restore_log_sha256",
          "entrypoint", "uart_wiring", "independent_rescue",
          "actual_restore_to_stock", "witness", "test_date"]
HEX = re.compile(r"^[0-9a-f]{64}$")


def static_check():
    errors = []
    src = (BASE/"common_files/src/g30_recovery_iap.c").read_text()
    main = (BASE/"g30p/Src/main.c").read_text()
    if any(p not in main for p in REQUIRED):
        errors.append("Early recovery or motor initialization anchors missing")
    else:
        # UART-first boot defers the motor's ADC/PWM setup into a FreeRTOS
        # task. Check the control-flow anchors in each function explicitly.
        runtime_start = main.find("static void G30_RuntimeInitTask(")
        main_start = main.find("int main(void)")
        task_body = main[runtime_start:main_start] if 0 <= runtime_start < main_start else ""
        boot_body = main[main_start:] if main_start >= 0 else ""
        runtime_sequence = ("MX_ADC1_Init();", "MX_TIM1_Init();", "MX_MotorControl_Init();")
        boot_sequence = ("G30Recovery_CheckAndRun();", "MX_USART1_UART_Init();",
                         "task_comm_init();", "xTaskCreate(G30_RuntimeInitTask",
                         "vTaskStartScheduler();")
        if (not task_body or not all(x in task_body for x in runtime_sequence) or
                not all(x in boot_body for x in boot_sequence) or
                not all(task_body.index(a) < task_body.index(b)
                        for a, b in zip(runtime_sequence, runtime_sequence[1:])) or
                not all(boot_body.index(a) < boot_body.index(b)
                        for a, b in zip(boot_sequence, boot_sequence[1:]))):
            errors.append("Power-button recovery no longer precedes deferred ADC/PWM startup")
    required_recovery = ("if (f->cmd==0x07u)", "if (f->cmd==0x08u)",
                         "if (f->cmd==0x09u)", "if (f->cmd==0x0Au)",
                         "REC_STAGING_BASE", "REC_CONTROL",
                         "if (!s_iap.finalized)", "REC_APP_BASE")
    for q in required_recovery:
        if q not in src:
            errors.append("Required guarded IAP control missing: " + q)
    for f in ("common_files/src/g30_recovery_iap.c", "g30p/Src/main.c"):
        text = (BASE/f).read_text()
        for pat in GATE_PATTERNS:
            if re.search(pat, text, re.I):
                errors.append(f + ": forbidden FO91-class CRC/size IAP gate " + pat)
    return errors


def check_hardware(path, image):
    if not path.is_file():
        return ["No independent physical restore evidence; do NOT package firmware"]
    try:
        d=json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return [f"Invalid evidence JSON: {e}"]
    errors=[f"Missing {k}" for k in FIELDS if d.get(k) in (None, "")]
    for k in ("bootloader_sha256","image_sha256","stock_image_sha256","restore_log_sha256"):
        if not HEX.fullmatch(str(d.get(k,""))):
            errors.append("Invalid SHA256 for "+k)
    if d.get("board_profile") != "G30_STM32F103_3CAP":
        errors.append("Wrong board profile")
    if image and (not image.is_file() or d.get("image_sha256")!=hashlib.sha256(image.read_bytes()).hexdigest()):
        errors.append("No proven restore for EXACT candidate image")
    if d.get("physical_flash_geometry") != "128K_VERIFIED":
        errors.append("0x0800E800/0x0801F800 require physically verified >=128KiB")
    if d.get("independent_rescue") is not True:
        errors.append("3-second application recovery is NOT independent")
    if d.get("actual_restore_to_stock") is not True:
        errors.append("Actual return to correct stock DRV not demonstrated")
    return errors


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--release",action="store_true")
    ap.add_argument("--evidence",type=Path,default=BASE/"evidence/G30_PHY_UART_STOCK_RESTORE.json")
    ap.add_argument("--image",type=Path)
    args=ap.parse_args()
    errors=static_check()
    if args.release:
        errors += check_hardware(args.evidence,args.image)
    if errors:
        for e in errors: print("BLOCKED:",e,file=sys.stderr)
        return 1
    print("PASS: early power recovery, guarded IAP, no FO91 hardcoded lockout")
    if not args.release: print("SOURCE AUDIT ONLY, NO FLASH RELEASE")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
