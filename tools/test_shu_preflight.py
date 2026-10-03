#!/usr/bin/env python3
"""Static/packaging preflight for the reversible G30 SHU build."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import struct
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_packager():
    path = ROOT / "tools" / "make_shu_zip.py"
    spec = importlib.util.spec_from_file_location("make_shu_zip", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def require_text(path: Path, needle: str) -> None:
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        raise AssertionError(f"{path}: missing expected text: {needle}")


def checksum16(data: bytes) -> int:
    total = sum(data) & 0xFFFF
    return (~total) & 0xFFFF


def test_layout() -> None:
    require_text(
        ROOT / "g30p" / "STM32CubeIDE" / "STM32F103C8TX_FLASH.ld",
        "ORIGIN = 0x08001000,   LENGTH = 52K",
    )
    require_text(
        ROOT / "g30p" / "Src" / "system_stm32f1xx.c",
        "#define VECT_TAB_OFFSET         0x00001000U",
    )
    product = ROOT / "common_files" / "inc" / "product.h"
    require_text(product, "#define APP_PAGE")
    require_text(product, "56")
    require_text(product, "#define CONF_PAGE")
    require_text(product, "57")
    require_text(product, "SESC_SHU_MAX_APP_BYTES")
    require_text(product, "(52u * 1024u)")


def test_bms_activator_source() -> None:
    product = ROOT / "common_files" / "inc" / "product.h"
    task_init = ROOT / "common_files" / "src" / "task_init.c"
    app_core = ROOT / "common_files" / "src" / "app.c"
    app_uart = ROOT / "common_files" / "src" / "app_uartcomm.c"

    require_text(product, "G30_BMS_ACTIVATOR_PERIOD_MS")
    require_text(product, "(200u)")
    require_text(
        task_init,
        "0x5A, 0xA5, 0x06, 0x20, 0x22, 0x30, 0x00, 0x00, 0x87, 0xFF, 0xFF",
    )
    require_text(task_init, "HAL_UART_Receive_DMA(&APP2_USART_DMA")
    require_text(task_init, "poll_regs[] = {0x32, 0x33, 0x34, 0x35, 0x30}")
    require_text(app_core, "g30_bms_init();")
    require_text(app_uart, "g30_bms_is_online()")
    require_text(app_uart, "g30_bms_get_soc()")

    # Activator checksum as used by the public Ninebot-BMS-Activator:
    # checksum covers 06 20 22 30 00 00 and is stored little-endian.
    activation_body = bytes([0x06, 0x20, 0x22, 0x30, 0x00, 0x00])
    assert checksum16(activation_body) == 0xFF87


def test_iap_start_vector() -> None:
    # Public G30 IAP example: size 33388 (0x826C), version 0x060D.
    # Old/public tooling convention uses LEN=8 (4 routing bytes + 4 payload).
    body = bytes([0x08, 0x3E, 0x20, 0x02, 0x07, 0x6C, 0x82, 0x0D, 0x06])
    chk = checksum16(body)
    frame = b"\x5A\xA5" + body + struct.pack("<H", chk)

    assert len(frame) == 13
    assert frame[:7] == bytes([0x5A, 0xA5, 0x08, 0x3E, 0x20, 0x02, 0x07])
    assert frame[7:11] == bytes([0x6C, 0x82, 0x0D, 0x06])

    src = ROOT / "common_files" / "src" / "app_uartcomm.c"
    require_text(src, "SHU_IAP_START_BODY_BYTES 11u")
    require_text(src, "shu_rx.body[0] == 4u || shu_rx.body[0] == 8u")
    require_text(src, "arg != 0x07u")
    require_text(src, "SESC_SHU_MAX_APP_BYTES")


def test_ninebottea_and_zip() -> None:
    pack = load_packager()

    plain = struct.pack("<II", 0x20005000, 0x08001001) + bytes(range(256)) * 4
    sp, reset = pack.validate_app_image(plain)
    assert sp == 0x20005000
    assert reset == 0x08001001

    enc = pack.ninebot_tea_encrypt(plain)
    # Regression vector captured after byte-for-byte comparison with the
    # public ScooterHacking NinebotTEA implementation.
    assert len(enc) == 1040
    assert enc[:16].hex() == "e442260569d928a71e88a4f51b0b75d3"
    assert hashlib.md5(enc).hexdigest() == "481406633bae0c36720d6201207c44d4"

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        fw = td / "g30p.bin"
        out = td / "SmartESC_G30_SHU_Coast_Delta.zip"
        fw.write_bytes(plain)

        old_argv = __import__("sys").argv
        try:
            __import__("sys").argv = [
                "make_shu_zip.py",
                str(fw),
                str(out),
            ]
            rc = pack.main()
        finally:
            __import__("sys").argv = old_argv

        assert rc == 0
        with zipfile.ZipFile(out, "r") as zf:
            assert set(zf.namelist()) == {
                "FIRM.bin",
                "FIRM.bin.enc",
                "info.json",
                "params.txt",
            }
            assert zf.read("FIRM.bin") == plain
            assert zf.read("FIRM.bin.enc") == enc
            info = json.loads(zf.read("info.json"))
            fwinfo = info["firmware"]
            assert info["schemaVersion"] == 1
            assert fwinfo["model"] == "max"
            assert fwinfo["type"] == "DRV"
            assert fwinfo["compatible"] == ["max_DRV_STM32F103CxT6"]
            assert fwinfo["encryption"] == "both"
            assert fwinfo["md5"]["bin"] == hashlib.md5(plain).hexdigest()
            assert fwinfo["md5"]["enc"] == hashlib.md5(enc).hexdigest()


def main() -> int:
    test_layout()
    test_bms_activator_source()
    test_iap_start_vector()
    test_ninebottea_and_zip()
    print("SHU preflight: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
