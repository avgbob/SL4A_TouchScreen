# Gate 2 capture attempt 2026-09-22 — REJECTED

This is a capture-level rejection, not a Windows-behavior conclusion.

## Trace identity

- ETL SHA-256: `1db3dff3f8bceb154cd801d909b4882afa44955a51f128e2b874e0550b8992de`
- ETL bytes: `10100`
- tracerpt buffers: `2`
- tracerpt events: `52`
- tracerpt events lost: `0`
- ETL header interval: approximately `11.7060486 s`

## Why it is rejected

The run used `wpr -start ... -shutdown`.

After cold power-on, `wpr -status` reported:

`Shutdown trace is stopped and waiting to be merged. Use -stop to merge the trace.`

Therefore the recorder was no longer active during the scripted T1-T6 work.

The decoded tracerpt output confirms that the final ETL is only the short pre-shutdown trace. The external `markers.tsv` contains later T1-T6 timestamps, but those local marker files do not prove that their corresponding ETW events are present in the ETL.

Consequently this attempt cannot answer any of the four Gate 2 binary questions:

1. cold / disable-enable `_RST`;
2. `_INI/_PS0/_PS3` lifecycle;
3. post-RDESC ID5 / ID6 / 0x56;
4. finger-down 0x0C vs 0x40 and reader.

No Linux behavior may be changed from this attempt.

## Harness correction

Gate 2 now uses the WPR boot autologger:

- `wpr -boottrace -addboot ... -filemode` before the S5 power-off;
- require an actively recording WPR session after cold boot;
- perform T1-T6 while that boot trace remains active;
- `wpr -boottrace -stopboot gate2.etl` at T6;
- run a tracerpt structural postcheck and reject any ETL shorter than 60 seconds.

The HID report-descriptor helper's x64 DevicePath offset was also corrected separately.
