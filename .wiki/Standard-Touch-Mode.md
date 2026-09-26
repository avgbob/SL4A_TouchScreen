# Standard Touch / Gate5 Mode

The installed `raw_mode=0` behavior is now **device-specific**.

## Surface Laptop 4 AMD / MSHW0231

Gate5 keeps normal HID-over-SPI discovery and the standard HID device, then
switches the panel to the CapImg stream:

```text
_PS0 -> _RST
  -> RESET_RSP / DEVICE_DESC / 936-byte RDESC
  -> write GET_FEATURE report 6
  -> do not synchronously consume the reply
  -> wait 4.5-5.5 ms
  -> SET_FEATURE report 5 = 1
  -> DONE / 0x0c CapImg
  -> beta tracker -> MSHW0231 Touchscreen MT node
```

The standard profile pins `skip_std_getfeat=1` so a generic HID feature
GET_REPORT cannot insert a competing feature transaction. The standard HID
device remains registered; beta heatmap contacts are published separately.

This path was field-qualified on one SL4 unit at Gate5: true cold power-on +
touch, 3/3 warm reload + touch, and 2/2 s2idle resume + touch, with zero
observed frame drops and no unexpected post-DONE reset in those captures.

## Surface Laptop 3 AMD / MSHW0162

The installer deliberately retains the conservative standard-HID profile:

```text
raw_mode=N wire_double_opcode=1
```

The Gate5 MSHW0231 activation sequence is not claimed on SL3 until separately
qualified.

## Historical standard coordinate reports

Without a CapImg transition, the panel can emit firmware-computed report
`0x40` touch coordinates and report `0x01` pen/stylus data. Those reports
are forwarded through `hid_input_report()`. Pen remains unqualified.

The earlier mode-3 SET5-only bridge is preserved as a historical experiment,
not current installer policy. See `docs/STANDARD-SET5-MULTITOUCH.md` and
`docs/GATE5-QUALIFICATION.md`.
