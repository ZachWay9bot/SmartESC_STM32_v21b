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
#include "app.h"
#include "utils.h"
#include "VescToSTM.h"
#include "FreeRTOS.h"
#include "task.h"
#include "product.h"
#include "ninebot.h"
#include "VescCommand.h"
#include "task_init.h"
#include "task_LED.h"
#include "timers.h"
#include <math.h>
#include <string.h>

NinebotPack frame;

m365Answer m365_to_display = {.start1=NinebotHeader0, .start2=NinebotHeader1, .len=8, .addr=0x21, .cmd=0x64, .arg=0, .mode=M365_MODE_SPORT};

uint8_t app_connection_timout = 8;

void vTimerCallback( TimerHandle_t xTimer );
uint32_t app_updaterate();

TaskHandle_t task_app_handle;
TimerHandle_t xTimer;

#if defined(G30P) && SESC_SHU_COMPAT
/*
 * Stock G30 / SHU protocol sniffer.
 *
 * SmartESC's normal dashboard protocol is left untouched. In parallel we watch
 * for checksum-valid stock Ninebot frames:
 *
 *   5A A5 LEN SRC DST CMD ARG payload[LEN] CK_LO CK_HI
 *
 * If SHU starts an ESC firmware-update transaction while the scooter is
 * stationary, SmartESC releases the motor and reboots so the preserved stock
 * 4 KiB IAP bootloader can take over. The phone-side flasher will retry the
 * update command after the reset.
 */
typedef struct {
	uint8_t state;
	uint8_t index;
	uint8_t expected;
	uint8_t body[80];
} shu_rx_t;

static shu_rx_t shu_rx;

static void shu_rx_reset(void) {
	memset(&shu_rx, 0, sizeof(shu_rx));
}

/*
 * IAP start has exactly four payload bytes on the reversible G30 build:
 *   uint16_t firmware_size_le
 *   uint16_t version_le
 *
 * There are two LEN conventions in public Ninebot tooling:
 *   - firmware-verified G30 framing: LEN == payload bytes      -> LEN = 4
 *   - older flasher tooling:         LEN == 4 + payload bytes -> LEN = 8
 *
 * Both produce the same 11-byte body after 5A A5:
 *   LEN SRC DST CMD ARG PAY0 PAY1 PAY2 PAY3 CK_LO CK_HI
 *
 * We deliberately recognize only this exact, checksum-valid IAP-start shape.
 * That matters because entering recovery invalidates the current app vector;
 * a fuzzy opcode detector would be a remarkably stupid place to be generous.
 */
#define SHU_IAP_START_BODY_BYTES 11u

static bool shu_is_iap_start(void) {
	const uint8_t len = shu_rx.body[0];
	const uint8_t src = shu_rx.body[1];
	const uint8_t dst = shu_rx.body[2];
	const uint8_t cmd = shu_rx.body[3];
	const uint8_t arg = shu_rx.body[4];

	if(len != 4u && len != 8u) {
		return false;
	}

	if(dst != 0x20u || (src != 0x21u && src != 0x3Eu && src != 0x3Fu)) {
		return false;
	}

	if((cmd != 0x02u && cmd != 0x03u) || arg != 0x07u) {
		return false;
	}

	const uint16_t fw_size =
			(uint16_t)shu_rx.body[5] |
			((uint16_t)shu_rx.body[6] << 8);

	if(fw_size < 256u || (uint32_t)fw_size > SESC_SHU_MAX_APP_BYTES) {
		return false;
	}

	return true;
}

