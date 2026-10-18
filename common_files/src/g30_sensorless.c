#include "g30_sensorless.h"
#include "main.h"
#include "product.h"
#include "mc_config.h"
#include <string.h>

G30Sensorless_Handle_t G30Sensorless_M1;

static int16_t clamp_i16(int32_t x) {
    if (x > 32767) return 32767;
    if (x < -32767) return -32767;
    return (int16_t)x;
}

static int32_t i_counts_to_ma(int16_t x) {
    return (int32_t)((float)x * 1000.0f / (float)CURRENT_FACTOR_A);
}

static uint16_t adc1_read_regular_12b(uint8_t ch) {
    ADC1->SQR1 &= ~(0xFu << 20);
    ADC1->SQR3 = (ADC1->SQR3 & ~0x1Fu) | ((uint32_t)ch & 0x1Fu);
    ADC1->SR &= ~ADC_SR_EOC;
    ADC1->CR2 |= ADC_CR2_ADON;
    ADC1->CR2 |= ADC_CR2_SWSTART;
    uint32_t start = DWT->CYCCNT;
    uint32_t timeout = HAL_RCC_GetHCLKFreq() / 2000u;
    while ((ADC1->SR & ADC_SR_EOC) == 0u) {
        if ((uint32_t)(DWT->CYCCNT - start) > timeout) return 0xFFFFu;
    }
    return (uint16_t)(ADC1->DR >> 4);
}

static bool sample_floating_phases(uint16_t *a, uint16_t *b, uint16_t *c) {
    uint32_t tim_cr1 = TIM1->CR1;
    uint32_t sqr1 = ADC1->SQR1, sqr2 = ADC1->SQR2, sqr3 = ADC1->SQR3;
    uint32_t smpr2 = ADC1->SMPR2;
    TIM1->CR1 &= ~TIM_CR1_CEN;
    for (volatile uint32_t i = 0; i < 64u; i++) { __NOP(); }

    ADC1->SMPR2 = (ADC1->SMPR2 & ~((7u << 18) | (7u << 21) | (7u << 27))) |
                  (4u << 18) | (4u << 21) | (4u << 27);
    uint32_t sa = 0u, sb = 0u, sc = 0u;
    for (unsigned n = 0; n < 3u; n++) {
        uint16_t va = adc1_read_regular_12b(6u);
        uint16_t vb = adc1_read_regular_12b(7u);
        uint16_t vc = adc1_read_regular_12b(9u);
        if (va == 0xFFFFu || vb == 0xFFFFu || vc == 0xFFFFu) {
            ADC1->SQR1 = sqr1; ADC1->SQR2 = sqr2; ADC1->SQR3 = sqr3;
            ADC1->SMPR2 = smpr2; TIM1->CR1 = tim_cr1;
            return false;
        }
        sa += va; sb += vb; sc += vc;
    }
    ADC1->SQR1 = sqr1; ADC1->SQR2 = sqr2; ADC1->SQR3 = sqr3; ADC1->SMPR2 = smpr2;
    TIM1->CNT = 0u;
    TIM1->EGR = TIM_EGR_UG;
    TIM1->SR = 0u;
    TIM1->CR1 = tim_cr1;
    *a = (uint16_t)(sa / 3u); *b = (uint16_t)(sb / 3u); *c = (uint16_t)(sc / 3u);
    return true;
}

void G30SL_Init(G30Sensorless_Handle_t *h, const SpeednPosFdbk_Handle_t *template_spd) {
    memset(h, 0, sizeof(*h));
    h->_Super = *template_spd;
    g30sl_core_config_t cfg = {
        .cpu_hz = HAL_RCC_GetHCLKFreq(), .observer_hz = 1000u,
        .bemf_span_min = 40u, .min_speed_unit = 160u, .min_lock_edges = 4u,
        .r_mohm = 0u, .l_uh = 0u, .lambda_uwb = 0u
    };
    g30sl_core_init(&h->core, &cfg);
    h->observer_div = 16u;
}

