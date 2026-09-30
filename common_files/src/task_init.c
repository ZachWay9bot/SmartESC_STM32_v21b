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

#include "task_init.h"
#include "task_LED.h"
#include "task_pwr.h"
#include "product.h"
#include "app.h"
#include <string.h>

unsigned long getRunTimeCounterValue(void){
	return HAL_GetTick();
}

port_str main_uart = {	.uart = &VESC_USART_DMA,
					    .rx_buffer_size = 512,
						.phandle = NULL,
						.half_duplex = false,
						.task_handle = NULL
};
port_str aux_uart = {	.uart = &APP_USART_DMA,
					    .rx_buffer_size = 128,
						.phandle = NULL,
						.half_duplex = true,
						.task_handle = NULL
};

#ifdef G30P

/*
 * Stock Ninebot G30 BMS link.
 *
 * USART3 is the factory full-duplex ESC <-> BMS bus:
 *   PB10 = ESC TX -> BMS RX
 *   PB11 = ESC RX <- BMS TX
 *
 * The public Ninebot-BMS-Activator project demonstrates that the stock BMS
 * needs a periodic ESC heartbeat/activation frame to avoid the approximately
 * 19 A no-communication fallback limit. We intentionally transmit that proven
 * byte sequence exactly as published, including the trailing idle 0xFF byte.
 *
 * In parallel we send ordinary checksum-valid Ninebot READ requests for SOC,
 * current, voltage, temperature and status. These reads do not modify BMS
 * configuration or protection thresholds.
 */

typedef struct {
	volatile uint8_t soc;
	volatile uint16_t voltage_10mv;
	volatile int16_t current_10ma;
	volatile int16_t temp_deci_c;
	volatile uint16_t status;
	volatile TickType_t last_valid_rx;
} g30_bms_state_t;

static g30_bms_state_t g30_bms_state;
static TaskHandle_t g30_bms_task_handle;

#define G30_BMS_RX_BUF_SIZE 64u
#define G30_BMS_FRAME_BUF_SIZE 32u

typedef struct {
	uint8_t state;
	uint8_t idx;
	uint8_t expected;
	uint8_t body[G30_BMS_FRAME_BUF_SIZE];
} g30_bms_parser_t;

static g30_bms_parser_t g30_bms_parser;

/* Byte-for-byte payload used by rasil1127/Ninebot-BMS-Activator. */
static const uint8_t g30_bms_activator_frame[] = {
	0x5A, 0xA5, 0x06, 0x20, 0x22, 0x30, 0x00, 0x00, 0x87, 0xFF, 0xFF
};

static uint16_t g30_bms_checksum(const uint8_t *data, uint8_t len) {
	uint16_t sum = 0;
	for(uint8_t i = 0; i < len; i++) {
		sum = (uint16_t)(sum + data[i]);
	}
	return (uint16_t)(~sum);
}

static uint8_t g30_bms_build_read(uint8_t reg, uint8_t *out) {
	/* Verified stock G30 format: LEN equals payload byte count. */
	out[0] = 0x5A;
	out[1] = 0xA5;
	out[2] = 0x01; /* one payload byte: number of bytes requested */
	out[3] = 0x20; /* ESC */
	out[4] = 0x22; /* BMS */
	out[5] = 0x01; /* READ */
	out[6] = reg;
	out[7] = 0x02; /* read one 16-bit register */

	const uint16_t ck = g30_bms_checksum(&out[2], 6u);
	out[8] = (uint8_t)(ck & 0xFFu);
	out[9] = (uint8_t)(ck >> 8);
	return 10u;
}

static void g30_bms_parser_reset(void) {
	memset(&g30_bms_parser, 0, sizeof(g30_bms_parser));
}

static void g30_bms_accept_packet(void) {
	const uint8_t len = g30_bms_parser.body[0];
	const uint8_t src = g30_bms_parser.body[1];
	const uint8_t dst = g30_bms_parser.body[2];
	const uint8_t arg = g30_bms_parser.body[4];

	if(src != 0x22u || dst != 0x20u || len < 2u) {
		return;
	}

	const uint16_t v =
			(uint16_t)g30_bms_parser.body[5] |
			((uint16_t)g30_bms_parser.body[6] << 8);

	switch(arg) {
	case 0x30: /* status */
		g30_bms_state.status = v;
		break;
	case 0x32: /* SOC % */
		g30_bms_state.soc = (uint8_t)(v > 100u ? 100u : v);
		break;
	case 0x33: /* signed current, 10 mA */
		g30_bms_state.current_10ma = (int16_t)v;
		break;
	case 0x34: /* pack voltage, 10 mV */
		g30_bms_state.voltage_10mv = v;
		break;
	case 0x35: /* pack temperature, 0.1 C */
		g30_bms_state.temp_deci_c = (int16_t)v;
		break;
	default:
		break;
	}

	g30_bms_state.last_valid_rx = xTaskGetTickCount();
}

