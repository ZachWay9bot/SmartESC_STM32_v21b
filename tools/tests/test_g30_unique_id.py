#!/usr/bin/env python3
"""Source regression for G30 3-Cap unique VESC Tool controller identity.

Hardware UID bytes are fixed by STM32 silicon and cannot be verified on CI.
No firmware flash, UART, or motor action is performed by this test.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
VESC = (ROOT / "common_files/src/VescToSTM.c").read_text()
COMMANDS = (ROOT / "common_files/src/VescCommand.c").read_text()
RECOVERY = (ROOT / "common_files/src/g30_recovery_iap.c").read_text()


class G30UniqueID(unittest.TestCase):
    def test_g30_reports_factory_uid_from_same_silicon_address_as_recovery(self):
        function = VESC.split("uint8_t VescToSTM_get_uid(", 1)[1].split("\n}", 1)[0]
        g30 = function.split("#ifdef G30P", 1)[1].split("#else", 1)[0]
        self.assertIn("0x1FFFF7E8u", g30)
        self.assertIn("memcpy(ptr, uid, size);", g30)
        self.assertIn("if(size>12) size=12;", function)
        self.assertIn("ind += VescToSTM_get_uid(buffer + ind, 12);", COMMANDS)
        self.assertIn("0x1FFFF7E8u", RECOVERY)
        self.assertNotIn("test[12]", g30)

    def test_other_targets_keep_their_existing_uid_fallback(self):
        function = VESC.split("uint8_t VescToSTM_get_uid(", 1)[1].split("\n}", 1)[0]
        nong30 = function.split("#else", 1)[1].split("#endif", 1)[0]
        self.assertIn("test[12]", nong30)
        self.assertIn("memcpy(ptr, test, size);", nong30)


if __name__ == "__main__":
    unittest.main()
