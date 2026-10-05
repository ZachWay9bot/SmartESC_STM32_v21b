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


def forbid_text(path: Path, needle: str) -> None:
    text = path.read_text(encoding="utf-8")
    if needle in text:
        raise AssertionError(f"{path}: forbidden text still present: {needle}")


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


def test_g30_config_protocol() -> None:
    app_uart = ROOT / "common_files" / "src" / "app_uartcomm.c"
    conf_h = ROOT / "common_files" / "src" / "conf_general.h"
    conf_c = ROOT / "common_files" / "src" / "conf_general.c"
    delta = ROOT / "common_files" / "src" / "task_LED.c"

    require_text(conf_h, "G30_CONFIG_MAGIC")
    require_text(conf_h, "g30_foc_profile_t")
    require_text(conf_h, "G30_CFG_FLAG_STAR_VALID")
    require_text(conf_h, "G30_CFG_FLAG_DELTA_VALID")
    require_text(conf_h, "G30_CFG_FLAG_AUTO_DELTA")

    require_text(conf_c, "G30_CONFIG_FLASH_ADDR")
    require_text(conf_c, "_Static_assert(sizeof(app_configuration) + sizeof(g30_sesc_config_t) <= PAGE_SIZE")
    require_text(conf_c, "g30_config_apply_runtime_profile")
    require_text(conf_c, "PIDIqHandle_M1.wIntegralTerm = 0")
    require_text(conf_c, "PIDIdHandle_M1.wIntegralTerm = 0")

    require_text(app_uart, "#define SESC_CFG_CMD                 0x7Du")
    require_text(app_uart, "SESC_CFG_DETECT")
    require_text(app_uart, "tune_foc_measure_r_l_imax")
    require_text(app_uart, "tune_foc_measure_flux_linkage_openloop")
    require_text(app_uart, "tune_mcpwm_foc_hall_detect")
    require_text(app_uart, "sesc_detect_restore_original")
    require_text(app_uart, "(delta && !g30_config_profile_valid(false))")

    require_text(delta, "g30_config_auto_delta_enabled()")
    require_text(delta, "g30_config_apply_runtime_profile(delta_target)")
    require_text(delta, "cfg->relay_settle_ms")



def test_g30_gen1_rc_safety() -> None:
    main_h = ROOT / "g30p" / "Inc" / "main.h"
    main_c = ROOT / "g30p" / "Src" / "main.c"
    product = ROOT / "common_files" / "inc" / "product.h"
    app_uart = ROOT / "common_files" / "src" / "app_uartcomm.c"
    pwr = ROOT / "common_files" / "src" / "task_pwr.c"
    conf = ROOT / "common_files" / "src" / "conf_general.c"

    # G30 Gen1 hardware mapping reconstructed from stock DRV firmware.
    require_text(main_h, "#define PWR_BTN_Pin GPIO_PIN_12")
    require_text(main_h, "#define PWR_BTN_GPIO_Port GPIOA")
    require_text(main_c, "GPIO_InitStruct.Pull = GPIO_PULLUP;")
    require_text(product, "#define DELTA_RELAY_GPIO_Port")
    require_text(product, "LED_GPIO_Port")
    require_text(product, "#define DELTA_RELAY_Pin")
    require_text(product, "LED_Pin")

    # Both recovery paths must force STAR on PA15, never on legacy PB9.
    require_text(
        app_uart,
        "HAL_GPIO_WritePin(DELTA_RELAY_GPIO_Port, DELTA_RELAY_Pin, GPIO_PIN_RESET);",
    )
    require_text(
        pwr,
        "HAL_GPIO_WritePin(DELTA_RELAY_GPIO_Port, DELTA_RELAY_Pin, GPIO_PIN_RESET);",
    )
    forbid_text(
        app_uart,
        "HAL_GPIO_WritePin(BRAKE_LIGHT_GPIO_Port, BRAKE_LIGHT_Pin, GPIO_PIN_RESET);",
    )

    # Active-low G30 power button must not block shutdown waiting for a press.
    require_text(pwr, "#ifdef G30P")
    require_text(
        pwr,
        "HAL_GPIO_WritePin(TPS_ENA_GPIO_Port, TPS_ENA_Pin, GPIO_PIN_RESET);",
    )
    require_text(pwr, "stable_pressed = (last_raw == GPIO_PIN_RESET);")
    require_text(pwr, "LONG_PRESS_MILLIS_MAX \t= 10000;")
    require_text(pwr, "app_adc_get_decoded_level2() >= 0.80f")
    require_text(pwr, "very_long_sent = true")

    # RC remains sensored-only and automatic DELTA starts disabled.
    require_text(conf, "mcconf->foc_sensor_mode = FOC_SENSOR_MODE_HALL;")
    require_text(conf, "g30_cfg.flags = 0;")

    # Stock G30 motor reconstruction uses 15 pole pairs. SmartESC's
    # si_motor_poles field is used as a pole-pair divisor in speed conversion.
    require_text(product, "#define POLE_PAIR_NUM                                                     (uint8_t)15")
    require_text(product, "#define MCCONF_SI_MOTOR_POLES                                                15")




