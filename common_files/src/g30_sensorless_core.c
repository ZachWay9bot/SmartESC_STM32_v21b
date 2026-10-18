#include "g30_sensorless_core.h"
#include <string.h>

#define INV_SQRT3_Q15 18919
#define PHASE_90 16384u
#define PHASE_180 32768u
#define OBS_MIN_GOOD 20u
#define OBS_MAX_BAD 20u

static uint32_t uabs32(int32_t x) { return (uint32_t)(x < 0 ? -(int64_t)x : x); }
static int16_t phase_delta(uint16_t to, uint16_t from) { return (int16_t)(to - from); }

static uint8_t sector_from_abc(uint16_t a, uint16_t b, uint16_t c) {
    if (a >= b) { if (b >= c) return 0u; if (a >= c) return 5u; return 4u; }
    if (a >= c) return 1u;
    if (b >= c) return 2u;
    return 3u;
}

static uint16_t atan2_turn(int32_t y, int32_t x) {
    static const uint16_t at[15] = {
        8192u, 4836u, 2555u, 1297u, 651u, 326u, 163u, 81u,
        41u, 20u, 10u, 5u, 3u, 1u, 1u
    };
    if (x == 0 && y == 0) return 0u;
    int32_t xi = x, yi = y;
    int32_t z = 0;
    if (xi < 0) { xi = -xi; yi = -yi; z = (int32_t)PHASE_180; }
    for (unsigned i = 0; i < 15u; i++) {
        int32_t xn, yn;
        if (yi > 0) {
            xn = xi + (yi >> i); yn = yi - (xi >> i); z += at[i];
        } else {
            xn = xi - (yi >> i); yn = yi + (xi >> i); z -= at[i];
        }
        xi = xn; yi = yn;
    }
    return (uint16_t)z;
}

static uint32_t mag_fast(int32_t x, int32_t y) {
    uint32_t ax = uabs32(x), ay = uabs32(y);
    uint32_t hi = ax > ay ? ax : ay;
    uint32_t lo = ax > ay ? ay : ax;
    return hi + ((lo * 3u) >> 3);
}

void g30sl_core_init(g30sl_core_t *s, const g30sl_core_config_t *cfg) {
    memset(s, 0, sizeof(*s));
    s->cfg = *cfg;
    s->sector = s->last_sector = G30SL_NO_SECTOR;
}

void g30sl_core_reset_roll(g30sl_core_t *s) {
    s->a = s->b = s->c = s->span = 0u;
    s->sector = s->last_sector = G30SL_NO_SECTOR;
    s->direction = s->edge_direction = 0;
    s->forward_edges = s->reverse_edges = 0u;
    s->last_edge_cycles = s->last_sample_cycles = s->avg_edge_cycles = 0u;
    s->speed_unit = 0;
    s->rolling_locked = 0u;
}

void g30sl_core_set_motor(g30sl_core_t *s, uint32_t r_mohm, uint32_t l_uh, uint32_t lambda_uwb) {
    if (r_mohm) s->cfg.r_mohm = r_mohm;
    if (l_uh) s->cfg.l_uh = l_uh;
    if (lambda_uwb) s->cfg.lambda_uwb = lambda_uwb;
}