static bool shu_feed_stock_frame(uint8_t b) {
	switch(shu_rx.state) {
	case 0:
		if(b == 0x5A) {
			shu_rx.state = 1;
		}
		break;

	case 1:
		if(b == 0xA5) {
			shu_rx.state = 2;
			shu_rx.index = 0;
			shu_rx.expected = 0;
		} else if(b != 0x5A) {
			shu_rx_reset();
		}
		break;

	case 2:
		if(shu_rx.index >= sizeof(shu_rx.body)) {
			shu_rx_reset();
			break;
		}

		shu_rx.body[shu_rx.index++] = b;

		if(shu_rx.index == 1u) {
			/*
			 * Only the exact 4-byte IAP-start payload is interesting here.
			 * Accept LEN=4 (verified convention) and LEN=8 (legacy tooling).
			 */
			if(shu_rx.body[0] == 4u || shu_rx.body[0] == 8u) {
				shu_rx.expected = SHU_IAP_START_BODY_BYTES;
			} else {
				shu_rx_reset();
				break;
			}
		}

		if(shu_rx.expected && shu_rx.index == shu_rx.expected) {
			uint16_t sum = 0;
			for(uint8_t i = 0; i < (uint8_t)(SHU_IAP_START_BODY_BYTES - 2u); i++) {
				sum = (uint16_t)(sum + shu_rx.body[i]);
			}

			const uint16_t calc = (uint16_t)(~sum);
			const uint16_t recv =
					(uint16_t)shu_rx.body[SHU_IAP_START_BODY_BYTES - 2u] |
					((uint16_t)shu_rx.body[SHU_IAP_START_BODY_BYTES - 1u] << 8);

			const bool request = (calc == recv) && shu_is_iap_start();
			shu_rx_reset();
			return request;
		}
		break;

	default:
		shu_rx_reset();
		break;
	}

	return false;
}

#define G30_STOCK_APP_VECTOR_BASE 0x08001000u

bool app_shu_invalidate_app_vector(void) {
	/*
	 * The stock bootloader has a recovery path for an invalid application.
	 * Clearing the upper half-word of the application's initial stack pointer
	 * changes e.g. 0x2000xxxx into 0x0000xxxx without erasing any code page.
	 *
	 * That is preferable to guessing a revision-specific update-control block:
	 * after reset the current SmartESC image is intentionally non-bootable and
	 * the preserved stock IAP bootloader must remain in recovery/update mode.
	 * A successful SHU flash writes a fresh vector table and restores normal
	 * boot automatically.
	 */
	HAL_StatusTypeDef st;

	if(HAL_FLASH_Unlock() != HAL_OK) {
		return false;
	}

	__HAL_FLASH_CLEAR_FLAG(FLASH_FLAG_EOP | FLASH_FLAG_PGERR | FLASH_FLAG_WRPERR);

	/* Program high half first. One successful write is enough to invalidate SP. */
	st = HAL_FLASH_Program(FLASH_TYPEPROGRAM_HALFWORD,
			G30_STOCK_APP_VECTOR_BASE + 2u, 0x0000u);

	HAL_FLASH_Lock();
	return st == HAL_OK;
}

static void shu_handoff_to_stock_iap(void) {
	/* Never enter a flasher while the wheel is moving. */
	if(fabsf(VescToSTM_get_speed()) > 0.5f) {
		return;
	}

	VescToSTM_set_current_rel(0.0f);
	vTaskDelay(MS_TO_TICKS(20));

	if(fabsf(VescToSTM_get_iq()) > DELTA_SWITCH_MAX_IQ_A) {
		return;
	}

	/* Fail-safe STAR and high-Z inverter before committing to IAP recovery. */
	HAL_GPIO_WritePin(BRAKE_LIGHT_GPIO_Port, BRAKE_LIGHT_Pin, GPIO_PIN_RESET);
	VescToSTM_pwm_stop();
	vTaskDelay(MS_TO_TICKS(10));

	if(!app_shu_invalidate_app_vector()) {
		/* Keep the current firmware running if flash programming was rejected. */
		VescToSTM_pwm_start();
		return;
	}

	__disable_irq();
	NVIC_SystemReset();
}
#endif

void my_uart_send_data(unsigned char *buf, unsigned int len, port_str * port){
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
}

static uint32_t uart_get_write_pos(port_str * port){
	return ( ((uint32_t)port->rx_buffer_size - port->uart->hdmarx->Instance->CNDTR) & ((uint32_t)port->rx_buffer_size -1));
}

static uint8_t adc1;
static uint8_t adc2;
void app_adc_set_adc(uint8_t AD1, uint8_t AD2){
	if(xTimer!=NULL && xTimerIsTimerActive(xTimer)==pdFALSE){
		xTimerStart(xTimer, 100);
	}
	adc1 = AD1;
	adc2 = AD2;
}



static float decoded_level = 0.0;
static float decoded_level2 = 0.0;

#define config		appconf.app_adc_conf

#define TimeMsElapsedSinceX(start)                                        \
  ((uint32_t)((xTaskGetTickCount()- (start))/2))


