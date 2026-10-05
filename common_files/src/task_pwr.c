/*
 * m365
 *
 * Copyright (c) 2021 Francois Deslandes
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

#include "task_pwr.h"
#include "task_LED.h"
#include "task_init.h"
#include "main.h"
#include "task.h"
#include "task_cli.h"
#include <string.h>
#include <math.h>
#include "VescCommand.h"
#include "music.h"
#include "ninebot.h"
#include "conf_general.h"
#include "VescToSTM.h"
#include "app.h"

//Not a real Task... it's called from safety task. No delays allowed

#define EXECUTION_SPEED		40			//every 40 ticks (20ms)

extern m365Answer m365_to_display;
//extern const uint8_t m365_mode[3];
uint32_t shutdown_limit = 0;

uint8_t buttonState() {
    static const uint32_t DEBOUNCE_MILLIS = 20u;
    static bool initialized = false;
    static GPIO_PinState last_raw = GPIO_PIN_SET;
    static bool stable_pressed = false;
    static uint32_t changed_ts = 0u;

    const GPIO_PinState raw = HAL_GPIO_ReadPin(PWR_BTN_GPIO_Port, PWR_BTN_Pin);
    const uint32_t now = HAL_GetTick();

    if(!initialized) {
        initialized = true;
        last_raw = raw;
        stable_pressed = (raw == GPIO_PIN_RESET);
        changed_ts = now;
    }

    if(raw != last_raw) {
        last_raw = raw;
        changed_ts = now;
    }

    if((uint32_t)(now - changed_ts) >= DEBOUNCE_MILLIS) {
        /* G30 Gen1 power-button line is pulled up and pressed active-low. */
        stable_pressed = (last_raw == GPIO_PIN_RESET);
    }

    return stable_pressed ? 1u : 0u;
}

eButtonEvent getButtonEvent()
{
    static const uint32_t DOUBLE_GAP_MILLIS_MAX 	= 250;
    static const uint32_t SINGLE_PRESS_MILLIS_MAX 	= 300;
    static const uint32_t LONG_PRESS_MILLIS_MAX 	= 10000;

    static uint32_t button_down_ts = 0 ;
    static uint32_t button_up_ts = 0 ;
    static bool double_pending = false ;
    static bool button_down = false ;
    static bool very_long_sent = false ;

    eButtonEvent button_event = NO_PRESS ;
    uint32_t now = HAL_GetTick() ;

    if( button_down != buttonState() ) {
        button_down = !button_down ;
        if( button_down ) {
            button_down_ts = now ;
            very_long_sent = false ;
        } else {
            very_long_sent = false ;
            button_up_ts = now ;
            if( double_pending ) {
                button_event = DOUBLE_PRESS ;
                double_pending = false ;
            }
            else {
                double_pending = true ;
            }
        }
    }

    uint32_t diff =  button_up_ts - button_down_ts;
    if (!button_down && double_pending && now - button_up_ts > DOUBLE_GAP_MILLIS_MAX) {
    	double_pending = false ;
    	button_event = SINGLE_PRESS ;
	} else if (!button_down && double_pending && diff >= SINGLE_PRESS_MILLIS_MAX && diff <= LONG_PRESS_MILLIS_MAX) {
		double_pending = false ;
		button_event = LONG_PRESS ;
	} else if (button_down && !very_long_sent && now - button_down_ts > LONG_PRESS_MILLIS_MAX) {
		double_pending = false ;
		very_long_sent = true ;
		button_event = VERY_LONG_PRESS ;
	}

    return button_event ;
}

void PWR_set_shutdown_time(uint32_t seconds){

	shutdown_limit = seconds * 2000;

}

