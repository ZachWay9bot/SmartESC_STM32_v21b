#pragma once
#include <stdint.h>
#include <stdbool.h>
#include "speed_pos_fdbk.h"
#include "mc_type.h"
#include "g30_sensorless_core.h"

typedef struct {
    SpeednPosFdbk_Handle_t _Super;
    g30sl_core_t core;
    uint16_t observer_div;
    uint16_t observer_div_cnt;
    uint16_t active_grace;
    uint8_t active;
    uint8_t passive_adc_ok;
    int32_t tachometer;
    uint32_t tachometer_abs;
    int32_t tacho_phase_accum;
} G30Sensorless_Handle_t;

extern G30Sensorless_Handle_t G30Sensorless_M1;

void G30SL_Init(G30Sensorless_Handle_t *h, const SpeednPosFdbk_Handle_t *template_spd);
void G30SL_Clear(G30Sensorless_Handle_t *h);
void G30SL_Configure(G30Sensorless_Handle_t *h, float r_ohm, float l_h, float flux_wb,
                     float wheel_diameter_m, float gear_ratio, uint8_t motor_poles,
                     uint32_t foc_hz);
void G30SL_PassivePoll(G30Sensorless_Handle_t *h);
bool G30SL_PreparePwmStart(G30Sensorless_Handle_t *h);
void G30SL_OnPwmStop(G30Sensorless_Handle_t *h);
int16_t G30SL_CalcElAngle(G30Sensorless_Handle_t *h);
bool G30SL_CalcAvrgMecSpeedUnit(G30Sensorless_Handle_t *h, int16_t *speed_unit);
void G30SL_ObserverStep(G30Sensorless_Handle_t *h, alphabeta_t i_ab, alphabeta_t v_ab, uint32_t vbus_mv);
bool G30SL_IsActive(const G30Sensorless_Handle_t *h);
bool G30SL_IsLocked(const G30Sensorless_Handle_t *h);
int32_t G30SL_GetTacho(G30Sensorless_Handle_t *h, bool reset);
int32_t G30SL_GetTachoAbs(G30Sensorless_Handle_t *h, bool reset);
