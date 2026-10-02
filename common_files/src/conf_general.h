/*
	Copyright 2017 - 2021 Benjamin Vedder	benjamin@vedder.se

	This file is part of the VESC firmware.

	The VESC firmware is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    The VESC firmware is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
    */

#ifndef CONF_GENERAL_H_
#define CONF_GENERAL_H_

#include "VescDatatypes.h"
#include "packet.h"
#include "product.h"


#define ADDR_FLASH_PAGE_126    ((uint32_t)0x08000000+(APP_PAGE*PAGE_SIZE))
#define ADDR_FLASH_PAGE_127    ((uint32_t)0x08000000+(CONF_PAGE*PAGE_SIZE))

extern mc_configuration mc_conf;
extern app_configuration appconf;

#ifdef G30P
#define G30_CONFIG_MAGIC   0x53474346u /* "SGCF" */
#define G30_CONFIG_VERSION 1u

#define G30_CFG_FLAG_STAR_VALID   (1u << 0)
#define G30_CFG_FLAG_DELTA_VALID  (1u << 1)
#define G30_CFG_FLAG_AUTO_DELTA   (1u << 2)

typedef struct {
	float r_ohm;
	float l_h;
	float flux_wb;
	float phase_current_max_a;
} g30_foc_profile_t;

typedef struct {
	uint32_t magic;
	uint16_t version;
	uint16_t size;
	uint16_t crc;
	uint16_t reserved0;
	g30_foc_profile_t star;
	g30_foc_profile_t delta;
	float battery_current_max_a;
	float delta_enter_kmh;
	float delta_exit_kmh;
	float switch_iq_a;
	float wheel_diameter_m;
	uint16_t relay_settle_ms;
	uint8_t motor_poles;
	uint8_t flags;
	uint8_t hall_table[8];
} g30_sesc_config_t;

void g30_config_init(void);
const g30_sesc_config_t *g30_config_get(void);
bool g30_config_store(void);
bool g30_config_set_profile(bool delta, const g30_foc_profile_t *profile);
bool g30_config_set_common(float battery_current_max_a, float wheel_diameter_m,
		uint8_t motor_poles, float delta_enter_kmh, float delta_exit_kmh,
		float switch_iq_a, uint16_t relay_settle_ms, bool auto_delta);
void g30_config_set_hall_table(const uint8_t hall_table[8]);
bool g30_config_apply_runtime_profile(bool delta);
bool g30_config_profile_valid(bool delta);
bool g30_config_auto_delta_enabled(void);
#endif

// Functions
void conf_general_init(void);
void conf_general_read_app_configuration(app_configuration *conf);
void conf_general_read_mc_configuration(mc_configuration *conf, bool is_motor_2);
bool conf_general_store_mc_configuration(mc_configuration *conf, bool is_motor_2);
void conf_update_override_current(mc_configuration *mcconf);
void conf_general_setup_mc(mc_configuration *mcconf);
void conf_general_calc_apply_foc_cc_kp_ki_gain(mc_configuration *mcconf, float tc);
void conf_general_update_current(mc_configuration *mcconf);
mc_configuration* mc_interface_get_configuration(void);
bool conf_general_store_app_configuration(app_configuration *conf);
void conf_general_mcconf_hw_limits(mc_configuration *mcconf);
int conf_general_detect_apply_all_foc_can(bool detect_can, float max_power_loss, float min_current_in, float max_current_in, float openloop_rpm, float sl_erpm, PACKET_STATE_t * phandle);
#endif /* CONF_GENERAL_H_ */