//This is not a FreeRTOS Task... its called from safety task to safe some heap space every 500us
void task_PWR(void *argument) {
	static uint8_t main_loop_counter = 0;
	static uint32_t shutdown_timer = 0;


	if(SpeednTorqCtrlM1.SPD->hAvrMecSpeedUnit){
		shutdown_timer = 0;
	}else if (shutdown_limit > 0){
		shutdown_timer++;
		if(shutdown_timer>shutdown_limit){
			shutdown_timer=0;
			power_control(DEV_PWR_OFF);
		}
	}

	if(main_loop_counter > 40){
		main_loop_counter=0;
		switch( getButtonEvent() ){
			  case NO_PRESS : break ;
			  case SINGLE_PRESS : {
				  m365_to_display.light = !m365_to_display.light;
#ifndef G30P
				  if(m365_to_display.light){
					  task_LED_set_brake_light(BRAKE_LIGHT_ON);
				  }else{
					  task_LED_set_brake_light(BRAKE_LIGHT_OFF);
				  }
#endif

			  } break ;
			  case LONG_PRESS :   {
				  power_control(DEV_PWR_OFF);

			  } break ;
			  case VERY_LONG_PRESS :   {
#if defined(G30P) && SESC_SHU_COMPAT
				  /*
				   * Manual recovery path. Once the scooter is stationary and Iq has
				   * collapsed, deliberately invalidate only the application's initial
				   * stack-pointer word. On reset the preserved stock bootloader sees
				   * an invalid app and remains available for a recovery flash.
				   */
				  if(fabsf(VescToSTM_get_speed()) < 0.5f &&
					 fabsf(VescToSTM_get_iq()) <= DELTA_SWITCH_MAX_IQ_A &&
					 app_adc_get_decoded_level() <= 0.02f &&
					 app_adc_get_decoded_level2() >= 0.80f) {
					  /*
					   * Deliberate recovery gesture: >10 s power-button hold
					   * while stationary, throttle neutral and brake held.
					   */
					  VescToSTM_pwm_stop();
					  HAL_GPIO_WritePin(DELTA_RELAY_GPIO_Port, DELTA_RELAY_Pin, GPIO_PIN_RESET);
					  if(app_shu_invalidate_app_vector()) {
						  __disable_irq();
						  NVIC_SystemReset();
					  }
				  } else {
					  /* Ordinary very-long hold is just a safe power-off. */
					  power_control(DEV_PWR_OFF);
				  }
#endif
			  } break ;
			  case DOUBLE_PRESS : {
				  uint32_t kmh=0;
				  switch(m365_to_display.mode){
				  	case M365_MODE_DRIVE:
				  		app_adc_speed_mode(M365_MODE_SPORT);
						kmh = mc_conf.modes_kmh_limits[2];
						mc_conf.lo_current_max_scale =  mc_conf.modes_curr_scale[2];
						break;
				  	case M365_MODE_SPORT:
				  		app_adc_speed_mode(M365_MODE_SLOW);
				  		kmh = mc_conf.modes_kmh_limits[0];
				  		mc_conf.lo_current_max_scale = mc_conf.modes_curr_scale[0];
						break;
				  	case M365_MODE_SLOW:
				  		app_adc_speed_mode(M365_MODE_DRIVE);
				  		kmh = mc_conf.modes_kmh_limits[1];
				  		mc_conf.lo_current_max_scale = mc_conf.modes_curr_scale[1];
						break;
				  }
				  if(kmh==1337){
					  mc_conf.lo_max_erpm = mc_conf.l_max_erpm;
				  }else{
					  mc_conf.lo_max_erpm = (((float)kmh * 1000.0 / 60.0)/(mc_conf.si_wheel_diameter*M_PI)) * mc_conf.si_motor_poles * mc_conf.si_gear_ratio;
				  }
				  MCI_ExecSpeedRamp(pMCI[M1], VescToSTM_erpm_to_speed(mc_conf.lo_max_erpm), 0);
			  } break ;
		 }
	}
	main_loop_counter++;
}

void task_PWR_init(port_str * port) {
	/* Check button pressed state at startup */
	buttonState();

    /* Power ON board temporarily, ultimate decision to keep hardware ON or OFF is made later */
	power_control(DEV_PWR_ON);

}

void power_control(uint8_t pwr)
{
	if(pwr == DEV_PWR_ON) {
		/* Turn the PowerON line high to keep the board powered on even when
		 * the power button is released
		 */
		HAL_GPIO_WritePin(TPS_ENA_GPIO_Port, TPS_ENA_Pin, GPIO_PIN_SET);
	} else if(pwr == DEV_PWR_OFF) {
#ifdef G30P
		/*
		 * G30 Gen1 PA12 is active-low while PA11 is the power-hold output.
		 * Drop the hold line immediately. Waiting while PA12 is high would
		 * deadlock an inactivity shutdown until somebody presses the button.
		 */
		HAL_GPIO_WritePin(TPS_ENA_GPIO_Port, TPS_ENA_Pin, GPIO_PIN_RESET);
		while(1) { }
#else
		vTaskDelay(1);
		while(HAL_GPIO_ReadPin(PWR_BTN_GPIO_Port, PWR_BTN_Pin));
		HAL_GPIO_WritePin(TPS_ENA_GPIO_Port, TPS_ENA_Pin, GPIO_PIN_RESET);
		while(1);
#endif
	} else if(pwr == DEV_PWR_RESTART) {

		/* Restart the system */
		NVIC_SystemReset();
	}
}
