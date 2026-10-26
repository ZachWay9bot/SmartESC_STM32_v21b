#!/usr/bin/env python3
"""G30 3-Cap port routing regression. Source inspection only, no UART or flash."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
PRODUCT = (ROOT / "common_files/inc/product.h").read_text()
TASK = (ROOT / "common_files/src/task_init.c").read_text()
MAIN = (ROOT / "g30p/Src/main.c").read_text()
MSP = (ROOT / "g30p/Src/stm32f1xx_hal_msp.c").read_text()
REC = (ROOT / "common_files/src/g30_recovery_iap.c").read_text()
G30 = PRODUCT.split("#ifdef G30P", 1)[1].split("#elif", 1)[0].split("#else", 1)[0]


def macro(name):
    m = re.search(r"^\s*#define\s+" + re.escape(name) + r"\s+(\S+)", G30, re.M)
    if not m:
        raise AssertionError("G30 macro missing: " + name)
    return m.group(1)


class G30PortRouting(unittest.TestCase):
    def test_vesc_tool_is_on_iot_uart1(self):
        self.assertEqual(macro("VESC_USART"), "USART1")
        self.assertEqual(macro("VESC_USART_DMA"), "huart1")
        self.assertEqual(macro("VESC_USART_TX_DMA"), "hdma_usart1_tx")
        self.assertEqual(macro("VESC_USART_RX_DMA"), "hdma_usart1_rx")
        self.assertIn(".uart = &VESC_USART_DMA", TASK)
        self.assertIn("PB6     ------> USART1_TX", MSP)
        self.assertIn("PB7     ------> USART1_RX", MSP)
        self.assertIn("huart1.Init.BaudRate = 115200;", MAIN)

    def test_dashboard_yellow_is_unchanged_uart2(self):
        self.assertEqual(macro("APP_USART_DMA"), "huart2")
        self.assertEqual(macro("APP_USART_TX_DMA"), "hdma_usart2_tx")
        self.assertEqual(macro("APP_USART_RX_DMA"), "hdma_usart2_rx")
        self.assertIn(".uart = &APP_USART_DMA", TASK)
        self.assertIn("HAL_HalfDuplex_Init(&huart2)", MAIN)
        self.assertIn("PA2     ------> USART2_TX", MSP)

    def test_iot_usart1_is_preserved_for_early_iap(self):
        self.assertIn("RCC_APB2ENR_USART1EN", REC)
        self.assertIn("AFIO_MAPR_USART1_REMAP", REC)
        self.assertIn("gpio_nibble(GPIOB,6u", REC)
        self.assertIn("gpio_nibble(GPIOB,7u", REC)
        self.assertIn("USART1->CR1=0;", REC)
        self.assertIn("REC_APP_BASE       0x08001000u", REC)
        self.assertIn("REC_STAGING_BASE   0x0800E800u", REC)


if __name__ == "__main__":
    unittest.main()
