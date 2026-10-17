#include <stdio.h>
#include <string.h>
#include "g30_sensorless_handover.h"

static int run_good(void) {
    g30_sl_config_t c;
    g30_sl_handover_t h;
    g30_sl_input_t in;

    g30_sl_config_xbot316_reference(&c);
    c.align_ticks = 2u;
    c.blend_ticks = 4u;
    c.open_timeout_ticks = 40u;

    g30_sl_init(&h);
    g30_sl_start(&h);
    memset(&in, 0, sizeof(in));

    for (int i = 0; i < 2; i++) g30_sl_update(&h, &c, &in);
    if (h.state != G30_SL_OPEN) return 1;

    in.open_step = 328u;
    in.observer_step = 220u;
    in.direction_score = 6;
    in.direction_evidence = 30u;
    in.observer_valid = true;
    in.observer_recent = true;
    in.phase_error = 4000;
    in.anchor_event = true;

    for (int i = 0; i < 5; i++) g30_sl_update(&h, &c, &in);
    if (h.state != G30_SL_BLEND) return 2;

    for (int i = 0; i < 4; i++) g30_sl_update(&h, &c, &in);
    if (h.state != G30_SL_CLOSED) return 3;

    return 0;
}

static int run_reverse(void) {
    g30_sl_config_t c;
    g30_sl_handover_t h;
    g30_sl_input_t in = {0};

    g30_sl_config_xbot316_reference(&c);
    c.align_ticks = 1u;
    c.open_timeout_ticks = 50u;

    g30_sl_init(&h);
    g30_sl_start(&h);
    g30_sl_update(&h, &c, &in);

    in.open_step = 328u;
    in.observer_step = 220u;
    in.direction_score = -6;
    in.direction_evidence = 20u;
    in.observer_valid = true;
    in.observer_recent = true;
    in.anchor_event = true;
    in.reverse_event = true;

    g30_sl_update(&h, &c, &in);
    return (h.state == G30_SL_FAULT &&
            h.fault == G30_SL_FAULT_DIRECTION) ? 0 : 4;
}

static int run_fallback(void) {
    g30_sl_config_t c;
    g30_sl_handover_t h;
    g30_sl_input_t in = {0};

    g30_sl_config_xbot316_reference(&c);
    c.align_ticks = 1u;
    c.blend_ticks = 2u;
    c.open_timeout_ticks = 50u;

    g30_sl_init(&h);
    g30_sl_start(&h);
    g30_sl_update(&h, &c, &in);

    in.open_step = 328u;
    in.observer_step = 220u;
    in.direction_score = 6;
    in.direction_evidence = 30u;
    in.observer_valid = true;
    in.observer_recent = true;
    in.phase_error = 4000;
    in.anchor_event = true;

    for (int i = 0; i < 5; i++) g30_sl_update(&h, &c, &in);
    if (h.state != G30_SL_BLEND) return 5;

    /* Force incoherent observer speed / phase before blend completion. */
    in.observer_step = 80u;
    in.phase_error = 20000;

    for (int i = 0; i < 2; i++) g30_sl_update(&h, &c, &in);
    return h.state == G30_SL_OPEN ? 0 : 6;
}

int main(void) {
    int good = run_good();
    int reverse = run_reverse();
    int fallback = run_fallback();

    printf("good=%d reverse=%d fallback=%d\n", good, reverse, fallback);
    return good ? good : (reverse ? reverse : fallback);
}