void g30sl_core_sample_bemf(g30sl_core_t *s, uint16_t a, uint16_t b, uint16_t c, uint32_t now_cycles) {
    uint16_t hi = a, lo = a;
    if (b > hi) hi = b;
    if (c > hi) hi = c;
    if (b < lo) lo = b;
    if (c < lo) lo = c;
    s->a = a; s->b = b; s->c = c; s->span = (uint16_t)(hi - lo);
    s->last_sample_cycles = now_cycles;
    if (s->span < s->cfg.bemf_span_min) {
        s->rolling_locked = 0u; s->direction = 0; s->speed_unit = 0;
        s->last_sector = G30SL_NO_SECTOR; s->last_edge_cycles = 0u;
        return;
    }

    int32_t cm = ((int32_t)a + (int32_t)b + (int32_t)c) / 3;
    int32_t ea = (int32_t)a - cm;
    int32_t eb = (int32_t)b - cm;
    int32_t ealpha = ea;
    int32_t ebeta = -((int32_t)(((int64_t)(ea + 2 * eb) * INV_SQRT3_Q15) >> 15));
    s->bemf_phase = atan2_turn(ebeta, ealpha);

    uint8_t sec = sector_from_abc(a, b, c);
    s->sector = sec;
    if (s->last_sector == G30SL_NO_SECTOR) {
        s->last_sector = sec; s->last_edge_cycles = now_cycles; return;
    }
    if (sec == s->last_sector) return;

    uint8_t step = (uint8_t)((sec + 6u - s->last_sector) % 6u);
    uint32_t dt = now_cycles - s->last_edge_cycles;
    s->last_sector = sec; s->last_edge_cycles = now_cycles;
    if (step != 1u && step != 5u) {
        s->rolling_locked = 0u; s->direction = 0;
        s->forward_edges = s->reverse_edges = 0u; s->avg_edge_cycles = 0u;
        return;
    }
    if (dt < (s->cfg.cpu_hz / 2000u) || dt > (s->cfg.cpu_hz / 4u)) {
        s->rolling_locked = 0u; s->forward_edges = s->reverse_edges = 0u;
        s->avg_edge_cycles = 0u;
        return;
    }

    int8_t dir = step == 1u ? 1 : -1;
    s->edge_direction = dir;
    if (dir > 0) {
        if (s->forward_edges < 65535u) s->forward_edges++;
        s->reverse_edges = 0u;
    } else {
        if (s->reverse_edges < 65535u) s->reverse_edges++;
        s->forward_edges = 0u;
    }
    s->direction = dir;

    if (!s->avg_edge_cycles) s->avg_edge_cycles = dt;
    else s->avg_edge_cycles = (3u * s->avg_edge_cycles + dt + 2u) >> 2;
    if (s->avg_edge_cycles) {
        uint32_t su = (uint32_t)(((uint64_t)s->cfg.cpu_hz * 10ull) /
                                 (6ull * s->avg_edge_cycles));
        if (su > 32767u) su = 32767u;
        s->speed_unit = dir > 0 ? (int16_t)su : -(int16_t)su;
    }

    s->control_phase = (dir > 0) ? (uint16_t)(0u - s->bemf_phase)
                                  : (uint16_t)(PHASE_180 - s->bemf_phase);

    uint16_t edges = dir > 0 ? s->forward_edges : s->reverse_edges;
    if (edges >= s->cfg.min_lock_edges &&
        uabs32(s->speed_unit) >= s->cfg.min_speed_unit) s->rolling_locked = 1u;
}

bool g30sl_core_roll_ready(const g30sl_core_t *s, uint32_t now_cycles) {
    if (!s->rolling_locked || !s->last_edge_cycles || !s->speed_unit) return false;
    if ((uint32_t)(now_cycles - s->last_edge_cycles) > (s->cfg.cpu_hz / 12u)) return false;
    return true;
}

void g30sl_core_seed_observer_from_roll(g30sl_core_t *s, int32_t i_alpha_ma, int32_t i_beta_ma) {
    if (!s->rolling_locked || !s->cfg.lambda_uwb) return;
    int32_t cm = ((int32_t)s->a + (int32_t)s->b + (int32_t)s->c) / 3;
    int32_t ea = (int32_t)s->a - cm;
    int32_t eb = (int32_t)s->b - cm;
    int32_t ealpha = ea;
    int32_t ebeta = -((int32_t)(((int64_t)(ea + 2 * eb) * INV_SQRT3_Q15) >> 15));
    uint32_t em = mag_fast(ealpha, ebeta);
    if (!em) return;

    int32_t pa, pb;
    if (s->direction > 0) { pa = -ebeta; pb = ealpha; }
    else { pa = ebeta; pb = -ealpha; }
    pa = (int32_t)(((int64_t)pa * s->cfg.lambda_uwb) / em);
    pb = (int32_t)(((int64_t)pb * s->cfg.lambda_uwb) / em);
    s->psi_alpha_uwb = pa; s->psi_beta_uwb = pb;
    s->x_alpha_uwb = pa + (int32_t)(((int64_t)s->cfg.l_uh * i_alpha_ma) / 1000);
    s->x_beta_uwb  = pb + (int32_t)(((int64_t)s->cfg.l_uh * i_beta_ma) / 1000);
    s->flux_mag_uwb = mag_fast(pa, pb);
    s->flux_phase = atan2_turn(pb, pa);
    s->observer_phase = (uint16_t)(PHASE_90 - s->flux_phase);
    s->last_observer_phase = s->observer_phase;
    s->observer_speed_unit = s->speed_unit;
    s->observer_good = s->observer_bad = 0u;
    s->observer_seeded = 1u;
    s->observer_valid = 0u;
}

