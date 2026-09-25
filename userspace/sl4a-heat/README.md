# sl4a-heat Gate-3 checkpoint client

This directory starts the Architecture-A userspace side.

The current client is intentionally **transport-only**. It does not decode the
CapImg raster, track fingers, or create a uinput device yet. Its only job is to
prove that the normal Linux HID device/hidraw boundary can carry the Windows
Col02 Heat traffic without the in-kernel raw tracker.

## What it does

For MSHW0231 / VID:PID `045e:0c19`:

1. find the matching `/dev/hidrawN`;
2. verify the sysfs report descriptor is exactly 936 bytes;
3. issue HID `GET_FEATURE` report 6 and require 120 HID bytes
   (`06` + 119 data bytes);
4. issue HID `SET_FEATURE` report 5 with payload `01`;
5. read hidraw and save exact 4300-byte numbered input report `0x0c` frames.

That maps the V0 transport envelope back to the descriptor-defined HID ABI:

- Gate-2 V0 ID6 content length 122 -> HID report `06` + 119 data bytes;
- Gate-2 V0 ID0C content length 4302 -> HID report `0c` + 4299 data bytes.

## Run

Use the standard transport path, not `raw_mode=Y`.

First inspect the available hidraw nodes:

```bash
sudo python3 userspace/sl4a-heat/sl4a_heat.py --list
```

Descriptor-only checkpoint:

```bash
sudo python3 userspace/sl4a-heat/sl4a_heat.py --no-arm
```

Gate-3 raw-frame checkpoint:

```bash
sudo python3 userspace/sl4a-heat/sl4a_heat.py \
  --frames 20 \
  --timeout 20 \
  --output-dir /tmp/sl4a-gate3
```

After `SET_FEATURE 5: payload=01 accepted`, touch and drag one finger on the
panel. Success ends with:

```text
GATE3 HIDRAW CHECKPOINT PASS
```

and the output directory contains `heat-*.bin` files, each exactly 4300 bytes
and beginning with report ID `0x0c`.

## Not implemented yet

- CapImg extraction;
- c590/baseline processing;
- blobs / association / contact tracking;
- uinput;
- suspend/resume re-arm;
- Col07 report 0x56.

Those come only after this boundary is proven on hardware.
