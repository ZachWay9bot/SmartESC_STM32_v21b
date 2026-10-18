#pragma once
#include <stdint.h>
#include <stdbool.h>

#define G30SL_NO_SECTOR 255u

typedef struct {
    uint32_t cpu_hz;
    uint32_t observer_hz;
    uint16_t bemf_span_min;
    uint16_t min_speed_unit;
    uint16_t min_lock_edges;
    uint32_t r_mohm;
    uint32_t l_uh;
    uint32_t lambda_uwb;
} g30sl_core_config_t;

typedef struct {
    g30sl_core_config_t cfg;
    uint16_t a, b, c, span;
    uint8_t sector, last_sector;
    int8_t direction;
    int8_t edge_direction;
    uint16_t forward_edges, reverse_edges;
    uint32_t last_edge_cycles;
    uint32_t last_sample_cycles;
    uint32_t avg_edge_cycles;
    int16_t speed_unit;
    int16_t observer_speed_unit;
    uint16_t control_phase;
    uint16_t bemf_phase;
    uint16_t flux_phase;
    uint8_t rolling_locked;
    int32_t x_alpha_uwb;
    int32_t x_beta_uwb;
    int32_t psi_alpha_uwb;
    int32_t psi_beta_uwb;
    uint32_t flux_mag_uwb;
    uint16_t observer_phase;
    uint16_t last_observer_phase;
    uint16_t observer_good;
    uint16_t observer_bad;
    uint8_t observer_seeded;
    uint8_t observer_valid;
} g30sl_core_t;

void g30sl_core_init(g30sl_core_t *s, const g30sl_core_config_t *cfg);
void g30sl_core_reset_roll(g30sl_core_t *s);
void g30sl_core_set_motor(g30sl_core_t *s, uint32_t r_mohm, uint32_t l_uh, uint32_t lambda_uwb);
void g30sl_core_sample_bemf(g30sl_core_t *s, uint16_t a, uint16_t b, uint16_t c, uint32_t now_cycles);
bool g30sl_core_roll_ready(const g30sl_core_t *s, uint32_t now_cycles);
void g30sl_core_seed_observer_from_roll(g30sl_core_t *s, int32_t i_alpha_ma, int32_t i_beta_ma);
void g30sl_core_observer_step(g30sl_core_t *s,
                              int32_t i_alpha_ma, int32_t i_beta_ma,
                              int32_t v_alpha_mv, int32_t v_beta_mv);
bool g30sl_core_run_valid(const g30sl_core_t *s);