def test_g30_dashboard_protocol() -> None:
    src = ROOT / "common_files" / "src" / "app_uartcomm.c"
    text = src.read_text(encoding="utf-8")

    # Native G30 framing is deliberately separate from the legacy M365 55 AA parser.
    require_text(src, "#define G30_DASH_HEADER0                0x5Au")
    require_text(src, "#define G30_DASH_HEADER1                0xA5u")
    require_text(src, "#define G30_DASH_ADDR_ESC               0x20u")
    require_text(src, "#define G30_DASH_ADDR_BLE               0x21u")
    require_text(src, "#define G30_DASH_CMD_STATUS             0x64u")
    require_text(src, "#define G30_DASH_CMD_CONTROL            0x65u")
    require_text(src, "const uint16_t expected = (uint16_t)b + 7u;")
    require_text(src, "g30_dash_feed_byte(usart_rx_dma_buffer[rd_ptr])")
    require_text(src, "g30_control_seen")
    require_text(src, "g30_control_armed")
    require_text(src, "G30_CONTROL_RX_TIMEOUT_MS")
    require_text(src, "app_adc_get_decoded_level() > 0.02f")

    # Stock-format 0x64 display update:
    # 5A A5 LEN SRC DST CMD ARG mode batt light beep speed fault CKlo CKhi
    status = bytes([
        0x5A, 0xA5, 0x06, 0x20, 0x21, 0x64, 0x00,
        0x04, 0x64, 0x00, 0x00, 0x19, 0x00,
    ])
    ck = checksum16(status[2:])
    assert ck == 0xFED3
    assert status + struct.pack("<H", ck) == bytes([
        0x5A, 0xA5, 0x06, 0x20, 0x21, 0x64, 0x00,
        0x04, 0x64, 0x00, 0x00, 0x19, 0x00, 0xD3, 0xFE,
    ])

    # Established G30 bridge 0x65 control layout: leading control byte,
    # then raw throttle/brake.  LEN is payload count, so total is LEN + 9.
    control = bytes([
        0x5A, 0xA5, 0x03, 0x21, 0x20, 0x65, 0x00,
        0x04, 0x80, 0x10,
    ])
    ck = checksum16(control[2:])
    assert ck == 0xFEC2
    assert len(control + struct.pack("<H", ck)) == 12

    # Compatible compact two-byte throttle/brake payload is accepted as well.
    compact = bytes([
        0x5A, 0xA5, 0x02, 0x21, 0x20, 0x65, 0x00,
        0x80, 0x10,
    ])
    ck = checksum16(compact[2:])
    assert ck == 0xFEC7
    assert len(compact + struct.pack("<H", ck)) == 11

    # Older/stock-style Ninebot head-I/O trace. The request uses CMD 0x64
    # and carries leading-control/throttle/brake bytes; checksum is known.
    head_io = bytes([
        0x5A, 0xA5, 0x07, 0x21, 0x20, 0x64, 0x00,
        0x06, 0x2A, 0x29, 0x00, 0x00, 0x07, 0x01,
    ])
    ck = checksum16(head_io[2:])
    assert ck == 0xFEF2
    assert head_io + struct.pack("<H", ck) == bytes([
        0x5A, 0xA5, 0x07, 0x21, 0x20, 0x64, 0x00,
        0x06, 0x2A, 0x29, 0x00, 0x00, 0x07, 0x01, 0xF2, 0xFE,
    ])
    require_text(src, "g30_dash_accept_control(payload, len);")