void vTimerCallback( TimerHandle_t xTimer ){
	//uint32_t cycles = *DWT_CYCCNT;
	if(SpeednTorqCtrlM1.SPD->open_loop==true) return;
	uint32_t temp1 = adc1;
	uint32_t temp2 = adc2;
	temp1 <<= 4;
	temp2 <<= 4;
	static uint16_t aver1=0;
	static uint16_t aver2=0;

	if(config.use_filter){
		aver1 += temp1;
		aver1 /=2;
		aver2 += temp2;
		aver2 /=2;
	}else{
		aver1 = temp1;
		aver2 = temp2;
	}

	float pwr = utils_map(aver1, 0, 255<<4, 0, 3.3); //Throttle;
	float brake = utils_map(aver2, 0, 255<<4, 0, 3.3); //Brake;
	VescToSTM_set_ADC1(pwr);
	VescToSTM_set_ADC2(brake);


	// Map the read voltage
	switch (config.ctrl_type) {
	case ADC_CTRL_TYPE_CURRENT_REV_CENTER:
	case ADC_CTRL_TYPE_CURRENT_REV_BUTTON_BRAKE_CENTER:
	case ADC_CTRL_TYPE_CURRENT_NOREV_BRAKE_CENTER:
	case ADC_CTRL_TYPE_DUTY_REV_CENTER:
	case ADC_CTRL_TYPE_PID_REV_CENTER:
		// Mapping with respect to center voltage
		if (pwr < config.voltage_center) {
			pwr = utils_map(pwr, config.voltage_start,
					config.voltage_center, 0.0, 0.5);
		} else {
			pwr = utils_map(pwr, config.voltage_center,
					config.voltage_end, 0.5, 1.0);
		}
		break;

	default:
		// Linear mapping between the start and end voltage
		pwr = utils_map(pwr, config.voltage_start, config.voltage_end, 0.0, 1.0);
		break;
	}

	// Optionally invert the read voltage
	if (config.voltage_inverted) {
		pwr = 1.0 - pwr;
	}
	pwr *= mc_conf.lo_current_max_scale;
	utils_truncate_number(&pwr, 0.0, 1.0);

	brake = utils_map(brake, config.voltage2_start, config.voltage2_end, 0.0, 1.0);
	// Optionally invert the read voltage
	if (config.voltage2_inverted) {
		brake = 1.0 - brake;
	}
	utils_truncate_number(&brake, 0.0, 1.0);
	decoded_level = pwr;
	decoded_level2 = brake;

	switch (config.ctrl_type) {
		case ADC_CTRL_TYPE_CURRENT_REV_CENTER:
		case ADC_CTRL_TYPE_CURRENT_REV_BUTTON_BRAKE_CENTER:
		case ADC_CTRL_TYPE_CURRENT_NOREV_BRAKE_CENTER:
		case ADC_CTRL_TYPE_DUTY_REV_CENTER:
		case ADC_CTRL_TYPE_PID_REV_CENTER:
			// Scale the voltage and set 0 at the center
			pwr *= 2.0;
			pwr -= 1.0;
			break;

		case ADC_CTRL_TYPE_CURRENT_NOREV_BRAKE_ADC:
		case ADC_CTRL_TYPE_CURRENT_REV_BUTTON_BRAKE_ADC:
			pwr -= brake;
			break;

		default:
			break;
	}

	// Apply deadband
	utils_deadband(&pwr, config.hyst, 1.0);
	utils_deadband(&brake, config.hyst, 1.0);

	// Apply throttle curve
	pwr = utils_throttle_curve(pwr, config.throttle_exp, config.throttle_exp_brake, config.throttle_exp_mode);

#if defined(G30P) && SESC_NO_REGEN
	/*
	 * Physical brake is a motor cut/coast input on this build.
	 * Never turn a brake request into negative torque.
	 */
	if(brake > 0.0f || pwr < 0.0f) {
		pwr = 0.0f;
	}
#endif

	// Apply ramping
	static uint32_t last_time = 0;
	static float pwr_ramp = 0.0;
	float ramp_time = fabsf(pwr) > fabsf(pwr_ramp) ? config.ramp_time_pos : config.ramp_time_neg;

	if (ramp_time > 0.01) {
		const float ramp_step = (float)TimeMsElapsedSinceX(last_time) / (ramp_time * 1000.0);
		utils_step_towards(&pwr_ramp, pwr, ramp_step);
		last_time = xTaskGetTickCount();
		pwr = pwr_ramp;
	}

#if defined(G30P) && SESC_NO_REGEN
	/* Brake must cut propulsion immediately, without regenerative torque. */
	if(brake > 0.0f) {
		pwr_ramp = 0.0f;
		pwr = 0.0f;
	}
#endif

#ifdef G30P
	/*
	 * STAR/DELTA transition owns the motor for a short window. task_LED.c
	 * waits for low Iq, disables PWM, changes the relay topology and keeps
	 * torque inhibited until the contacts have settled.
	 */
	if(task_delta_coast_required()) {
		pwr_ramp = 0.0f;
		VescToSTM_set_current_rel(0.0f);
		return;
	}
#endif

	if(app_is_output_disabled()){
#if defined(G30P) && SESC_NO_REGEN
		VescToSTM_set_current_rel(0.0f);
		if(fabsf(VescToSTM_get_iq()) <= TRUE_COAST_IQ_A) {
			VescToSTM_pwm_stop();
		}
#endif
		return;
	}

#if defined(G30P) && SESC_NO_REGEN
	/*
	 * True coast: once commanded torque and measured Iq are near zero, turn
	 * the inverter PWM fully off. On throttle re-application pwm_start()
	 * re-synchronizes to the Hall angle and preloads the current controller.
	 */
	if(pwr <= 0.0001f) {
		VescToSTM_set_current_rel(0.0f);
		if(fabsf(VescToSTM_get_iq()) <= TRUE_COAST_IQ_A) {
			VescToSTM_pwm_stop();
		}
		return;
	}

	VescToSTM_pwm_start();
#endif

	// Use the filtered and mapped voltage for control according to the configuration.
	switch (config.ctrl_type) {
	case ADC_CTRL_TYPE_CURRENT:
	case ADC_CTRL_TYPE_CURRENT_REV_CENTER:
		VescToSTM_set_current_rel(pwr);
		break;

	case ADC_CTRL_TYPE_CURRENT_NOREV_BRAKE_CENTER:
#if defined(G30P) && SESC_NO_REGEN
		VescToSTM_set_current_rel(pwr > 0.0f ? pwr : 0.0f);
#else
		if(pwr>=0){
			VescToSTM_set_current_rel(pwr);
		}else{
			VescToSTM_set_brake_current_rel(pwr);
		}
#endif
		break;
	case ADC_CTRL_TYPE_CURRENT_NOREV_BRAKE_ADC:
#if defined(G30P) && SESC_NO_REGEN
		if(brake > 0.0f){
			VescToSTM_set_current_rel(0.0f);
		}else{
			VescToSTM_set_current_rel(pwr > 0.0f ? pwr : 0.0f);
		}
#else
		if(brake>0){
			VescToSTM_set_brake_current_rel(brake);
		}else if(pwr>=0){
			VescToSTM_set_current_rel(pwr);
		}
#endif

		break;

	case ADC_CTRL_TYPE_PID:
	case ADC_CTRL_TYPE_PID_REV_CENTER:
	case ADC_CTRL_TYPE_PID_REV_BUTTON:{
		float speed = 0.0;
		if (pwr >= 0.0) {
			speed = pwr * mc_conf.lo_max_erpm;
		} else {
			speed = pwr * fabsf(mc_conf.lo_min_erpm);
		}
		VescToSTM_set_speed(speed);
	}
		break;
	default:
		break;
	}
//	FOCVars[M1].cycles_last = *DWT_CYCCNT - cycles;
//		if(FOCVars[M1].cycles_last > FOCVars[M1].cycles_max){
//			FOCVars[M1].cycles_max = FOCVars[M1].cycles_last;
//		}
}

