#!/usr/bin/env python3
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
core = (ROOT / "driver" / "spi-hid-core.c").read_text()
failures = 0

# 1. The three fixed 16-byte header buffers must remain guarded.
guards = core.count("hdr_len > sizeof(hdr)")
if guards != 3:
    print(f"FAIL: expected 3 hdr[] bounds guards, found {guards}")
    failures += 1

# 2. Extract spi_hid_hdr_len() and ensure WAIT_FEATURE can never request
#    more than the fixed 16-byte header buffers can hold.
m = re.search(
    r"static inline unsigned int spi_hid_hdr_len\(struct spi_hid \*shid\)"
    r"\s*\{(?P<body>.*?)\n\}",
    core,
    re.S,
)

if not m:
    print("FAIL: could not locate spi_hid_hdr_len()")
    failures += 1
else:
    body = m.group("body")

    wm = re.search(
        r"if\s*\(\s*shid->seq_state\s*==\s*SPI_HID_SEQ_WAIT_FEATURE\s*\)"
        r"\s*return\s+(\d+)\s*;",
        body,
        re.S,
    )

    if not wm:
        print("FAIL: WAIT_FEATURE header length is not a statically bounded integer")
        failures += 1
    else:
        n = int(wm.group(1))
        if n > 16:
            print(
                f"FAIL: WAIT_FEATURE header length {n} exceeds hdr[16]; "
                "this would recreate the kernel stack-overflow class"
            )
            failures += 1

# 3. Keep the known hardware checkpoint pinned for now.
if "return 12;" not in m.group("body") if m else True:
    print("FAIL: Gate-3 WAIT_FEATURE header window is no longer pinned to 12 bytes")
    failures += 1

if failures:
    print(f"header read bounds: {failures} failure(s)")
    sys.exit(1)

print("header read bounds: PASS")
