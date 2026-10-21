#!/usr/bin/env python3
"""Bench-independent regression for G30 sensorless rolling lock.

Run: python3 -m unittest discover -s tools/tests -p 'test_g30_rolling.py' -v

The test compiles the real portable observer/core code and supplies synthetic
three-phase BEMF sectors. It does not prove actual ADC wiring, motor phase
sequence or measured FOC torque on hardware.
"""
from pathlib import Path
import math
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "common_files/src/g30_sensorless_core.c"
INC = ROOT / "common_files/src"
BOARD_MAIN = (ROOT / "g30p/Src/main.c").read_text()
SENSOR = (ROOT / "common_files/src/g30_sensorless.c").read_text()

C_TEST = r"""
#include <stdint.h>
#include <stdio.h>
#include "g30_sensorless_core.h"

static const uint16_t abc[6][3] = {
    {3000,2000,1000}, {2000,3000,1000}, {1000,3000,2000},
    {1000,2000,3000}, {2000,1000,3000}, {3000,1000,2000}
};

static void sample(g30sl_core_t *s, unsigned sector, uint32_t t) {
    g30sl_core_sample_bemf(s, abc[sector][0], abc[sector][1],
                           abc[sector][2], t);
}
static void init(g30sl_core_t *s) {
    /* 30 magnetic poles (15 pairs), 0.243 m wheel, ~3 km/h at 164 x 0.1Hz. */
    const g30sl_core_config_t cfg = {
        .cpu_hz = 72000000, .observer_hz = 1000, .bemf_span_min = 40,
        .min_speed_unit = 164, .min_lock_edges = 4,
        .r_mohm = 300, .l_uh = 250, .lambda_uwb = 13000
    };
    g30sl_core_init(s, &cfg);
}
static void acquire(g30sl_core_t *s, uint32_t *now, uint32_t dt) {
    sample(s, 0, *now);
    for (unsigned i = 1; i <= 4; i++) {
        *now += dt;
        sample(s, i, *now);
    }
}
int main(void) {
    g30sl_core_t s;
    uint32_t now;

    /* Above 3 km/h: 171 speed units, four consecutive sector edges. */
    init(&s); now = 1000000u;
    acquire(&s, &now, 700000u);
    if (!g30sl_core_roll_ready(&s, now) || s.direction != 1 ||
        s.forward_edges != 4u || s.speed_unit < 164) return 1;
    g30sl_core_seed_observer_from_roll(&s, 0, 0);
    if (!s.observer_seeded) return 2;

    /* Falling below threshold must release a previous rolling lock. */
    for (unsigned i = 0; i < 10; ++i) {
        now += 950000u;
        sample(&s, (5 + i) % 6, now);
    }
    if (s.speed_unit >= 164 || s.rolling_locked ||
        g30sl_core_roll_ready(&s, now)) return 3;

    /* Sub-threshold speed must never acquire the rolling lock. */
    init(&s); now = 1000000u;
    acquire(&s, &now, 950000u);
    if (s.rolling_locked || g30sl_core_roll_ready(&s, now)) return 4;

    /* BEMF dropout must reset the old sector streak and timing history. */
    init(&s); now = 1000000u;
    sample(&s, 0, now);
    for (unsigned i = 1; i <= 3; ++i) {
        now += 700000u; sample(&s, i, now);
    }
    if (s.forward_edges != 3u || s.rolling_locked) return 5;
    now += 700000u;
    g30sl_core_sample_bemf(&s, 2048, 2048, 2048, now);
    if (s.forward_edges || s.reverse_edges || s.avg_edge_cycles ||
        s.rolling_locked || s.speed_unit) return 6;
    now += 700000u; sample(&s, 0, now);
    now += 700000u; sample(&s, 1, now);
    if (s.rolling_locked || s.forward_edges != 1u) return 7;

    /* Stale samples invalidate readiness even with previously latched lock. */
    init(&s); now = 1000000u;
    acquire(&s, &now, 700000u);
    if (!g30sl_core_roll_ready(&s, now)) return 8;
    if (g30sl_core_roll_ready(&s, now + 72000000u / 12u + 1u)) return 9;

    /* Invalid multi-sector jump cannot reuse previous successful edges. */
    init(&s); now = 1000000u;
    acquire(&s, &now, 700000u);
    now += 700000u; sample(&s, 1, now); /* last sector 4 -> 1: invalid */
    if (s.rolling_locked || s.forward_edges || s.reverse_edges ||
        s.speed_unit || s.avg_edge_cycles) return 10;

    /* Reverse rolling direction remains detected, not silently remapped. */
    init(&s); now = 1000000u;
    sample(&s, 0, now);
    for (unsigned i = 1; i <= 4; ++i) {
        now += 700000u; sample(&s, 6u-i, now);
    }
    if (!g30sl_core_roll_ready(&s, now) || s.direction != -1 ||
        s.speed_unit >= 0 || s.reverse_edges != 4u) return 11;

    puts("G30 rolling BEMF host regression OK");
    return 0;
}
"""

class G30Rolling(unittest.TestCase):
    def test_real_core_with_synthetic_bemf(self):
        compiler = shutil.which("cc") or shutil.which("gcc")
        if not compiler:
            self.skipTest("Host C compiler unavailable")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            ctest = path / "test.c"
            exe = path / "test_rolling"
            ctest.write_text(C_TEST)
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(INC), str(CORE), str(ctest), "-o", str(exe)],
                           check=True, capture_output=True, text=True)
            result = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0,
                             f"core test exit={result.returncode}: {result.stdout} {result.stderr}")

    def test_adc_left_alignment_and_phase_channels(self):
        self.assertIn("hadc1.Init.DataAlign = ADC_DATAALIGN_LEFT;", BOARD_MAIN)
        self.assertIn("ADC1->DR >> 4", SENSOR)
        for pin in ("adc1_read_regular_12b(6u)", "adc1_read_regular_12b(7u)",
                    "adc1_read_regular_12b(9u)"):
            self.assertIn(pin, SENSOR)

    def test_three_kmh_threshold_matches_poles_not_serial_prefix(self):
        for poles, expected_su in ((12, 65), (18, 98), (30, 164)):
            ehz = (3.0 / 3.6) / (math.pi * 0.243) * (poles / 2)
            self.assertEqual(int(ehz * 10 + 0.5), expected_su)
        self.assertIn("motor_poles * 0.5f", SENSOR)
        self.assertIn("h->core.cfg.min_speed_unit = (uint16_t)min_su;", SENSOR)


if __name__ == "__main__":
    unittest.main()
