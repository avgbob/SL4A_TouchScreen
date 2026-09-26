#!/usr/bin/env python3

from pathlib import Path
import sys

root = Path(__file__).resolve().parent.parent
core = (root / "driver/spi-hid-core.c").read_text()

start = core.find(
    "static void seq_handle_data(struct spi_hid *shid, int type, u16 blen)\n{"
)

end = core.find(
    "\nstatic irqreturn_t spi_hid_dev_irq",
    start
)

errors = []

def check(v, msg):
    if not v:
        errors.append(msg)

check(start >= 0, "seq_handle_data not found")
check(end > start, "could not isolate seq_handle_data")

if start >= 0 and end > start:
    block = core[start:end]

    old_bug = """\
if (shid->hid_creating ||
\t    (!shid->hid"""

    check(
        old_bug not in block,
        "DATA path still returns before drain when hid_creating"
    )

    check(
        "!shid->hid && !shid->hid_creating" in block,
        "pre-drain eligibility does not preserve hid_creating frames"
    )

    check(
        "spi_hid_seq_read(shid, body, rblen)" in block,
        "DATA body read missing"
    )

    check(
        "shid->hid && !shid->hid_creating" in block,
        "HID publication is not suppressed during registration"
    )

    drain = block.find(
        "spi_hid_seq_read(shid, body, rblen)"
    )

    publish = block.find(
        "if (shid->hid && !shid->hid_creating) {"
    )

    check(
        drain >= 0 and publish > drain,
        "HID publication guard must occur after DATA body drain"
    )

if errors:
    for e in errors:
        print("FAIL:", e)
    sys.exit(1)

print("gate5 DATA drain race source test: PASS")
