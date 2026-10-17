#ifndef G30_SENSORLESS_HANDOVER_H
#define G30_SENSORLESS_HANDOVER_H

#include <stdint.h>
#include <stdbool.h>

/*
 * Sensorless startup / observer handover policy only.
 *
 * This module never drives PWM, gates, ADCs or the motor. It is deliberately
 * hardware-agnostic so the handover rules can be host-tested before they are
 * connected to the G30 MCSDK current loop.
 *
 * Origin: distilled from the real-hardware validated XBOT sensorless v0.3.16
 * startup path. XBOT-specific BEMF ADC pins, current polarity, PWM mapping and
 * raw sector direction are intentionally NOT copied into the G30 target.
 */

typedef enum {
    G30_SL_OFF = 0,
    G30_SL_ALIGN,
    G30_SL_OPEN,
    G30_SL_BLEND,
    G30_SL_CLOSED,
    G30_SL_FAULT
} g30_sl_state_t;

typedef enum {
    G30_SL_FAULT_NONE = 0,
    G30_SL_FAULT_DIRECTION,
    G30_SL_FAULT_NO_LOCK,
    G30_SL_FAULT_OBSERVER_LOST
} g30_sl_fault_t;

typedef struct {
    uint32_t align_ticks;
    uint32_t open_timeout_ticks;
    uint32_t blend_ticks;
    uint16_t lock_score_required;
    uint16_t lock_score_max;
    uint16_t phase_good;
    uint16_t phase_accept;
    int8_t direction_lock_score;
    int8_t direction_fault_score;
    uint16_t direction_fault_min_evidence;
} g30_sl_config_t;

typedef struct {
    uint16_t open_step;
    uint16_t observer_step;
    int16_t phase_error;
    int8_t direction_score;
    uint16_t direction_evidence;
    bool observer_valid;
    bool observer_recent;
    bool anchor_event;
    bool reverse_event;
} g30_sl_input_t;

typedef struct {
    g30_sl_state_t state;
    g30_sl_fault_t fault;
    uint32_t state_ticks;
    uint16_t lock_score;
    uint16_t blend_q15;
} g30_sl_handover_t;

void g30_sl_config_xbot316_reference(g30_sl_config_t *cfg);
void g30_sl_init(g30_sl_handover_t *h);
void g30_sl_start(g30_sl_handover_t *h);
void g30_sl_stop(g30_sl_handover_t *h);
void g30_sl_update(g30_sl_handover_t *h, const g30_sl_config_t *cfg,
                   const g30_sl_input_t *in);
bool g30_sl_speed_coherent(uint16_t open_step, uint16_t observer_step);

#endif
