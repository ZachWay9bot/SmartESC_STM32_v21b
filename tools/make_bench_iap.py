#!/usr/bin/env python3
"""Prepare an encrypted BENCH UART-IAP Driver.bin, without a dashboard/SHU ZIP.

Uses exactly the same existing vector/bounds validation and NinebotTEA
encryption as make_shu_zip.py; does not change or invoke any IAP/flash code.
The file is a *test candidate*, not a verified safe-to-flash release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from make_shu_zip import MAX_APP_SIZE, ninebot_tea_encrypt, validate_app_image


def make_driver(plain: bytes) -> tuple[bytes, int, int]:
    initial_sp, reset_handler = validate_app_image(plain)
    encrypted = ninebot_tea_encrypt(plain)
    if len(encrypted) > MAX_APP_SIZE:
        raise ValueError(
            f"encrypted UART-IAP image is {len(encrypted)} bytes, "
            f"staging supports at most {MAX_APP_SIZE} bytes"
        )
    return encrypted, initial_sp, reset_handler


def main() -> int:
    parser = argparse.ArgumentParser(description="G30 BENCH UART-IAP Driver.bin (no SHU ZIP)")
    parser.add_argument("image", type=Path, help="linked application .bin from g30p/Debug")
    parser.add_argument("output", type=Path, help="encrypted IAP Driver.bin output")
    parser.add_argument("--manifest", type=Path, help="write build checksums and vector metadata")
    opts = parser.parse_args()

    plain = opts.image.read_bytes()
    driver, stack, reset = make_driver(plain)
    if opts.output.resolve() == opts.image.resolve():
        raise ValueError("output must not overwrite the unencrypted application BIN")
    opts.output.parent.mkdir(parents=True, exist_ok=True)
    opts.output.write_bytes(driver)
    report = {
        "status": "BENCH_TEST_CANDIDATE_NOT_HARDWARE_VERIFIED",
        "packaging": "direct_encrypted_uart_iap_not_shu",
        "format": "same NinebotTEA as tools/make_shu_zip.py",
        "application_size_bytes": len(plain),
        "iap_driver_size_bytes": len(driver),
        "application_sha256": hashlib.sha256(plain).hexdigest(),
        "iap_driver_sha256": hashlib.sha256(driver).hexdigest(),
        "initial_stack_pointer": f"0x{stack:08X}",
        "reset_handler": f"0x{reset:08X}",
        "note": "Only binary packaging was performed; no UART flash or hardware validation.",
    }
    print(json.dumps(report, indent=2))
    if opts.manifest:
        opts.manifest.parent.mkdir(parents=True, exist_ok=True)
        opts.manifest.write_text(json.dumps(report, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
