#include "main.h"
#include "defines.h"


#ifndef APP_PRODUCT_H_
#define APP_PRODUCT_H_
 /*  Phase current (int16_t 0-to-peak) = (Phase current (A 0-to-peak)* 32767 * Rshunt *
                                   *Amplifying network gain)/(MCU supply voltage/2)
*/

#ifdef G30P

#define VBUS_ADC_CHANNEL                                                     MC_ADC_CHANNEL_1
#define VOLTAGE_DIVIDER_GAIN     											 (float)3363.5

#define VESC_USART                                                 			 USART1

#define VESC_USART_DMA													     huart1
#define VESC_USART_TX_DMA													 hdma_usart1_tx
#define VESC_USART_RX_DMA													 hdma_usart1_rx

#define APP_USART_DMA														 huart2
#define APP_USART_TX_DMA												     hdma_usart2_tx
#define APP_USART_RX_DMA													 hdma_usart2_rx

#define APP2_USART_DMA														 huart3
#define APP2_USART_TX_DMA												     hdma_usart3_tx
#define APP2_USART_RX_DMA													 hdma_usart3_rx

#define RSHUNT                        										 0.00200
/*
 * G30 schematic nominal current-sense gain is 1 + 24k/3k = 9.0.
 * Upstream uses 9.4336, likely as empirical calibration. Keep that value
 * until a controlled current calibration is done on the real controller.
 */
#define AMPLIFICATION_GAIN            										 9.4336
#define NOMINAL_CURRENT         											 2000
#define ID_DEMAG															 -2000

#define SCOPE_UVW															 0

#define POLE_PAIR_NUM                                                 	 	 (uint8_t)14
#define HALL_PHASE_SHIFT        											 90
#define HALL_SENSORS_PLACEMENT  											 DEGREES_120
#define HALL_FAULT_RESET_CNT												 200

#define TEMP_SENSOR_TYPE													 VIRTUAL_SENSOR
#define CURR_SENSOR_TYPE													 REAL_SENSOR

#define ADC_SAMPLE_MAX_LEN 													 500

#define BRAKE_LIGHT_GPIO_Port												 REAR_LED_GPIO_Port
#define BRAKE_LIGHT_Pin														 REAR_LED_Pin

/*
 * G30 custom ride behaviour.
 * Rear LED output is repurposed as the external STAR/DELTA relay control.
 * Hardware is fail-safe: GPIO low (RESET) = STAR, released/high = DELTA.
 */
#define SESC_NO_REGEN                                                       1
/*
 * Bring-up policy: prove stock STAR + Hall FOC first.
 * No automatic or setup-forced STAR/DELTA switching on this branch.
 */
#define G30_SENSORED_BRINGUP                                               1
#define DELTA_RELAY_ENABLE                                                  0
#define SESC_SHU_COMPAT                                                     1
#define SESC_SHU_LITE                                                       1
#define SESC_SHU_MAX_APP_BYTES                                              (52u * 1024u)
#define G30_BMS_ACTIVATOR_ENABLE                                            1
#define G30_BMS_ACTIVATOR_PERIOD_MS                                         (200u)
#define G30_BMS_POLL_PERIOD_MS                                              (400u)
#define G30_BMS_ONLINE_TIMEOUT_MS                                           (2000u)
#define TRUE_COAST_IQ_A                                                     (1.5f)
#define DELTA_ENTER_SPEED_KMH                                               (32.0f)
#define DELTA_EXIT_SPEED_KMH                                                (26.0f)
#define DELTA_SWITCH_MAX_IQ_A                                               (2.0f)
#define DELTA_RELAY_SETTLE_MS                                               (100u)

// Setting limits
#if G30_SENSORED_BRINGUP
#define HW_LIM_CURRENT            -12.0, 12.0
#define HW_LIM_CURRENT_IN         -8.0, 8.0
#define HW_LIM_CURRENT_ABS        0.0, 15.0
#else
#define HW_LIM_CURRENT            -70.0, 70.0
#define HW_LIM_CURRENT_IN         -70.0, 70.0
#define HW_LIM_CURRENT_ABS        0.0, 100.0
#endif
#define HW_LIM_VIN				6.0, 57.0
#define HW_LIM_ERPM				-100e3, 100e3
#define HW_LIM_DUTY_MIN			0.0, 0.1
#define HW_LIM_DUTY_MAX			0.0, 0.99
#define HW_LIM_TEMP_FET			-40.0, 75.0
#define HW_LIM_F_SW			    4000.0, 20000.0

