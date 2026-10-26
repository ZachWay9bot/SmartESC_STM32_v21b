#!/usr/bin/env python3
"""Exercise the actual portable G30 rolling/observer C core at boundary cases.

Synthetic signals only: does not establish real ADC phase polarity, physical
motor angle, gate-driver behavior or permission to flash a sealed controller.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "common_files/src/g30_sensorless_core.c"
INCLUDE = ROOT / "common_files/src"

C_CASES = r"""
#include <stdint.h>
#include <stdio.h>
#include "g30_sensorless_core.h"

static const uint16_t abc[6][3] = {
    {3000,2000,1000}, {2000,3000,1000}, {1000,3000,2000},
    {1000,2000,3000}, {2000,1000,3000}, {3000,1000,2000}
};
static void sample(g30sl_core_t *s, unsigned sector, uint32_t ticks) {
    g30sl_core_sample_bemf(s, abc[sector][0],abc[sector][1],
                           abc[sector][2], ticks);
}
static void prepare(g30sl_core_t *s) {
    g30sl_core_config_t cfg = {
        .cpu_hz=72000000u, .observer_hz=1000u,
        .bemf_span_min=40u, .min_speed_unit=164u, .min_lock_edges=4u,
        .r_mohm=300u, .l_uh=250u, .lambda_uwb=13000u
    };
    g30sl_core_init(s, &cfg);
}
static void spin(g30sl_core_t *s, uint32_t *ticks, uint32_t delta,
                 unsigned first, int dir, unsigned count) {
    sample(s, first, *ticks);
    for(unsigned i=1;i<=count;i++) {
        *ticks += delta;
        unsigned sector = dir>0 ? (first+i)%6u :
                                    (first+6u-(i%6u))%6u;
        sample(s, sector, *ticks);
    }
}
static int wraparound(void) {
    g30sl_core_t s;
    prepare(&s);
    uint32_t now=0xFFF00000u;
    spin(&s,&now,700000u,0u,+1,4u);
    if(!g30sl_core_roll_ready(&s,now) ||
       s.forward_edges!=4u || s.direction!=1)return 1;
    if(g30sl_core_roll_ready(&s,now+72000000u/12u+1u))return 2;
    return 0;
}
static int threshold(void) {
    g30sl_core_t s;
    uint32_t now=1000000u;
    prepare(&s);
    spin(&s,&now,730000u,0u,+1,4u);
    if(s.speed_unit<164 || !g30sl_core_roll_ready(&s,now))return 1;
    prepare(&s);now=1000000u;
    spin(&s,&now,740000u,0u,+1,4u);
    if(s.speed_unit>=164 || g30sl_core_roll_ready(&s,now))return 2;
    return 0;
}
static int reversal(void) {
    g30sl_core_t s;
    uint32_t now=1000000u;
    prepare(&s);
    spin(&s,&now,700000u,0u,+1,4u);
    if(!g30sl_core_roll_ready(&s,now))return 1;
    now+=700000u;
    sample(&s,3u,now); /* Last 4 -> 3: first opposite edge. */
    if(s.direction!=-1 || s.forward_edges!=0u ||
       s.reverse_edges!=1u || s.rolling_locked)return 2;
    now+=100000u;sample(&s,3u,now); /* duplicate sector, same edge cadence */
    if(s.reverse_edges!=1u || s.rolling_locked)return 3;
    for(unsigned sector=2u;sector<6u;sector--) {
        now+=(sector==2u ? 600000u : 700000u);
        sample(&s,sector,now);
        if(sector==0u)break;
    }
    if(!g30sl_core_roll_ready(&s,now) ||
       s.direction!=-1 || s.reverse_edges!=4u)return 4;
    return 0;
}
static int dropout_restart(void) {
    g30sl_core_t s;
    uint32_t now=1000000u;
    prepare(&s);
    spin(&s,&now,700000u,0u,+1,4u);
    if(!g30sl_core_roll_ready(&s,now))return 1;
    now+=100000u;
    g30sl_core_sample_bemf(&s,2048u,2048u,2048u,now);
    if(s.rolling_locked || s.speed_unit || s.forward_edges ||
       s.last_sector!=G30SL_NO_SECTOR)return 2;
    now+=700000u;sample(&s,0u,now);
    now+=700000u;sample(&s,1u,now);
    if(s.rolling_locked || s.forward_edges!=1u)return 3;
    return 0;
}
static int invalid_flux_start(void) {
    g30sl_core_t s;
    prepare(&s);
    s.cfg.lambda_uwb=0u;
    uint32_t now=1000000u;
    spin(&s,&now,700000u,0u,+1,4u);
    if(!g30sl_core_roll_ready(&s,now))return 1;
    g30sl_core_seed_observer_from_roll(&s,0,0);
    if(s.observer_seeded || g30sl_core_run_valid(&s))return 2;
    g30sl_core_set_motor(&s,0u,0u,13000u);
    if(s.cfg.r_mohm!=300u || s.cfg.l_uh!=250u ||
       s.cfg.lambda_uwb!=13000u)return 3;
    g30sl_core_seed_observer_from_roll(&s,0,0);
    if(!s.observer_seeded || s.observer_valid ||
       g30sl_core_run_valid(&s))return 4;
    return 0;
}
int main(void) {
    int rc;
#define CHECK(test) do { rc=test(); if(rc) { \
    fprintf(stderr,"%s: %d\n",#test,rc);return rc;} } while(0)
    CHECK(wraparound);
    CHECK(threshold);
    CHECK(reversal);
    CHECK(dropout_restart);
    CHECK(invalid_flux_start);
    puts("G30 synthetic boundary cases OK");
    return 0;
}
"""

class G30CoreBoundaryCases(unittest.TestCase):
    def test_real_g30_core_cycle_wrap_speed_reversal_dropout_and_no_flux(self):
        cc = shutil.which("cc") or shutil.which("gcc")
        if not cc:
            self.skipTest("Host C compiler missing")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "boundaries.c"
            executable = root / "boundaries"
            source.write_text(C_CASES)
            build = subprocess.run(
                [cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                 "-I", str(INCLUDE), str(CORE), str(source), "-o", str(executable)],
                capture_output=True, text=True
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0,
                             f"exit={run.returncode}: {run.stdout} {run.stderr}")

if __name__ == "__main__":
    unittest.main()
