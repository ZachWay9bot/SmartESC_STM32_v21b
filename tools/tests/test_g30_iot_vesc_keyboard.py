"""Source-level regression for the G30 IoT VESC keyboard control path.
The ARM build and physical motor verification remain separate requirements.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
G30 = lambda p: (ROOT / p).read_text(encoding="utf-8")


class G30IoTVescKeyboard(unittest.TestCase):
    def test_service_uart_is_iot(self):
        p = G30("common_files/inc/product.h").split("#else", 1)[0]
        self.assertRegex(p, r"#define\s+VESC_USART\s+USART1")
        self.assertRegex(p, r"#define\s+VESC_USART_DMA\s+huart1")
        self.assertRegex(p, r"#define\s+APP_USART_DMA\s+huart2")

    def test_early_recovery_call_preserved(self):
        s = G30("g30p/Src/main.c")
        self.assertIn("G30Recovery_CheckAndRun();", s)
        self.assertLess(s.index("G30Recovery_CheckAndRun();"), s.index("MX_USART1_UART_Init();"))

    def test_keyboard_commands_in_g30_dispatch(self):
        s = G30("common_files/src/VescCommand.c")
        g30 = s.split("static void commands_process_packet_g30(", 1)[1].split("\n#endif", 1)[0]
        for cmd in ("COMM_SET_CURRENT", "COMM_SET_DUTY", "COMM_SET_RPM",
                    "COMM_SET_CURRENT_REL", "COMM_SET_CURRENT_BRAKE",
                    "COMM_SET_HANDBRAKE", "COMM_APP_DISABLE_OUTPUT", "COMM_ALIVE"):
            with self.subTest(cmd=cmd):
                self.assertRegex(g30, r"case\s+" + cmd + r"\s*:")
        self.assertIn("VescToSTM_set_speed(buffer_get_int32", g30)
        self.assertIn("VescToSTM_set_current_rel", g30)

    def test_uart_task_is_usable_before_motor_runtime(self):
        main = G30("g30p/Src/main.c")
        cli = G30("common_files/src/task_cli.c")
        dispatch = G30("common_files/src/VescCommand.c")
        task = G30("common_files/src/task_init.c")
        self.assertIn("vTaskStartScheduler();", main)
        self.assertNotIn("vTaskSwitchContext();", main)
        self.assertLess(main.index("task_comm_init();"), main.index("vTaskStartScheduler();"))
        self.assertIn("HAL_UART_Receive(port->uart, &rx_byte, 1U, 1U)", cli)
        self.assertIn("HAL_UART_Transmit(port->uart, buf, len, 100U)", cli)
        self.assertIn("if (!g30_runtime_ready && packet_id != COMM_FW_VERSION) return;", dispatch)
        self.assertIn("volatile bool g30_runtime_ready = false;", task)
        self.assertIn("task_cli_init(&main_uart);", task)
        self.assertNotIn("task_cli_init(&iot_uart);", task)

    def test_reverse_only_same_rolling_direction_and_zero_coast(self):
        s = G30("common_files/src/VescToSTM.c")
        self.assertIn("G30Sensorless_M1.core.direction != g30_requested_direction", s)
        self.assertIn("if (!g30_drive_request_ok(erpm)) return;", s)
        self.assertIn("if (!g30_drive_request_ok(current)) return;", s)
        self.assertIn("VescToSTM_set_brake(0);", s)


if __name__ == "__main__":
    unittest.main()