#define MOT_TMR_MHZ 64
/*
 * Upstream G30 sat essentially on the 20 KiB SRAM ceiling. The previous
 * candidate linked with data+bss = 20,436 bytes, leaving only 44 bytes of
 * static headroom. Several independent G30 forks reduced the RTOS heap to
 * 13 KiB to make the target robustly link. Scope capture is disabled on G30,
 * and automatic motor detection is disabled in this bring-up candidate.
 */
#define HEAP_SIZE_KB 13
#define CPU_MHZ  (64*1000000)
/*
 * Do not use pages 126/127 here. Stock G30 reserves the last 2 KiB for
 * update-control data used by the IAP/SHU rollback path.
 *
 * The stock application region ends at 0x0800DFFF (page 55). Pages 56/57
 * (0x0800E000..0x0800E7FF) are used for SmartESC app/motor configuration.
 * The documented stock update staging starts at 0x0800E800, so the normal
 * IAP staging/calibration/update-control ranges remain available.
 */
#define APP_PAGE				56
#define CONF_PAGE				57
#define PAGE_SIZE				0x400

#endif

#ifdef M365
#define VBUS_ADC_CHANNEL                                                     MC_ADC_CHANNEL_2
#define PHASE_A_V_ADC_CHANNEL                                                MC_ADC_CHANNEL_6
#define PHASE_B_V_ADC_CHANNEL                                                MC_ADC_CHANNEL_7
#define PHASE_C_V_ADC_CHANNEL                                                MC_ADC_CHANNEL_9
#define VOLTAGE_DIVIDER_GAIN     											 (float)2808.6359

#define VESC_USART_DMA													     huart3
#define VESC_USART_TX_DMA													 hdma_usart3_tx
#define VESC_USART_RX_DMA													 hdma_usart3_rx

#define APP_USART_DMA														 huart1
#define APP_USART_TX_DMA												     hdma_usart1_tx
#define APP_USART_RX_DMA													 hdma_usart1_rx

//Current Measurement
#define RSHUNT                        										 0.00200
#define AMPLIFICATION_GAIN            										 8.00
#define NOMINAL_CURRENT         											 2000
#define ID_DEMAG														     -2000

#define SCOPE_UVW															 1

#define POLE_PAIR_NUM                                                 	 	 (uint8_t)15
#define HALL_PHASE_SHIFT        											 90
#define HALL_FAULT_RESET_CNT												 200

#define TEMP_SENSOR_TYPE													 REAL_SENSOR
#define CURR_SENSOR_TYPE													 VIRTUAL_SENSOR

#define ADC_SAMPLE_MAX_LEN 													 1000

// Setting limits
#define HW_LIM_CURRENT			-70.0, 70.0
#define HW_LIM_CURRENT_IN		-70.0, 70.0
#define HW_LIM_CURRENT_ABS		0.0, 100.0
#define HW_LIM_VIN				6.0, 56.0
#define HW_LIM_ERPM				-100e3, 100e3
#define HW_LIM_DUTY_MIN			0.0, 0.1
#define HW_LIM_DUTY_MAX			0.0, 0.99
#define HW_LIM_TEMP_FET			-40.0, 75.0
#define HW_LIM_F_SW			    4000.0, 20000.0

#define MOT_TMR_MHZ 64
#define HEAP_SIZE_KB 14
#define CPU_MHZ  (64*1000000)
#define APP_PAGE				126
#define CONF_PAGE				127
#define PAGE_SIZE				0x400


#endif

#ifdef M365_gd32
#define VBUS_ADC_CHANNEL                                                     MC_ADC_CHANNEL_2
#define PHASE_A_V_ADC_CHANNEL                                                MC_ADC_CHANNEL_6
#define PHASE_B_V_ADC_CHANNEL                                                MC_ADC_CHANNEL_7
#define PHASE_C_V_ADC_CHANNEL                                                MC_ADC_CHANNEL_9
#define VOLTAGE_DIVIDER_GAIN     											 (float)2808.6359

#define VESC_USART_DMA													     huart3
#define VESC_USART_TX_DMA													 hdma_usart3_tx
#define VESC_USART_RX_DMA													 hdma_usart3_rx

#define APP_USART_DMA														 huart1
#define APP_USART_TX_DMA												     hdma_usart1_tx
#define APP_USART_RX_DMA													 hdma_usart1_rx