static void g30_bms_feed_byte(uint8_t b) {
	switch(g30_bms_parser.state) {
	case 0:
		if(b == 0x5A) {
			g30_bms_parser.state = 1;
		}
		break;

	case 1:
		if(b == 0xA5) {
			g30_bms_parser.state = 2;
			g30_bms_parser.idx = 0;
		} else if(b != 0x5A) {
			g30_bms_parser_reset();
		}
		break;

	case 2:
		if(g30_bms_parser.idx >= sizeof(g30_bms_parser.body)) {
			g30_bms_parser_reset();
			break;
		}

		g30_bms_parser.body[g30_bms_parser.idx++] = b;

		if(g30_bms_parser.idx == 1u) {
			const uint16_t expected = (uint16_t)b + 7u;
			if(expected < 7u || expected > sizeof(g30_bms_parser.body)) {
				g30_bms_parser_reset();
				break;
			}
			g30_bms_parser.expected = (uint8_t)expected;
		}

		if(g30_bms_parser.expected &&
		   g30_bms_parser.idx == g30_bms_parser.expected) {
			const uint8_t data_len = (uint8_t)(g30_bms_parser.expected - 2u);
			const uint16_t calc = g30_bms_checksum(g30_bms_parser.body, data_len);
			const uint16_t recv =
					(uint16_t)g30_bms_parser.body[data_len] |
					((uint16_t)g30_bms_parser.body[data_len + 1u] << 8);

			if(calc == recv) {
				g30_bms_accept_packet();
			}
			g30_bms_parser_reset();
		}
		break;

	default:
		g30_bms_parser_reset();
		break;
	}
}

static void g30_bms_send(const uint8_t *data, uint16_t len) {
	/*
	 * 11 bytes at 115200 baud are below 1 ms on the wire. A short blocking
	 * transfer keeps the BMS task simple and avoids sharing DMA TX state.
	 */
	(void)HAL_UART_Transmit(&APP2_USART_DMA, (uint8_t*)data, len, 10u);
}

static void task_g30_bms(void *argument) {
	(void)argument;
	static uint8_t rx[G30_BMS_RX_BUF_SIZE];
	uint32_t rd_ptr = 0;

	memset(&g30_bms_state, 0, sizeof(g30_bms_state));
	g30_bms_parser_reset();

	/* USART3 is already configured at 115200 8N1 by main.c. */
	HAL_UART_Receive_DMA(&APP2_USART_DMA, rx, sizeof(rx));
	CLEAR_BIT(APP2_USART_DMA.Instance->CR3, USART_CR3_EIE);

	TickType_t next_activation = xTaskGetTickCount();
	TickType_t next_poll = next_activation + MS_TO_TICKS(100u);
	uint8_t poll_idx = 0;
	static const uint8_t poll_regs[] = {0x32, 0x33, 0x34, 0x35, 0x30};

	for(;;) {
		const uint32_t wr_ptr =
				((uint32_t)sizeof(rx) - APP2_USART_DMA.hdmarx->Instance->CNDTR) &
				((uint32_t)sizeof(rx) - 1u);

		while(rd_ptr != wr_ptr) {
			g30_bms_feed_byte(rx[rd_ptr]);
			rd_ptr = (rd_ptr + 1u) & ((uint32_t)sizeof(rx) - 1u);
		}

		const TickType_t now = xTaskGetTickCount();

#if G30_BMS_ACTIVATOR_ENABLE
		if((int32_t)(now - next_activation) >= 0) {
			g30_bms_send(g30_bms_activator_frame,
					(uint16_t)sizeof(g30_bms_activator_frame));
			next_activation = now + MS_TO_TICKS(G30_BMS_ACTIVATOR_PERIOD_MS);
		}
#endif

		if((int32_t)(now - next_poll) >= 0) {
			uint8_t rq[10];
			const uint8_t n = g30_bms_build_read(
					poll_regs[poll_idx % (sizeof(poll_regs) / sizeof(poll_regs[0]))], rq);
			g30_bms_send(rq, n);
			poll_idx++;
			next_poll = now + MS_TO_TICKS(G30_BMS_POLL_PERIOD_MS);
		}

		vTaskDelay(MS_TO_TICKS(10u));
	}
}

bool g30_bms_is_online(void) {
	const TickType_t last = g30_bms_state.last_valid_rx;
	if(last == 0) {
		return false;
	}
	return (xTaskGetTickCount() - last) <= MS_TO_TICKS(G30_BMS_ONLINE_TIMEOUT_MS);
}

uint8_t g30_bms_get_soc(void) {
	return g30_bms_state.soc;
}

uint16_t g30_bms_get_voltage_10mv(void) {
	return g30_bms_state.voltage_10mv;
}

int16_t g30_bms_get_current_10ma(void) {
	return g30_bms_state.current_10ma;
}

int16_t g30_bms_get_temp_deci_c(void) {
	return g30_bms_state.temp_deci_c;
}

uint16_t g30_bms_get_status(void) {
	return g30_bms_state.status;
}

static void g30_bms_init(void) {
	xTaskCreate(task_g30_bms, "tskBMS", 192, NULL, PRIO_BELOW_NORMAL,
			&g30_bms_task_handle);
}

#endif /* G30P */

void task_init(){
	app_adc_init_timer();
	task_cli_init(&main_uart);
	task_LED_init(&main_uart);  //Bring up the blinky
	task_PWR_init(&main_uart);  //Manage power button
#ifdef G30P
	g30_bms_init();
#endif
}