def test_recovery_order_and_drive_interlock() -> None:
    app_uart = (ROOT / "common_files" / "src" / "app_uartcomm.c").read_text(encoding="utf-8")
    task_pwr = (ROOT / "common_files" / "src" / "task_pwr.c").read_text(encoding="utf-8")
    conf = ROOT / "common_files" / "src" / "conf_general.c"
    led = ROOT / "common_files" / "src" / "task_LED.c"

    # Automatic SHU handoff must go high-Z before changing DELTA -> STAR.
    start = app_uart.index("static void shu_handoff_to_stock_iap")
    end = app_uart.index("/*\n * SmartESC G30 companion-app protocol", start)
    handoff = app_uart[start:end]
    assert handoff.index("VescToSTM_pwm_stop();") < handoff.index(
        "HAL_GPIO_WritePin(DELTA_RELAY_GPIO_Port, DELTA_RELAY_Pin, GPIO_PIN_RESET);"
    )
    require_text(
        ROOT / "common_files" / "src" / "app_uartcomm.c",
        "vTaskDelay(MS_TO_TICKS(g30_config_get()->relay_settle_ms));",
    )

    # Manual recovery follows the same ordering.
    start = task_pwr.index("case VERY_LONG_PRESS")
    end = task_pwr.index("case DOUBLE_PRESS", start)
    recovery = task_pwr[start:end]
    assert recovery.index("VescToSTM_pwm_stop();") < recovery.index(
        "HAL_GPIO_WritePin(DELTA_RELAY_GPIO_Port, DELTA_RELAY_Pin, GPIO_PIN_RESET);"
    )

    # Boot and fault recovery remain high-Z until fresh neutral dashboard input.
    require_text(conf, "MCI_StartMotor(pMCI[M1]);")
    require_text(conf, "VescToSTM_pwm_stop();")
    require_text(led, "Do not energize the bridge merely because a fault was")
    require_text(led, "VescToSTM_pwm_stop();")




def test_config_flash_symmetry() -> None:
    conf = ROOT / "common_files" / "src" / "conf_general.c"
    text = conf.read_text(encoding="utf-8")

    require_text(conf, "#define APP_CONFIG_FLASH_ADDR")
    require_text(conf, "((uint32_t)APP_PAGE * (uint32_t)PAGE_SIZE)")
    require_text(conf, "#define MC_CONFIG_FLASH_ADDR")
    require_text(conf, "((uint32_t)CONF_PAGE * (uint32_t)PAGE_SIZE)")
    require_text(conf, "APP_CONFIG_FLASH_ADDR + ((x / 4u) * 4u)")
    require_text(conf, "MC_CONFIG_FLASH_ADDR + ((x / 4u) * 4u)")
    require_text(
        conf,
        "#define G30_CONFIG_FLASH_ADDR (APP_CONFIG_FLASH_ADDR + PAGE_SIZE - sizeof(g30_sesc_config_t))",
    )
    require_text(conf, "_Static_assert(sizeof(app_configuration) <= PAGE_SIZE")
    require_text(conf, "_Static_assert(sizeof(mc_configuration) <= PAGE_SIZE")
    require_text(conf, "HAL_FLASHEx_Erase(&s_eraseinit, &page_error) != HAL_OK")
    require_text(conf, "HAL_FLASH_Program(FLASH_TYPEPROGRAM_WORD")
    forbid_text(conf, "ADDR_FLASH_PAGE_126")
    forbid_text(conf, "ADDR_FLASH_PAGE_127")

    # Writes must use the same target-specific page macros read above.
    require_text(conf, "conf_general_write_flash(APP_PAGE")
    require_text(conf, "conf_general_write_flash(CONF_PAGE")



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
    test_g30_config_protocol()
    test_g30_gen1_rc_safety()
    test_g30_dashboard_protocol()
    test_recovery_order_and_drive_interlock()
    test_config_flash_symmetry()
    test_iap_start_vector()
    test_ninebottea_and_zip()
    print("SHU preflight: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
