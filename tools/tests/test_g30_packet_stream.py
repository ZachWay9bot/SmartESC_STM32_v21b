#!/usr/bin/env python3
"""Compile and execute the actual G30/VESC packet.c parser on host.

Thin host shims replace FreeRTOS allocation and CRC hardware dependencies;
the packet parser and framing source itself is NOT duplicated or modified.
This does not exercise actual UART DMA, interrupts, or a controller.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "common_files/src"

C_TEST = r"""
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Skip platform packet.h only: matching types suffice for the real parser. */
#define PACKET_H_
#define PACKET_RX_TIMEOUT 1000
#define PACKET_MAX_PL_LEN 512
#define PACKET_HEADER 4
typedef struct port_str { int unused; } port_str;
typedef struct __PACKET_STATE_t__ PACKET_STATE_t;
struct __PACKET_STATE_t__ {
    volatile unsigned short rx_timeout;
    void (*send_func)(unsigned char *, unsigned int, port_str *);
    void (*process_func)(unsigned char *, unsigned int, PACKET_STATE_t *);
    unsigned int rx_read_ptr, rx_write_ptr;
    int bytes_left;
    unsigned char *rx_buffer;
    port_str *port;
};
static int alloc_attempts, fail_at, live_allocations;
void *pvPortMalloc(size_t n) {
    alloc_attempts++;
    if (fail_at && alloc_attempts == fail_at) return NULL;
    void *p = malloc(n);
    if (p) live_allocations++;
    return p;
}
void vPortFree(void *p) {
    if (p) { free(p); live_allocations--; }
}

/* CRC16 implementation of the stock VESC polynomial (crc.c uses STM32
 * peripherals only for CRC32, so port its CRC16 math here). */
unsigned short crc16(unsigned char *buffer, unsigned int length) {
    uint16_t crc=0;
    while(length--) {
        uint16_t x=(uint16_t)((crc>>8)^*buffer++);
        x^=(uint16_t)(x>>4);
        crc=(uint16_t)((crc<<8)^(x<<12)^(x<<5)^x);
    }
    return crc;
}

/* This inclusion executes the repository's unmodified packet.c. */
#include "packet.c"

static unsigned callbacks, sends, received_len, wire_len;
static uint8_t received[PACKET_MAX_PL_LEN], wire[PACKET_MAX_PL_LEN+8];

static void on_receive(unsigned char *data, unsigned int n,
                       PACKET_STATE_t *unused) {
    (void)unused;
    callbacks++;
    received_len=n;
    if(n<=sizeof(received))memcpy(received,data,n);
}
static void on_send(unsigned char *data, unsigned int n, port_str *unused) {
    (void)unused;
    sends++;
    wire_len=n;
    if(n<=sizeof(wire))memcpy(wire,data,n);
}
static void make_frame(PACKET_STATE_t *s, unsigned n) {
    uint8_t payload[PACKET_MAX_PL_LEN+8]={0};
    for(unsigned i=0;i<n;i++)payload[PACKET_HEADER+i]=(uint8_t)(i*13u+7u);
    packet_send_packet(payload,n,s);
}
static void feed(PACKET_STATE_t *s, unsigned start, unsigned end) {
    for(unsigned i=start;i<end;i++)packet_process_byte(wire[i],s);
}
static int frame_round_trip(PACKET_STATE_t *s, unsigned n) {
    callbacks=sends=0;
    make_frame(s,n);
    if(sends!=1u || wire_len>sizeof(wire))return 1;
    feed(s,0,wire_len-1u);
    if(callbacks)return 2;
    feed(s,wire_len-1u,wire_len);
    if(callbacks!=1u || received_len!=n)return 3;
    for(unsigned i=0;i<n;i++){
        if(received[i]!=(uint8_t)(i*13u+7u))return 4;
    }
    return 0;
}
static int corrupted_crc(PACKET_STATE_t *s) {
    packet_reset(s);
    callbacks=sends=0;
    make_frame(s,32);
    wire[wire_len-2u] ^= 1u;
    feed(s,0,wire_len);
    if(callbacks)return 1;
    packet_reset(s);
    make_frame(s,32);
    feed(s,0,wire_len);
    if(callbacks!=1u)return 2;
    return 0;
}
static int noisy_stream(PACKET_STATE_t *s) {
    packet_reset(s);
    callbacks=sends=0;
    for(unsigned i=0;i<7000u;i++){
        uint8_t b=(uint8_t)((i%3u)==0 ? 0xFFu : 0u);
        packet_process_byte(b,s);
    }
    if(callbacks)return 1;
    make_frame(s,24);
    feed(s,0,wire_len);
    if(callbacks!=1u || received_len!=24u)return 2;
    return 0;
}
static int oversize_and_empty(PACKET_STATE_t *s) {
    packet_reset(s);
    callbacks=sends=0;
    make_frame(s,0);
    make_frame(s,513);
    if(sends)return 1;
    packet_process_byte(3u,s);
    packet_process_byte(2u,s);
    packet_process_byte(1u,s); /* 513 exceeds 512 payload cap */
    make_frame(s,1);
    feed(s,0,wire_len);
    if(callbacks!=1u || received_len!=1u)return 2;
    return 0;
}
int main(void) {
    port_str p={0};
    /* Both FreeRTOS allocation failure points must return NULL and leave
     * no leaked state or attempted NULL dereference. */
    packet_free(NULL);
    for (int fail = 1; fail <= 2; ++fail) {
        alloc_attempts = 0;
        fail_at = fail;
        PACKET_STATE_t *failed = packet_init(on_send,on_receive,&p);
        if (failed != NULL || live_allocations != 0) return 2 + fail;
    }
    alloc_attempts = 0;
    fail_at = 0;
    PACKET_STATE_t *s=packet_init(on_send,on_receive,&p);
    if(!s || !s->rx_buffer)return 1;
    for(unsigned i=0;i<4u;i++) {
        const unsigned lens[4]={1u,255u,256u,512u};
        packet_reset(s);
        int result=frame_round_trip(s,lens[i]);
        if(result){fprintf(stderr,"round-trip %u: %d\n",lens[i],result);return 10+result;}
    }
    int x=corrupted_crc(s);
    if(x){fprintf(stderr,"corrupted CRC: %d\n",x);return 20+x;}
    x=noisy_stream(s);
    if(x){fprintf(stderr,"noise/resync: %d\n",x);return 30+x;}
    x=oversize_and_empty(s);
    if(x){fprintf(stderr,"oversize: %d\n",x);return 40+x;}
    packet_free(s);
    if (live_allocations != 0) return 5;
    puts("G30 packet.c fragmented/invalid stream and OOM tests OK");
    return 0;
}
"""

class G30PacketStream(unittest.TestCase):
    def test_actual_vesc_packet_c_corruption_resync_and_boundaries(self):
        cc = shutil.which("cc") or shutil.which("gcc")
        if not cc:
            self.skipTest("No host C compiler")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            # The included real packet.c expects the FreeRTOS header.
            # Host malloc/free shims live in the compiled C harness.
            (folder / "FreeRTOS.h").write_text("#pragma once\n")
            test_c = folder / "packet_harness.c"
            test_c.write_text(C_TEST)
            target = folder / "packet_harness"
            build = subprocess.run(
                [cc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                 "-I", str(SRC), "-I", str(folder),
                 str(test_c), "-o", str(target)],
                capture_output=True, text=True
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            run = subprocess.run([str(target)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0,
                             f"exit={run.returncode}: {run.stdout} {run.stderr}")


if __name__ == "__main__":
    unittest.main()
