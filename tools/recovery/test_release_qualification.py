#!/usr/bin/env python3
"""Source recovery and bench-build workflow regression tests. Never opens a serial port."""
import tempfile
from pathlib import Path
from release_qualification import static_check, check_hardware

def main():
    errors = static_check()
    assert not errors, errors
    with tempfile.TemporaryDirectory() as td:
        assert check_hardware(Path(td)/"missing.json",None), "missing physical evidence unexpectedly accepted"
    root = Path(__file__).resolve().parents[2]
    workflows = root/".github/workflows"
    assert not (workflows/"build_g30_shu.yml").exists(), "SHU workflow is still active"
    for name in ("build_on_commit.yml", "release_on_tag.yml"):
        build = (workflows/name).read_text()
        assert "make_shu_zip.py" not in build, f"SHU packaging still active in {name}"
    bench = (workflows/"build_on_commit.yml").read_text()
    assert "tools/make_bench_iap.py" in bench, "Direct UART-IAP bench packaging missing"
    print("PASS: SmartESC power-on recovery ordering, IAP command guards, no FO91 gates")
    print("PASS: automatic builds publish BENCH UART-IAP, not SHU ZIPs")
    print("PASS: independent stock-restore evidence remains unverified (no hardware claim)")

if __name__ == "__main__":
    main()
