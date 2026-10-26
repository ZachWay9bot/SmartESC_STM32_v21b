/*
 * m365
 *
 * Copyright (c) 2021 Jens Kerrinnes
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of
 * this software and associated documentation files (the "Software"), to deal in
 * the Software without restriction, including without limitation the rights to
 * use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 * the Software, and to permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 * FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 * COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 * IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
*/

#include "main.h"
#include "task_cli.h"
#include "task_init.h"
#ifdef G30P
#include "g30_recovery_iap.h"
extern int G30_IoT_GetByte(void);
#endif
#include "task_pwr.h"
#include "TTerm.h"
#include "printf.h"
#include "mc_config.h"
#include <string.h>
#include "packet.h"
#include "VescCommand.h"
#include "VescToSTM.h"
#include "product.h"
#include "app.h"
#include "ninebot.h"
#include "utils.h"


void putbuffer(unsigned char *buf, unsigned int len, port_str * port){
#ifdef G30P
	/* Bring-up reliability first: G30 VESC UART uses blocking TX so replies do
	 * not depend on DMA IRQ state or HAL DMA completion bookkeeping. At 115200
	 * baud the short VESC control packets are comfortably within the comm task
	 * budget while motor control continues in hardware/MC interrupts. */
	if(port->half_duplex){
		port->uart->Instance->CR1 &= ~USART_CR1_RE;
	}
	(void)HAL_UART_Transmit(port->uart, buf, len, 100U);
	if(port->half_duplex) port->uart->Instance->CR1 |= USART_CR1_RE;
#else
	if(port->half_duplex){
		port->uart->Instance->CR1 &= ~USART_CR1_RE;
		vTaskDelay(1);
	}
	HAL_UART_Transmit_DMA(port->uart, buf, len);
	while(port->uart->hdmatx->State != HAL_DMA_STATE_READY){
		port->uart->gState = HAL_UART_STATE_READY;
		vTaskDelay(1);
	}
	if(port->half_duplex) port->uart->Instance->CR1 |= USART_CR1_RE;
#endif
}

void comm_uart_send_packet(unsigned char *data, unsigned int len, PACKET_STATE_t * phandle) {
	packet_send_packet(data, len, phandle);
}

void process_packet(unsigned char *data, unsigned int len, PACKET_STATE_t * phandle){
	commands_process_packet(data, len, &comm_uart_send_packet, phandle);
}

static uint32_t uart_get_write_pos(port_str * port){
	return ( ((uint32_t)port->rx_buffer_size - port->uart->hdmarx->Instance->CNDTR) & ((uint32_t)port->rx_buffer_size -1));
}

