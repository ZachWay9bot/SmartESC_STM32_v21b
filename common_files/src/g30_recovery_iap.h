#pragma once

/*
 * Early G30 recovery entry.
 * Returns immediately unless the power button is held continuously for 3 s.
 * Once entered it never starts TIM1/ADC/MotorControl and serves the proven
 * Ninebot IAP 0x07/0x08/0x09/0x0A protocol on USART1 remap PB6/PB7 @115200.
 */
void G30Recovery_CheckAndRun(void);

/* Application-side protocol multiplexer: the FO76 path feeds the SAME UART
 * RX byte to Ninebot and VESC frame parsers. This leaves power-on recovery,
 * bootloader, and flash layout unchanged. */
#include <stdint.h>
#include <stdbool.h>
void G30Recovery_AppInit(void);
void G30Recovery_AppPushByte(uint8_t byte, bool flash_idle);
bool G30Recovery_AppIapActive(void);
