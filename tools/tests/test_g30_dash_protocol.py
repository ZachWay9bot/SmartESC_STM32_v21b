#!/usr/bin/env python3
"""Host regression for original Ninebot 5A A5 parser/checksum and G30 CMD64 reply.
No controller required. Run:
python3 -m unittest discover -s tools/tests -p 'test_g30_dash_protocol.py'
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "common_files/src/ninebot.c"
HEADERS = ROOT / "common_files/src"
APP = (ROOT / "common_files/src/app_uartcomm.c").read_text()

C_TEST = r"""
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "ninebot.h"

static uint16_t checksum(const uint8_t *p, unsigned n) {
    unsigned sum = 0;
    for (unsigned i=2; i<n-2; ++i) sum += p[i];
    return (uint16_t)~sum;
}
static int feed(const uint8_t *p, unsigned n, NinebotPack *out) {
    int valid = 0;
    for (unsigned i=0; i<n; ++i) if (ninebot_parse(p[i], out) == 0) valid++;
    return valid;
}
int main(void) {
    /* Historical G30 CMD65 lever payload: [04,29,23,02,00]. */
    uint8_t lever[] = {0x5A,0xA5,0x05,0x21,0x20,0x65,0x00,
                       0x04,0x29,0x23,0x02,0x00,0x00,0x00};
    addCRC(lever, sizeof lever);
    NinebotPack f = {0};
    if (feed(lever, sizeof lever, &f) != 1 ||
        f.src != 0x21 || f.dst != 0x20 || f.cmd != 0x65 ||
        f.len != 5 || f.payload[1] != 0x29 || f.payload[2] != 0x23) return 1;
    lever[8] ^= 0x01; /* corrupted throttle with stale checksum */
    if (feed(lever, sizeof lever, &f) != 0) return 2;

    /* CMD64 request -> existing CMD64 response [mode,bat,light,beep,speed,fault]. */
    uint8_t request[] = {0x5A,0xA5,0x03,0x21,0x20,0x64,0x00,0x00,0x00};
    addCRC(request, sizeof request);
    if (feed(request, sizeof request, &f) != 1 ||
        f.cmd != 0x64 || f.src != 0x21 || f.dst != 0x20) return 3;
    m365Answer reply = {.start1=0x5A,.start2=0xA5,.len=6,
                        .src=0x20,.dst=0x21,.cmd=0x64,.arg=0,
                        .mode=4,.battery=75,.light=0,.beep=0,
                        .speed=12,.faultcode=0};
    if (sizeof(reply) != 15u) return 4;
    addCRC((uint8_t *)&reply, sizeof reply);
    const uint8_t *rp=(const uint8_t *)&reply;
    if (checksum(rp, sizeof reply) !=
        ((uint16_t)rp[13] | ((uint16_t)rp[14]<<8))) return 5;
    if (feed(rp, sizeof reply, &f) != 1 ||
        f.cmd != 0x64 || f.len != 6 ||
        f.payload[1] != 75 || f.payload[4] != 12) return 6;
    puts("G30 native dash protocol host tests OK");
    return 0;
}
"""

class G30DashboardTests(unittest.TestCase):
    def test_parser_and_cmd64_reply_on_host(self):
        compiler = shutil.which("cc") or shutil.which("gcc")
        if not compiler:
            self.skipTest("Host C compiler missing")
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "m365_register_map.h").write_text("/* test-only stub */\n")
            (p / "test.c").write_text(C_TEST)
            exe = p / "dash_test"
            subprocess.run([compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
                            "-I", str(p), "-I", str(HEADERS),
                            str(SOURCE), str(p / "test.c"), "-o", str(exe)],
                           check=True, capture_output=True, text=True)
            subprocess.run([str(exe)], check=True, capture_output=True, text=True)

    def test_firmware_responds_only_to_cmd64_with_cmd64(self):
        self.assertIn("if(frame.cmd == 0x64)", APP)
        self.assertIn(".cmd=0x64", APP)
        self.assertIn("frame.payload[1]", APP)
        self.assertIn("frame.payload[2]", APP)
        self.assertIn("addCRC((uint8_t*)&m365_to_display", APP)
        self.assertIn("my_uart_send_data((uint8_t*)&m365_to_display", APP)
        self.assertIn("isfinite(speed_kmh)", APP)
        self.assertIn("isfinite(battery_pct)", APP)

if __name__ == "__main__":
    unittest.main()
