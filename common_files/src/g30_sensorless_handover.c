#include "g30_sensorless_handover.h"

static uint16_t abs16(int16_t v) {
    int32_t x = v;
    if (x < 0) x = -x;
    return (uint16_t)x;
}

static uint16_t sat_add(uint16_t v, uint16_t add, uint16_t maxv) {
    uint32_t x = (uint32_t)v + add;
    return (uint16_t)(x > maxv ? maxv : x);
}

static uint16_t sat_sub(uint16_t v, uint16_t sub) {
    return v > sub ? (uint16_t)(v - sub) : 0u;
}

bool g30_sl_speed_coherent(uint16_t open_step, uint16_t observer_step) {
    if (open_step == 0u || observer_step == 0u) return false;

    /* Hardware-proven XBOT capture band: observer 50..150% of the currently
     * commanded open-loop electrical speed. The G30 adapter may tighten this
     * later after real current/observer data exists. */
    return ((uint32_t)observer_step * 2u >= (uint32_t)open_step) &&
           ((uint32_t)observer_step * 2u <= (uint32_t)open_step * 3u);
}

void g30_sl_config_xbot316_reference(g30_sl_config_t *cfg) {
    if (cfg == 0) return;

    /* Reference values are expressed in the XBOT v0.3.16 4 kHz control ticks.
     * They are provenance/reference defaults, not an instruction to run the
     * G30 at 4 kHz. A future G30 adapter must scale time values to its actual
     * control rate. */
    cfg->align_ticks = 1200u;              /* 300 ms at 4 kHz */
    cfg->open_timeout_ticks = 18000u;      /* 4.5 s at 4 kHz */
    cfg->blend_ticks = 1600u;              /* 400 ms at 4 kHz */
    cfg->lock_score_required = 10u;
    cfg->lock_score_max = 24u;
    cfg->phase_good = 12288u;              /* 67.5 electrical degrees */
    cfg->phase_accept = 16384u;            /* 90 electrical degrees */
    cfg->direction_lock_score = 3;
    cfg->direction_fault_score = -6;
    cfg->direction_fault_min_evidence = 20u;
}

void g30_sl_init(g30_sl_handover_t *h) {
    if (h == 0) return;
    h->state = G30_SL_OFF;
    h->fault = G30_SL_FAULT_NONE;
    h->state_ticks = 0u;
    h->lock_score = 0u;
    h->blend_q15 = 0u;
}

void g30_sl_start(g30_sl_handover_t *h) {
    if (h == 0) return;
    h->state = G30_SL_ALIGN;
    h->fault = G30_SL_FAULT_NONE;
    h->state_ticks = 0u;
    h->lock_score = 0u;
    h->blend_q15 = 0u;
}

void g30_sl_stop(g30_sl_handover_t *h) {
    if (h == 0) return;
    h->state = G30_SL_OFF;
    h->fault = G30_SL_FAULT_NONE;
    h->state_ticks = 0u;
    h->lock_score = 0u;
    h->blend_q15 = 0u;
}

static void g30_sl_fault(g30_sl_handover_t *h, g30_sl_fault_t f) {
    h->fault = f;
    h->state = G30_SL_FAULT;
    h->blend_q15 = 0u;
}

static void update_lock_score(g30_sl_handover_t *h,
                              const g30_sl_config_t *cfg,
                              const g30_sl_input_t *in) {
    if (!in->anchor_event) return;

    if (in->reverse_event) {
        h->lock_score = sat_sub(h->lock_score, 2u);
        return;
    }

    uint16_t e = abs16(in->phase_error);
    if (e < cfg->phase_good) {
        h->lock_score = sat_add(h->lock_score, 2u, cfg->lock_score_max);
    } else if (e < cfg->phase_accept) {
        h->lock_score = sat_add(h->lock_score, 1u, cfg->lock_score_max);
    } else {
        h->lock_score = sat_sub(h->lock_score, 1u);
    }
}

void g30_sl_update(g30_sl_handover_t *h, const g30_sl_config_t *cfg,
                   const g30_sl_input_t *in) {
    if (h == 0 || cfg == 0 || in == 0) return;
    if (h->state == G30_SL_OFF || h->state == G30_SL_FAULT) return;

    h->state_ticks++;

    switch (h->state) {
    case G30_SL_ALIGN:
        if (h->state_ticks >= cfg->align_ticks) {
            h->state = G30_SL_OPEN;
            h->state_ticks = 0u;
        }
        break;

    case G30_SL_OPEN:
        update_lock_score(h, cfg, in);

        if (in->direction_evidence >= cfg->direction_fault_min_evidence &&
            in->direction_score <= cfg->direction_fault_score) {
            g30_sl_fault(h, G30_SL_FAULT_DIRECTION);
        } else if (in->observer_valid && in->observer_recent &&
                   in->direction_score >= cfg->direction_lock_score &&
                   h->lock_score >= cfg->lock_score_required &&
                   g30_sl_speed_coherent(in->open_step, in->observer_step)) {
            h->state = G30_SL_BLEND;
            h->state_ticks = 0u;
            h->blend_q15 = 0u;
        } else if (h->state_ticks >= cfg->open_timeout_ticks) {
            g30_sl_fault(h, G30_SL_FAULT_NO_LOCK);
        }
        break;

    case G30_SL_BLEND: {
        update_lock_score(h, cfg, in);

        if (!in->observer_valid || !in->observer_recent) {
            g30_sl_fault(h, G30_SL_FAULT_OBSERVER_LOST);
            break;
        }

        uint32_t den = cfg->blend_ticks ? cfg->blend_ticks : 1u;
        uint32_t q = (h->state_ticks * 32767u) / den;
        h->blend_q15 = (uint16_t)(q > 32767u ? 32767u : q);

        if (h->state_ticks >= cfg->blend_ticks) {
            uint16_t e = abs16(in->phase_error);
            if (g30_sl_speed_coherent(in->open_step, in->observer_step) &&
                in->direction_score >= (cfg->direction_lock_score - 1) &&
                h->lock_score >= (cfg->lock_score_required >> 1) &&
                e < cfg->phase_accept) {
                h->state = G30_SL_CLOSED;
                h->state_ticks = 0u;
                h->blend_q15 = 32767u;
            } else {
                /*
                 * Keep the XBOT v0.3.9+ lesson: never jump blindly off the
                 * observer cliff. Re-enter OPEN and reacquire coherently.
                 */
                h->state = G30_SL_OPEN;
                h->state_ticks = 0u;
                h->lock_score = 0u;
                h->blend_q15 = 0u;
            }
        }
        break;
    }

    case G30_SL_CLOSED:
        if (!in->observer_valid || !in->observer_recent) {
            g30_sl_fault(h, G30_SL_FAULT_OBSERVER_LOST);
        }
        break;

    default:
        break;
    }
}
