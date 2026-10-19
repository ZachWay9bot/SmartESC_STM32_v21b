#!/usr/bin/env python3
"""Static / negative release regression tests. Never opens a serial port."""
import tempfile
from pathlib import Path
from release_qualification import static_check, check_hardware

def main():
    errors = static_check()
    assert not errors, errors
    with tempfile.TemporaryDirectory() as td:
        assert check_hardware(Path(td)/"missing.json",None), "missing physical evidence unexpectedly accepted"
    maker = (Path(__file__).resolve().parents[1]/"make_shu_zip.py").read_text()
    assert "FLASHABLE PACKAGE BLOCKED" in maker
    assert '"--release"' in maker and "release_qualification.py" in maker
    print("PASS: SmartESC power-on recovery ordering, IAP command guards, no FO91 gates")
    print("PASS: SHU packaging fails closed unless independent UART rollback evidence is provided")

if __name__ == "__main__":
    main()
