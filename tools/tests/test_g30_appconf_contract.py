#!/usr/bin/env python3
"""Static regression checks for the G30 VESC APPCONF wire contract.

Run: python3 -m unittest discover -s tools/tests -p 'test_g30_appconf_contract.py'
These tests are source-level checks, NOT a firmware build or hardware test.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
GEN = (ROOT / "common_files/src/confgenerator.c").read_text()
COMMANDS = (ROOT / "common_files/src/VescCommand.c").read_text()


def function_body(text, marker):
    start = text.index(marker)
    first_brace = text.index("{", start)
    depth = 0
    for pos in range(first_brace, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return text[first_brace + 1:pos]
    raise AssertionError(f"Unterminated function: {marker}")


def wire_bytes(body, direction):
    count = 0
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if line.startswith("//") or line.startswith("*"):
            continue
        offset = re.search(r"\bind\s*\+=\s*(\d+)\s*;", line)
        if offset:
            count += int(offset.group(1))
        if "buffer[ind++]" in line:
            count += 1
        prefix = "buffer_get_" if direction == "read" else "buffer_append_"
        match = re.search(prefix + r"(uint32|uint16|float32_auto|float16)\(", line)
        if match:
            count += 2 if "16" in match.group(1) else 4
    return count


class G30AppconfContract(unittest.TestCase):
    def test_generated_wire_lengths_are_identical(self):
        encoded = wire_bytes(function_body(
            GEN, "int32_t confgenerator_serialize_appconf("), "write")
        decoded = wire_bytes(function_body(
            GEN, "bool confgenerator_deserialize_appconf("), "read")
        self.assertEqual((encoded, decoded), (476, 476))

    def test_g30_dispatcher_guards_unbounded_decoder(self):
        section = COMMANDS.split("static void commands_process_packet_g30", 1)[1].split(
            "\n#endif", 1)[0]
        case = section.split("case COMM_SET_APPCONF:", 1)[1].split(
            "case COMM_GET_APPCONF:", 1)[0]
        self.assertIn("G30_APPCONF_WIRE_BYTES = 476", case)
        self.assertLess(case.index("if (len != G30_APPCONF_WIRE_BYTES) break;"),
                        case.index("confgenerator_deserialize_appconf(data, new_conf)"))
        self.assertLess(case.index("*new_conf = *active;"),
                        case.index("confgenerator_deserialize_appconf(data, new_conf)"))

    def test_g30_dash_configuration_is_preserved(self):
        section = COMMANDS.split("case COMM_SET_APPCONF:", 1)[1].split(
            "case COMM_GET_APPCONF:", 1)[0]
        for field in ("app_to_use", "app_adc_conf.ctrl_type",
                      "app_uart_baudrate", "shutdown_mode"):
            self.assertIn(f"new_conf->{field} == active->{field}", section)
        self.assertLess(section.index("if (conf_general_store_app_configuration(new_conf))"),
                        section.index("app_set_configuration(new_conf);"))
        self.assertLess(section.index("app_set_configuration(new_conf);"),
                        section.index("reply_func(send_buffer, 1u, phandle);"))


if __name__ == "__main__":
    unittest.main()
