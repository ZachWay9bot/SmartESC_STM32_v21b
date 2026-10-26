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
#ifdef G30P
#include "g30_recovery_iap.h"
#endif
#include "task_LED.h"
#include "task_pwr.h"
#include "product.h"
#include "app.h"

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
volatile bool g30_runtime_ready = false;
static volatile bool g30_vesc_frame_seen = false;

/* One owner for the green PA15 LED.  Code = 2-second ON preamble,
 * N short flashes, 2-second OFF pause, repeated:
 * 1 runtime ready + a valid VESC frame seen
 * 2 motor runtime ready but no VESC frame received yet
 * 3 UART task online; motor runtime not ready
 * 4 UART RX ring overflow
 * 5 motor fault reported after runtime initialization
 * 6 hard startup error (see Error_Handler in main.c)
 * A parsed frame is not proof of a physically transmitted response.
 */
extern bool G30_UART1_RxOverflowed(void);
void G30_DiagVescFrameSeen(void) { g30_vesc_frame_seen = true; }

static void g30_diag_led(bool on)
{
    HAL_GPIO_WritePin(LED_GPIO_Port, LED_Pin,
                      on ? GPIO_PIN_SET : GPIO_PIN_RESET);
}

static void g30_diag_task(void *argument)
{
    (void)argument;
    for (;;) {
        unsigned code;
        if (G30_UART1_RxOverflowed()) code = 4u;
        else if (!g30_runtime_ready) code = 3u;
        else if (pMCI[M1] && pMCI[M1]->pSTM &&
                 pMCI[M1]->pSTM->hFaultOccurred) code = 5u;
        else code = g30_vesc_frame_seen ? 1u : 2u;

        g30_diag_led(true);
        vTaskDelay(pdMS_TO_TICKS(2000));
        g30_diag_led(false);
        vTaskDelay(pdMS_TO_TICKS(250));
        for (unsigned n=0; n<code; ++n) {
            g30_diag_led(true);
            vTaskDelay(pdMS_TO_TICKS(180));
            g30_diag_led(false);
            vTaskDelay(pdMS_TO_TICKS(230));
        }
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}

void task_comm_init(void){
    G30Recovery_AppInit();
    /* G30 green LED is reserved for deterministic diagnostics.
     * Disable the legacy status blinker only on G30. */
    (void)xTaskCreate(g30_diag_task, "g30diag", 160, NULL,
                      PRIO_NORMAL, NULL);
    task_cli_init(&main_uart);
}

void task_runtime_init(void){
	app_adc_init_timer();
	/* Green PA15 LED is owned by g30_diag_task on G30. */
#if !defined(G30_NO_DASH) || (G30_NO_DASH == 0)
	task_PWR_init(&main_uart);
#endif
	g30_runtime_ready = true;
}
#endif

void task_init(){
#ifdef G30P
	task_comm_init();
	task_runtime_init();
#else
	app_adc_init_timer();
	task_cli_init(&main_uart);
	task_LED_init(&main_uart);  //Bring up the blinky
	task_PWR_init(&main_uart);  //Manage power button
#endif
}