//Current Measurement
#define RSHUNT                        										 0.00200
#define AMPLIFICATION_GAIN            										 8.00
#define NOMINAL_CURRENT         											 2000
#define ID_DEMAG														     -2000

#define SCOPE_UVW															 1

#define POLE_PAIR_NUM                                                 	 	 (uint8_t)15
#define HALL_PHASE_SHIFT        											 90
#define HALL_FAULT_RESET_CNT												 200

#define TEMP_SENSOR_TYPE													 REAL_SENSOR
#define CURR_SENSOR_TYPE													 VIRTUAL_SENSOR

#define ADC_SAMPLE_MAX_LEN 													 2000

// Setting limits
#define HW_LIM_CURRENT			-70.0, 70.0
#define HW_LIM_CURRENT_IN		-70.0, 70.0
#define HW_LIM_CURRENT_ABS		0.0, 100.0
#define HW_LIM_VIN				6.0, 56.0
#define HW_LIM_ERPM				-100e3, 100e3
#define HW_LIM_DUTY_MIN			0.0, 0.1
#define HW_LIM_DUTY_MAX			0.0, 0.99
#define HW_LIM_TEMP_FET			-40.0, 75.0
#define HW_LIM_F_SW			    4000.0, 50000.0

#define MOT_TMR_MHZ 60
#define HEAP_SIZE_KB 80
#define CPU_MHZ  (120*1000000)
#define APP_PAGE				255
#define CONF_PAGE				254
#define PAGE_SIZE				0x800


#endif
/****************************************************************************/

#define KMH_NO_LIMIT														 1337
#define PRODUCT_FIRMWARE_VERSION                                      		 0x0001
#if defined(G30P) && SESC_SHU_LITE
/*
 * The stock G30 IAP application window is only 52 KiB. The full VESC Tool
 * command/serialization stack makes SmartESC substantially larger than that,
 * so the reversible SHU image is deliberately a compact ride build.
 * The normal branch keeps VESC Tool support.
 */
#define VESC_TOOL_ENABLE                                                     0
#define ERROR_PRINTING                                                       0
#define BATTERY_SUPPORT_LIION                                                1
#define BATTERY_SUPPORT_LIFEPO                                               0
#define BATTERY_SUPPORT_LEAD                                                 0
#else
#define VESC_TOOL_ENABLE													 1
#define ERROR_PRINTING														 1
#define BATTERY_SUPPORT_LIION												 1
#define BATTERY_SUPPORT_LIFEPO												 1
#define BATTERY_SUPPORT_LEAD												 1
#endif
#define AUTO_RESET_FAULT													 1
#define MUSIC_ENABLE														 0
#define ABS_OVR_CURRENT_TRIP_MS												 2.0
#define MIN_DUTY_FOR_PWM_FREEWHEEL											 20
#define CURRENT_DISPLAY_OFFSET											     80   //in cnts

#define MODE_SLOW_CURR														 0.5
#define MODE_DRIVE_CURR														 0.8
#define MODE_SPORT_CURR														 1.0
#define MODE_SLOW_SPEED														 10
#define MODE_DRIVE_SPEED													 25
#define MODE_SPORT_SPEED													 KMH_NO_LIMIT

#define BATTERY_VOLTAGE_GAIN     											 ((VOLTAGE_DIVIDER_GAIN * ADC_GAIN) * 512.0)
#define CURRENT_FACTOR_A 													 ((32767.0*RSHUNT*AMPLIFICATION_GAIN)/(3.3/2))
#define CURRENT_FACTOR_mA 													 (CURRENT_FACTOR_A/1000.0)
#define MIN_DUTY_PWM												         (32768 * MIN_DUTY_FOR_PWM_FREEWHEEL / 100)

#define DEMCR_TRCENA    0x01000000
#define DEMCR           (*((volatile uint32_t *)0xE000EDFC))
#define DWT_CTRL        (*(volatile uint32_t *)0xe0001000)
#define CYCCNTENA       (1<<0)
#define DWT_CYCCNT      ((volatile uint32_t *)0xE0001004)
#define CPU_CYCLES      *DWT_CYCCNT
#define CPU_CLOCK		64000000


#define PRIO_BELOW_NORMAL 4
#define PRIO_NORMAL  5
#define PRIO_HIGHER  6

#endif /* APP_PRODUCT_H_ */