float app_adc_get_decoded_level(void) {
	return decoded_level;
}
float app_adc_get_decoded_level2(void) {
	return decoded_level2;
}

void app_adc_stop_output(void) {
	if(xTimer!=NULL){
		xTimerStop(xTimer, 2000);
	}
}

void app_adc_set_mode(uint8_t mode_bit){
	m365_to_display.mode |= mode_bit;
}

void app_adc_clear_mode(uint8_t mode_bit){
	m365_to_display.mode &= ~mode_bit;
}

void app_adc_speed_mode(uint8_t speed){
	m365_to_display.mode &= 0xF8;
	m365_to_display.mode |= speed;
}

uint32_t app_updaterate(){
	return 2000 / config.update_rate_hz;
}

void app_check_timer(){
	if(xTimerIsTimerActive(xTimer)==pdFALSE){
		xTimerChangePeriod(xTimer, app_updaterate(),100);
		xTimerStart(xTimer, 100);
	}
}

void app_adc_init_timer(){
	if(xTimer==NULL){
		xTimer = xTimerCreate("ADC_UP",app_updaterate() , pdTRUE, ( void * ) 0,vTimerCallback );
	}
}

void app_timer_update_period(){
	xTimerChangePeriod(xTimer, app_updaterate(), 1000);
}

