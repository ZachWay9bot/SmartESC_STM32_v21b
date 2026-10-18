#pragma once

/*
 * Early G30 recovery entry.
 * Returns immediately unless the power button is held continuously for 3 s.
 * Once entered it never starts TIM1/ADC/MotorControl and serves the proven
 * Ninebot IAP 0x07/0x08/0x09/0x0A protocol on USART1 remap PB6/PB7 @115200.
 */
void G30Recovery_CheckAndRun(void);