void G30SL_Clear(G30Sensorless_Handle_t *h) {
    h->_Super.hElAngle = 0;
    h->_Super.hAvrMecSpeedUnit = 0;
    h->_Super.hElSpeedDpp = 0;
    h->_Super.InstantaneousElSpeedDpp = 0;
    h->_Super.bSpeedErrorNumber = 0u;
    h->active = 0u; h->active_grace = 0u; h->observer_div_cnt = 0u;
    /* Preserve trip/odometer counters across stop/start cycles. */\n    h->tacho_phase_accum = 0;
    g30sl_core_reset_roll(&h->core);
    h->core.observer_seeded = h->core.observer_valid = 0u;
    h->core.observer_good = h->core.observer_bad = 0u;
}

void G30SL_Configure(G30Sensorless_Handle_t *h, float r_ohm, float l_h, float flux_wb,
                     float wheel_diameter_m, float gear_ratio, uint8_t motor_poles,
                     uint32_t foc_hz) {
    uint32_t r = (r_ohm >= 0.005f && r_ohm <= 5.0f) ? (uint32_t)(r_ohm * 1000.0f + 0.5f) : 0u;
    uint32_t l = (l_h >= 0.000005f && l_h <= 0.02f) ? (uint32_t)(l_h * 1000000.0f + 0.5f) : 0u;
    uint32_t f = (flux_wb >= 0.0005f && flux_wb <= 0.2f) ? (uint32_t)(flux_wb * 1000000.0f + 0.5f) : 0u;
    g30sl_core_set_motor(&h->core, r, l, f);
    if (!r) h->core.cfg.r_mohm = 0u;
    if (!l) h->core.cfg.l_uh = 0u;
    if (!f) h->core.cfg.lambda_uwb = 0u;

    float pp = motor_poles >= 2u ? (float)motor_poles * 0.5f : 15.0f;
    float dia = wheel_diameter_m > 0.1f && wheel_diameter_m < 1.0f ? wheel_diameter_m : 0.243f;
    float gear = gear_ratio > 0.05f && gear_ratio < 20.0f ? gear_ratio : 1.0f;
    float ehz = (3.0f / 3.6f) / (3.14159265f * dia) * gear * pp;
    uint32_t min_su = (uint32_t)(ehz * 10.0f + 0.5f);
    if (min_su < 60u) min_su = 60u;
    if (min_su > 1000u) min_su = 1000u;
    h->core.cfg.min_speed_unit = (uint16_t)min_su;

    uint32_t hf = foc_hz ? foc_hz : 16000u;
    h->_Super.hMeasurementFrequency = (uint16_t)hf;
    h->observer_div = (uint16_t)(hf / h->core.cfg.observer_hz);
    if (!h->observer_div) h->observer_div = 1u;
}

void G30SL_PassivePoll(G30Sensorless_Handle_t *h) {
    if (h->active || !PWM_Handle_M1._Super.PWM_off) return;
    uint16_t a, b, c;
    if (!sample_floating_phases(&a, &b, &c)) { h->passive_adc_ok = 0u; return; }
    h->passive_adc_ok = 1u;
    g30sl_core_sample_bemf(&h->core, a, b, c, DWT->CYCCNT);
    if (g30sl_core_roll_ready(&h->core, DWT->CYCCNT)) {
        h->_Super.hElAngle = (int16_t)h->core.control_phase;
        h->_Super.hAvrMecSpeedUnit = h->core.speed_unit;
        int32_t dpp = ((int32_t)h->core.speed_unit * (int32_t)h->_Super.DPPConvFactor) /
                      ((int32_t)SPEED_UNIT * (int32_t)h->_Super.hMeasurementFrequency);
        h->_Super.hElSpeedDpp = h->_Super.InstantaneousElSpeedDpp = clamp_i16(dpp);
    }
}

bool G30SL_PreparePwmStart(G30Sensorless_Handle_t *h) {
    if (h->_Super.open_loop) return true;
    if (!h->core.cfg.r_mohm || !h->core.cfg.l_uh || !h->core.cfg.lambda_uwb) return false;
    if (!g30sl_core_roll_ready(&h->core, DWT->CYCCNT)) return false;
    g30sl_core_seed_observer_from_roll(&h->core, 0, 0);
    if (!h->core.observer_seeded) return false;
    h->_Super.hElAngle = (int16_t)h->core.control_phase;
    h->_Super.hAvrMecSpeedUnit = h->core.speed_unit;
    int32_t dpp = ((int32_t)h->core.speed_unit * (int32_t)h->_Super.DPPConvFactor) /
                  ((int32_t)SPEED_UNIT * (int32_t)h->_Super.hMeasurementFrequency);
    h->_Super.hElSpeedDpp = h->_Super.InstantaneousElSpeedDpp = clamp_i16(dpp);
    h->active = 1u;
    h->active_grace = 80u;
    return true;
}