void task_cli(void * argument)
{
	port_str * port = (port_str*) argument;
#ifdef G30P
	port->phandle = packet_init(putbuffer, process_packet, port);
	if (port->phandle == NULL) {
		port->task_handle = NULL;
		vTaskDelete(NULL);
		return;
	}

	/* The in-app Ninebot parser shares the USART1 byte stream with VESC. */
	G30Recovery_AppInit();

	/* USART was already fully initialized by MX_USARTx_UART_Init(). Do not
	 * re-run MSP/DMA setup here. Poll one byte at a time; this also clears and
	 * recovers UART error conditions through the HAL receive path.
	 *
	 * G30 communication starts before MCSDK motor initialization. Until
	 * g30_runtime_ready becomes true, only the packet transport is active. */
	bool runtime_comm_initialized = false;
	uint16_t slow_update_cnt=0;
	for(;;)
	{
		/* Drain the proven USART1 IRQ RX ring; a blocking single-byte
		 * HAL receive can miss bytes while the motor/RTOS is busy. */
		int rx;
		while ((rx = G30_IoT_GetByte()) >= 0) {
			uint8_t rx_byte = (uint8_t)rx;
			/* One incoming byte is presented to BOTH protocol parsers. */
			G30Recovery_AppPushByte(rx_byte,
				g30_runtime_ready && PWM_Handle_M1._Super.PWM_off);
			packet_process_byte(rx_byte, port->phandle);
		}
		vTaskDelay(1);

		if (g30_runtime_ready && !runtime_comm_initialized) {
			VescToSTM_set_brake_rel_int(0);
			app_check_timer();
			runtime_comm_initialized = true;
		}

		if (g30_runtime_ready) {
			VescToSTM_handle_timeout();
		}

		if(g30_runtime_ready && appconf.app_to_use == APP_ADC_UART){
			app_check_timer();
			if(slow_update_cnt==0){
				if(m365_to_display.mode & 0x40){
					m365_to_display.speed = VescToSTM_get_speed()*2.2369;
				}else{
					m365_to_display.speed = VescToSTM_get_speed()*3.6;
				}
				m365_to_display.speed *= DIR_MUL;
				m365_to_display.battery = utils_map(VescToSTM_get_battery_level(0), 0, 1, 0, 96);
				m365_to_display.beep=0;
				m365_to_display.faultcode=pMCI[M1]->pSTM->hFaultOccurred;
			}else{
				slow_update_cnt++;
				if(slow_update_cnt==100) slow_update_cnt=0;
			}
		}

		if(ulTaskNotifyTake(pdTRUE, 0)){
			if(appconf.app_to_use == APP_ADC_UART){
				app_adc_stop_output();
			}
			port->task_handle = NULL;
			packet_free(port->phandle);
			vTaskDelete(NULL);
			return;
		}
	}
#else
	uint32_t rd_ptr=0;
	uint8_t * usart_rx_dma_buffer = pvPortMalloc(port->rx_buffer_size);
	if (usart_rx_dma_buffer == NULL) {
		port->task_handle = NULL;
		vTaskDelete(NULL);
		return;
	}
	port->phandle = packet_init(putbuffer, process_packet, port);
	if (port->phandle == NULL) {
		vPortFree(usart_rx_dma_buffer);
		port->task_handle = NULL;
		vTaskDelete(NULL);
		return;
	}
	HAL_UART_MspInit(port->uart);
	if(port->half_duplex){
		HAL_HalfDuplex_Init(port->uart);
	}
	HAL_UART_Receive_DMA(port->uart, usart_rx_dma_buffer, port->rx_buffer_size);
	CLEAR_BIT(port->uart->Instance->CR3, USART_CR3_EIE);

	VescToSTM_set_brake_rel_int(0);

	app_check_timer();

	uint16_t slow_update_cnt=0;

  /* Infinite loop */
	for(;;)
	{
		/* `#START TASK_LOOP_CODE` */
		while(rd_ptr != uart_get_write_pos(port)) {
			packet_process_byte(usart_rx_dma_buffer[rd_ptr], port->phandle);
			rd_ptr++;
			rd_ptr &= ((uint32_t)port->rx_buffer_size - 1);
		}

#ifndef G30P
		send_sample(port->phandle);
		send_position(port->phandle);
#endif
		VescToSTM_handle_timeout();

		if(appconf.app_to_use == APP_ADC_UART){
			app_check_timer();

			if(slow_update_cnt==0){
				if(m365_to_display.mode & 0x40){
					m365_to_display.speed = VescToSTM_get_speed()*2.2369;
				}else{
					m365_to_display.speed = VescToSTM_get_speed()*3.6;

				}
				m365_to_display.speed *= DIR_MUL;
				m365_to_display.battery = utils_map(VescToSTM_get_battery_level(0), 0, 1, 0, 96);
				m365_to_display.beep=0;
				m365_to_display.faultcode=pMCI[M1]->pSTM->hFaultOccurred;

			}else{
				slow_update_cnt++;
				if(slow_update_cnt==100) slow_update_cnt=0;
			}
		}

		if(ulTaskNotifyTake(pdTRUE, 1)){
			if(appconf.app_to_use == APP_ADC_UART){
				app_adc_stop_output();
			}
			HAL_UART_MspDeInit(port->uart);
			port->task_handle = NULL;
			packet_free(port->phandle);
			vPortFree(usart_rx_dma_buffer);
			vTaskDelete(NULL);
			vTaskDelay(portMAX_DELAY);
		}

	}
#endif
}

void task_cli_init(port_str * port){
#if VESC_TOOL_ENABLE
	if(port->task_handle == NULL){
		xTaskCreate(task_cli, "tskCLI", 320, (void*)port, PRIO_NORMAL, &port->task_handle);
	}
#endif
}

void task_cli_kill(port_str * port){
	if(port->task_handle){
		xTaskNotify(port->task_handle, 0, eIncrement);
		vTaskDelay(200);
	}
}
