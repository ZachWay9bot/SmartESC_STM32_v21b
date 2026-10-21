#!/usr/bin/env python3
"""Exercise the real sensorless flux observer with synthetic three-phase motion.

This does NOT certify phase polarity, ADC scaling, shunt calibration or motor
commutation on the hardware. No new lockout or motor policy is introduced.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "common_files/src/g30_sensorless_core.c"
INC = ROOT / "common_files/src"
SENSOR = (INC / "g30_sensorless.c").read_text()
CURRENT = (INC / "mc_tasks.c").read_text()

C_TEST = r"""
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include "g30_sensorless_core.h"

#define PI_F 3.14159265358979323846f

static const uint16_t abc[6][3] = {
    {3000,2000,1000}, {2000,3000,1000}, {1000,3000,2000},
    {1000,2000,3000}, {2000,1000,3000}, {3000,1000,2000}
};
static void push_phase(g30sl_core_t *s, unsigned sec, uint32_t cycles) {
    g30sl_core_sample_bemf(s,abc[sec][0],abc[sec][1],abc[sec][2],cycles);
}
static int steady_motion(int dir) {
    const g30sl_core_config_t cfg={
        .cpu_hz=72000000u,.observer_hz=1000u,
        .bemf_span_min=40u,.min_speed_unit=160u,.min_lock_edges=4u,
        .r_mohm=300u,.l_uh=250u,.lambda_uwb=13000u
    };
    g30sl_core_t s;
    g30sl_core_init(&s,&cfg);
    uint32_t t=1000000u;
    push_phase(&s,0u,t);
    for(unsigned i=1;i<=4u;i++) {
        t+=700000u;
        push_phase(&s,dir>0 ? i : 6u-i,t);
    }
    if(!g30sl_core_roll_ready(&s,t) || s.direction!=dir)return 1;
    g30sl_core_seed_observer_from_roll(&s,0,0);
    if(!s.observer_seeded || s.observer_valid || g30sl_core_run_valid(&s))return 2;

    int32_t pa0=s.psi_alpha_uwb;
    int32_t pb0=s.psi_beta_uwb;
    float phi0=atan2f((float)pb0,(float)pa0);
    float lambda=sqrtf((float)pa0*pa0+(float)pb0*pb0);
    int32_t pa=pa0,pb=pb0;
    for(unsigned i=1;i<=70u;i++) {
        /* Flux rotates opposite to the expected electrical-angle sign.
         * Drive dPsi/dt (millivolts) directly into the actual C observer.
         * For observer_hz=1000, one mV equals one micro-Weber/tick. */
        float theta=phi0-(float)dir*(2.0f*PI_F*17.14f)*((float)i/1000.0f);
        int32_t na=(int32_t)lroundf(lambda*cosf(theta));
        int32_t nb=(int32_t)lroundf(lambda*sinf(theta));
        g30sl_core_observer_step(&s,0,0,na-pa,nb-pb);
        pa=na;pb=nb;
    }
    if(!s.observer_valid || !g30sl_core_run_valid(&s))return 3;
    if(dir>0 && (s.observer_speed_unit<90 || s.observer_speed_unit>320))return 4;
    if(dir<0 && (s.observer_speed_unit>-90 || s.observer_speed_unit<-320))return 5;

    /* Impossible continuing sensor estimates must eventually mark the core
     * invalid. This does not test what the motor task does with that status. */
    for(unsigned i=0;i<35u;i++) {
        g30sl_core_observer_step(&s,0,0,45000,0);
    }
    if(g30sl_core_run_valid(&s) || s.observer_bad<20u)return 6;
    return 0;
}
int main(void){
    int f=steady_motion(+1);
    if(f){fprintf(stderr,"forward failed: %d\n",f);return 10+f;}
    f=steady_motion(-1);
    if(f){fprintf(stderr,"reverse failed: %d\n",f);return 20+f;}
    puts("G30 observer synthetic dynamic tests OK");
    return 0;
}
"""

class G30ObserverDynamics(unittest.TestCase):
    def test_real_flux_observer_forward_reverse_and_bad_estimates(self):
        cc = shutil.which("cc") or shutil.which("gcc")
        if not cc:
            self.skipTest("C compiler missing")
        with tempfile.TemporaryDirectory() as name:
            p=Path(name)
            (p/"test.c").write_text(C_TEST)
            run=p/"observe"
            subprocess.run([cc,"-std=c11","-Wall","-Wextra","-Werror",
                            "-I",str(INC),str(CORE),str(p/"test.c"),
                            "-lm","-o",str(run)],check=True,capture_output=True,text=True)
            result=subprocess.run([str(run)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,
                             f"observer exit={result.returncode}; {result.stdout}; {result.stderr}")

    def test_handoff_blends_observer_phase_after_seed(self):
        angle=SENSOR.split("int16_t G30SL_CalcElAngle(",1)[1].split(
            "bool G30SL_CalcAvrgMecSpeedUnit(",1)[0]
        self.assertIn("old + h->_Super.hElSpeedDpp",angle)
        self.assertIn("h->active && h->core.observer_seeded && h->core.observer_valid",angle)
        self.assertIn("next + (err >> 3)",angle)
        start=SENSOR.split("bool G30SL_PreparePwmStart(",1)[1].split(
            "void G30SL_OnPwmStop(",1)[0]
        self.assertLess(start.index("g30sl_core_seed_observer_from_roll"),
                        start.index("h->active = 1u"))
        self.assertIn("h->active_grace = 80u",start)

    def test_current_signal_is_clarke_park_fed_to_observer(self):
        self.assertIn("Ialphabeta = MCM_Clarke(Iab);",CURRENT)
        self.assertIn("Iqd = MCM_Park(Ialphabeta, hElAngle);",CURRENT)
        self.assertIn("Valphabeta = MCM_Rev_Park(Vqd, hElAngle);",CURRENT)
        self.assertIn("G30SL_ObserverStep(&G30Sensorless_M1, Ialphabeta, Valphabeta, vbus_mv);",CURRENT)


if __name__ == "__main__":
    unittest.main()