void G30SL_OnPwmStop(G30Sensorless_Handle_t *h) {
    h->active = 0u; h->active_grace = 0u;
    h->core.observer_seeded = h->core.observer_valid = 0u;
    h->core.observer_good = h->core.observer_bad = 0u;
    g30sl_core_reset_roll(&h->core);
}

int16_t G30SL_CalcElAngle(G30Sensorless_Handle_t *h) {
    if (h->_Super.open_loop) return h->_Super.hElAngle;
    int16_t old = h->_Super.hElAngle;
    int16_t next = (int16_t)(old + h->_Super.hElSpeedDpp);
    if (h->active && h->core.observer_seeded && h->core.observer_valid) {
        int16_t err = (int16_t)((uint16_t)h->core.observer_phase - (uint16_t)next);
        next = (int16_t)(next + (err >> 3));
    }
    h->_Super.hElAngle = next;
    int16_t ds = (int16_t)(next - old);
    h->tacho_phase_accum += ds;
    while (h->tacho_phase_accum >= 10923) {
        h->tacho_phase_accum -= 10923; h->tachometer++; h->tachometer_abs++;
    }
    while (h->tacho_phase_accum <= -10923) {
        h->tacho_phase_accum += 10923; h->tachometer--; h->tachometer_abs++;
    }
    return next;
}

bool G30SL_CalcAvrgMecSpeedUnit(G30Sensorless_Handle_t *h, int16_t *speed_unit) {
    if (!h->active) {
        *speed_unit = g30sl_core_roll_ready(&h->core, DWT->CYCCNT) ? h->core.speed_unit : 0;
        h->_Super.hAvrMecSpeedUnit = *speed_unit;
        return true;
    }
    if (h->core.observer_seeded && h->core.observer_valid) {
        h->_Super.hAvrMecSpeedUnit = h->core.observer_speed_unit;
        int32_t dpp = ((int32_t)h->core.observer_speed_unit * (int32_t)h->_Super.DPPConvFactor) /
                      ((int32_t)SPEED_UNIT * (int32_t)h->_Super.hMeasurementFrequency);
        h->_Super.hElSpeedDpp = h->_Super.InstantaneousElSpeedDpp = clamp_i16(dpp);
    }
    *speed_unit = h->_Super.hAvrMecSpeedUnit;
    if (h->active_grace) { h->active_grace--; return true; }
    return h->core.observer_seeded && h->core.observer_bad < 20u;
}

void G30SL_ObserverStep(G30Sensorless_Handle_t *h, alphabeta_t i_ab, alphabeta_t v_ab, uint32_t vbus_mv) {
    if (!h->active || h->_Super.open_loop || PWM_Handle_M1._Super.PWM_off) return;
    if (++h->observer_div_cnt < h->observer_div) return;
    h->observer_div_cnt = 0u;
    int32_t ia = i_counts_to_ma(i_ab.alpha);
    int32_t ib = i_counts_to_ma(i_ab.beta);
    int32_t va = (int32_t)(((int64_t)v_ab.alpha * (int32_t)vbus_mv) / 32768);
    int32_t vb = (int32_t)(((int64_t)v_ab.beta * (int32_t)vbus_mv) / 32768);
    g30sl_core_observer_step(&h->core, ia, ib, va, vb);
}

bool G30SL_IsActive(const G30Sensorless_Handle_t *h) { return h->active != 0u; }
bool G30SL_IsLocked(const G30Sensorless_Handle_t *h) {
    return g30sl_core_roll_ready(&h->core, DWT->CYCCNT);
}
int32_t G30SL_GetTacho(G30Sensorless_Handle_t *h, bool reset) {
    int32_t v = h->tachometer; if (reset) h->tachometer = 0; return v;
}
int32_t G30SL_GetTachoAbs(G30Sensorless_Handle_t *h, bool reset) {
    int32_t v = (int32_t)h->tachometer_abs; if (reset) h->tachometer_abs = 0u; return v;
}