void task_app(void * argument)
{
	uint32_t rd_ptr=0;
	port_str * port = (port_str*) argument;
	uint8_t * usart_rx_dma_buffer = pvPortMalloc(port->rx_buffer_size);
	HAL_UART_MspInit(port->uart);
	if(port->half_duplex){
		HAL_HalfDuplex_Init(port->uart);
	}
	HAL_UART_Receive_DMA(port->uart, usart_rx_dma_buffer, port->rx_buffer_size);
	CLEAR_BIT(port->uart->Instance->CR3, USART_CR3_EIE);

	app_adc_init_timer();

	xTimerStart(xTimer, 100);


	uint16_t slow_update_cnt=0;
  /* Infinite loop */
	for(;;)
	{
		while(rd_ptr != uart_get_write_pos(port)) {
#if defined(G30P) && SESC_SHU_COMPAT
			if(shu_feed_stock_frame(usart_rx_dma_buffer[rd_ptr])) {
				shu_handoff_to_stock_iap();
			}
#endif
			if(ninebot_parse(usart_rx_dma_buffer[rd_ptr] ,&frame)	==0){
				//commands_printf(main_uart.phandle, "LEN: %d CMD: %x ARG: %x PAY: %02x %02x %02x %02x", frame.len, frame.cmd, frame.arg, frame.payload[0], frame.payload[1], frame.payload[2], frame.payload[3]);
				switch(frame.cmd){
					case 0x64:
						addCRC((uint8_t*)&m365_to_display, m365_to_display.len+6);
						my_uart_send_data((uint8_t*)&m365_to_display, sizeof(m365_to_display), port);
					break;
					case 0x65:
						adc1 = frame.payload[1];
						adc2 = frame.payload[2];
						VescToSTM_timeout_reset();
						app_check_timer();
						//commands_printf(main_uart.phandle, "LEN: %d CMD: %x ARG: %x PAY: %02x %02x %02x %02x", frame.len, frame.cmd, frame.arg, frame.payload[0], frame.payload[1], frame.payload[2], frame.payload[3]);
					break;
				}
			}
			rd_ptr++;
			rd_ptr &= ((uint32_t)port->rx_buffer_size - 1);
		}

		if(slow_update_cnt==0){
			if(m365_to_display.mode & 0x40){
				m365_to_display.speed = VescToSTM_get_speed()*2.2369;
			}else{
				m365_to_display.speed = VescToSTM_get_speed()*3.6;

			}
			m365_to_display.speed *= DIR_MUL;
			int temp = utils_map(VescToSTM_get_battery_level(0), 0, 1, 0, 100);
			m365_to_display.battery = temp>100?100:temp;
			m365_to_display.beep=0;
			m365_to_display.faultcode=pMCI[M1]->pSTM->hFaultOccurred;

		}else{
			slow_update_cnt++;
			if(slow_update_cnt==50) slow_update_cnt=0;
		}


		vTaskDelay(10);
		if(ulTaskNotifyTake(pdTRUE, 10)){
			xTimerStop(xTimer, 2000);
			HAL_UART_MspDeInit(port->uart);
			port->task_handle = NULL;
			vPortFree(usart_rx_dma_buffer);
			vTaskDelete(NULL);
			vTaskDelay(portMAX_DELAY);
		}

	}
}

void task_app_init(port_str * port){
	if(port->task_handle == NULL){
		xTaskCreate(task_app, "APP-ADC", 128, (void*)port, PRIO_BELOW_NORMAL, &port->task_handle);
	}else{
		app_timer_update_period();
	}
}

void task_app_kill(port_str * port){
	if(port->task_handle){
		xTaskNotify(port->task_handle, 0, eIncrement);
		vTaskDelay(200);
	}
}
