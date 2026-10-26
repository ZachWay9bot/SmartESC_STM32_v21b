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
extern void G30_DiagVescFrameSeen(void);
/* v0.4.6 USART1 IRQ/ring-buffer transport, implemented in stm32f1xx_it.c */
extern void G30_UART1_RxStart(void);
extern int G30_UART1_Getc(void);
extern void G30_UART1_Putc(uint8_t byte);
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
    /* Same bytewise blocking USART1 TX as verified v0.4.6.
     * No DMA completion state and no HAL UART TX state machine. */
    if (port->uart->Instance == USART1) {
        for (unsigned int i = 0; i < len; ++i)
            G30_UART1_Putc(buf[i]);
    }
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
#ifdef G30P
    /* v0.4.6 port invokes this only after a CRC-valid VESC frame. */
    G30_DiagVescFrameSeen();
#endif
	commands_process_packet(data, len, &comm_uart_send_packet, phandle);
}

#ifdef G30P
/* Exact v0.4.6 VESC serial frame state machine, independently from packet.c.
 * The only adapted boundary is the completed payload callback, which uses
 * existing SmartESC VESC command handlers and VESC reply framing.
 * Ninebot bytes continue to the unchanged recovery/IAP frame parser.
 */
#define G30_V046_VESC_RX_MAX 520u
typedef struct {
    uint8_t st, start, crc_hi, len_hi;
    uint16_t len, pos;
    uint8_t data[G30_V046_VESC_RX_MAX];
} g30_v046_parser_t;
static g30_v046_parser_t g30_v046_vp;

static uint16_t g30_v046_crc16(const uint8_t *buf, uint32_t len)
{
    int16_t crc = 0;
    while (len--) {
        int16_t x = ((uint8_t)(crc >> 8)) ^ *buf++;
        x ^= x >> 4;
        crc = (int16_t)((crc << 8) ^ (x << 12) ^ (x << 5) ^ x);
    }
    return (uint16_t)crc;
}

static int g30_v046_vesc_parser_push(uint8_t x, PACKET_STATE_t *phandle)
{
    g30_v046_parser_t *vp = &g30_v046_vp;
    switch (vp->st) {
    case 0: if (x == 2u) { vp->start = 2u; vp->st = 1; }
            else if (x == 3u) { vp->start = 3u; vp->st = 6; } break;
    case 1: vp->len = x;
            if (!vp->len || vp->len > G30_V046_VESC_RX_MAX) { vp->st = 0; break; }
            vp->pos = 0; vp->st = 2; break;
    case 6: vp->len_hi = x; vp->st = 7; break;
    case 7: vp->len = ((uint16_t)vp->len_hi << 8) | x;
            if (!vp->len || vp->len > G30_V046_VESC_RX_MAX) { vp->st = 0; break; }
            vp->pos = 0; vp->st = 2; break;
    case 2: vp->data[vp->pos++] = x;
            if (vp->pos >= vp->len) vp->st = 3; break;
    case 3: vp->crc_hi = x; vp->st = 4; break;
    case 4: {
        uint16_t got = ((uint16_t)vp->crc_hi << 8) | x;
        uint16_t want = g30_v046_crc16(vp->data, vp->len);
        vp->st = (got == want) ? 5 : 0;
        break;
    }
    case 5:
        if (x == 3u) {
            process_packet(vp->data, vp->len, phandle);
            vp->st = 0;
            return 1;
        }
        vp->st = 0;
        break;
    default: vp->st = 0; break;
    }
    return 0;
}
#endif

static uint32_t uart_get_write_pos(port_str * port){
	return ( ((uint32_t)port->rx_buffer_size - port->uart->hdmarx->Instance->CNDTR) & ((uint32_t)port->rx_buffer_size -1));
}

void task_cli(void * argument)
{
	port_str * port = (port_str*) argument;
#ifdef G30P
	/* IRQ-driven receive is drained here, as in verified v0.4.6. */
	port->phandle = packet_init(putbuffer, process_packet, port);
	if (port->phandle == NULL) {
		port->task_handle = NULL;
		vTaskDelete(NULL);
		return;
	}

	/* USART was already fully initialized by MX_USARTx_UART_Init(). Do not
	 * re-run MSP/DMA setup here. Poll one byte at a time; this also clears and
	 * recovers UART error conditions through the HAL receive path.
	 *
	 * G30 communication starts before MCSDK motor initialization. Until
	 * g30_runtime_ready becomes true, only the packet transport is active. */
	G30_UART1_RxStart();
	bool runtime_comm_initialized = false;
	uint16_t slow_update_cnt=0;
	for(;;)
	{
		/* Exact v0.4.6 dispatch model: every byte goes to both parsers.
		 * Processing is task-context, while the interrupt buffers RX bytes. */
		int rx;
		while ((rx = G30_UART1_Getc()) >= 0) {
			uint8_t byte = (uint8_t)rx;
			G30Recovery_AppPushByte(byte,
				g30_runtime_ready && PWM_Handle_M1._Super.PWM_off);
			(void)g30_v046_vesc_parser_push(byte, port->phandle);
		}

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
		/* The motor initialization task runs below PRIO_NORMAL. A busy
		 * UART polling loop would permanently starve it after scheduler start. */
		vTaskDelay(1);
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