void g30sl_core_observer_step(g30sl_core_t *s,
                              int32_t i_alpha_ma, int32_t i_beta_ma,
                              int32_t v_alpha_mv, int32_t v_beta_mv) {
    if (!s->observer_seeded || !s->cfg.observer_hz || !s->cfg.lambda_uwb) return;

    int32_t ri_a_mv = (int32_t)(((int64_t)s->cfg.r_mohm * i_alpha_ma) / 1000);
    int32_t ri_b_mv = (int32_t)(((int64_t)s->cfg.r_mohm * i_beta_ma) / 1000);
    s->x_alpha_uwb += (int32_t)(((int64_t)(v_alpha_mv - ri_a_mv) * 1000) /
                                s->cfg.observer_hz);
    s->x_beta_uwb  += (int32_t)(((int64_t)(v_beta_mv - ri_b_mv) * 1000) /
                                s->cfg.observer_hz);

    int32_t lia = (int32_t)(((int64_t)s->cfg.l_uh * i_alpha_ma) / 1000);
    int32_t lib = (int32_t)(((int64_t)s->cfg.l_uh * i_beta_ma) / 1000);
    int32_t pa = s->x_alpha_uwb - lia;
    int32_t pb = s->x_beta_uwb - lib;
    uint32_t mag = mag_fast(pa, pb);
    s->flux_mag_uwb = mag;
    if (!mag) {
        if (s->observer_bad < 65535u) s->observer_bad++;
        return;
    }

    int32_t radial = ((int32_t)s->cfg.lambda_uwb - (int32_t)mag) >> 3;
    pa += (int32_t)(((int64_t)pa * radial) / (int32_t)mag);
    pb += (int32_t)(((int64_t)pb * radial) / (int32_t)mag);
    s->x_alpha_uwb = pa + lia;
    s->x_beta_uwb = pb + lib;
    s->psi_alpha_uwb = pa; s->psi_beta_uwb = pb;

    s->flux_phase = atan2_turn(pb, pa);
    uint16_t theta = (uint16_t)(PHASE_90 - s->flux_phase);
    int16_t dtheta = phase_delta(theta, s->last_observer_phase);
    s->last_observer_phase = theta;
    s->observer_phase = theta;

    int32_t su = ((int32_t)dtheta * (int32_t)s->cfg.observer_hz * 10) / 65536;
    if (su > 32767) su = 32767;
    if (su < -32767) su = -32767;
    if (!s->observer_speed_unit) s->observer_speed_unit = (int16_t)su;
    else s->observer_speed_unit =
        (int16_t)((3 * (int32_t)s->observer_speed_unit + su) / 4);

    uint32_t lo = s->cfg.lambda_uwb / 2u;
    uint32_t hi = (s->cfg.lambda_uwb * 3u) / 2u;
    uint32_t ad = uabs32(dtheta);
    uint8_t sane = (uint8_t)(mag >= lo && mag <= hi && ad < PHASE_90);
    if (sane) {
        if (s->observer_good < 65535u) s->observer_good++;
        s->observer_bad = 0u;
    } else {
        if (s->observer_bad < 65535u) s->observer_bad++;
        if (s->observer_good) s->observer_good--;
    }
    if (s->observer_good >= OBS_MIN_GOOD) s->observer_valid = 1u;
    if (s->observer_bad >= OBS_MAX_BAD) s->observer_valid = 0u;
}

bool g30sl_core_run_valid(const g30sl_core_t *s) {
    return s->observer_seeded && s->observer_valid && s->observer_bad < OBS_MAX_BAD;
}
