"""Read-only FO76 / SmartESC G30 IoT contract tests. Run with python -m unittest tools.tests.test_g30_fo76_iap_contract"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
CLI = (ROOT / "common_files/src/task_cli.c").read_text(encoding="utf-8")
IRQ = (ROOT / "g30p/Src/stm32f1xx_it.c").read_text(encoding="utf-8")
MAIN = (ROOT / "g30p/Src/main.c").read_text(encoding="utf-8")
IAP = (ROOT / "common_files/src/g30_recovery_iap.c").read_text(encoding="utf-8")
HDR = (ROOT / "common_files/src/g30_recovery_iap.h").read_text(encoding="utf-8")


class TestFo76IapContract(unittest.TestCase):
    def test_both_protocol_parsers_on_same_byte(self):
        rx = CLI.index("G30_IoT_GetByte()")
        n = CLI.index("G30Recovery_AppPushByte(rx_byte", rx)
        v = CLI.index("packet_process_byte(rx_byte, port->phandle)", rx)
        self.assertLess(rx, n)
        self.assertLess(n, v)
        self.assertNotIn("HAL_UART_Receive(port->uart, &rx_byte", CLI)
        self.assertIn("USART1_IRQHandler(void)", IRQ)
        self.assertIn("USART_CR1_RXNEIE", IRQ)
        self.assertLess(MAIN.index("G30_IoT_RxInit();"), MAIN.index("task_comm_init()"))

    def test_ninebot_parser_initialized_before_receive(self):
        self.assertLess(CLI.index("G30Recovery_AppInit();"), CLI.index("G30_IoT_GetByte()"))
        for name in ("G30Recovery_AppInit", "G30Recovery_AppPushByte", "G30Recovery_AppIapActive"):
            self.assertIn(name + "(", HDR)
            self.assertIn(name + "(", IAP)

    def test_existing_flash_map_is_not_changed(self):
        expected = {"REC_APP_BASE": "0x08001000u",
                    "REC_STAGING_BASE": "0x0800E800u",
                    "REC_STAGING_LIMIT": "0x0801C000u",
                    "REC_CONTROL": "0x0801F800u",
                    "REC_PAGE_SIZE": "0x400u",
                    "REC_MAX_DATA": "128u"}
        for name, value in expected.items():
            self.assertRegex(IAP, rf"#define\s+{name}\s+{re.escape(value)}")
        self.assertNotIn("0x0801FC00", IAP)

    def test_ninebot_frame_and_commands(self):
        for literal in ("0x5A", "0xA5", "~p->sum",
                        "uart_putc_rec(0x5A)", "uart_putc_rec(0xA5)",
                        "f->cmd==0x01u", "f->cmd==0x07u",
                        "f->cmd==0x08u", "f->cmd==0x09u", "f->cmd==0x0Au",
                        "0x0Bu", "if (f->dst!=0x20u) return;"):
            self.assertIn(literal, IAP)

    def test_staging_not_active_app_write(self):
        self.assertIn("flash_program_rec(REC_STAGING_BASE+abs,dec,8u)", IAP)
        self.assertIn("REC_STAGING_BASE+erase_len > REC_STAGING_LIMIT", IAP)

    def test_existing_motor_idle_gate_is_present(self):
        self.assertIn("g30_runtime_ready && PWM_Handle_M1._Super.PWM_off", CLI)
        self.assertIn("!s_app_flash_idle", IAP)
        # Static source test only. No assertion of atomic motor lock, IAP readiness or hardware safety.


if __name__ == "__main__":
    unittest.main(verbosity=2)
