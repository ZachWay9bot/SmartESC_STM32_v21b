#!/usr/bin/env python3
"""Offline consistency verifier for G30 BENCH BIN + encrypted UART-IAP + JSON.

READ ONLY. Recomputes encryption of the candidate application; checks that
the manifest identifies these exact bytes. No serial/UART, no flash operation,
no bootloader modifications, and no claim of hardware motor validation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from make_shu_zip import MAX_APP_SIZE, ninebot_tea_encrypt, validate_app_image

STATUS = "BENCH_TEST_CANDIDATE_NOT_HARDWARE_VERIFIED"
FORMAT = "direct_encrypted_uart_iap_not_shu"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(image: Path, driver: Path, manifest: Path) -> dict:
    errors = []
    plain = image.read_bytes()
    encrypted = driver.read_bytes()
    try:
        metadata = json.loads(manifest.read_text())
        if not isinstance(metadata, dict):
            raise ValueError("expected object")
    except (ValueError, OSError) as exc:
        metadata = {}
        errors.append(f"Invalid manifest: {exc}")
    try:
        sp, reset = validate_app_image(plain)
    except ValueError as exc:
        sp = reset = None
        errors.append(f"Invalid plain application vector/size: {exc}")

    if len(encrypted) > MAX_APP_SIZE:
        errors.append("Encrypted UART-IAP payload exceeds staging limit")
    if len(encrypted) % 8:
        errors.append("Encrypted UART-IAP payload has invalid 8-byte alignment")

    expected_encrypted = ninebot_tea_encrypt(plain) if sp is not None else None
    if expected_encrypted is not None and encrypted != expected_encrypted:
        errors.append("Driver bytes do not match this BIN's NinebotTEA encoding")

    expected = {
        "status": STATUS,
        "packaging": FORMAT,
        "application_size_bytes": len(plain),
        "iap_driver_size_bytes": len(encrypted),
        "application_sha256": sha256(plain),
        "iap_driver_sha256": sha256(encrypted),
    }
    if sp is not None:
        expected["initial_stack_pointer"] = f"0x{sp:08X}"
        expected["reset_handler"] = f"0x{reset:08X}"

    for name, value in expected.items():
        if metadata.get(name) != value:
            errors.append(f"Manifest mismatch: {name}")

    return {
        "result": "PASS" if not errors else "FAIL",
        "verified_offline_only": True,
        "hardware_validated": False,
        "image_sha256": sha256(plain),
        "driver_sha256": sha256(encrypted),
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("driver", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    try:
        report = verify(args.image, args.driver, args.manifest)
    except OSError as exc:
        print(f"OFFLINE VERIFY FAIL: {exc}", file=sys.stderr)
        return 2
    output = json.dumps(report, indent=2) + "\n"
    print(output, end="")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(output)
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
