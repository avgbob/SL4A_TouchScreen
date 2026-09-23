# Gate 2 evidence directory

Do not hand-edit capture products placed here.

Expected after the single Windows capture:

- `gate2.etl`
- `capture-manifest.json`
- `markers.tsv`
- PnP / SetupAPI / registry / power evidence
- same-boot HID report descriptor or explicit recovery failure
- `windows-golden.jsonl` produced during decode

Gate 2 is not complete until `docs/GOLDEN-SM.md` gives a binary PASS/REJECT against `docs/GATE2-CAPTURE.md`.


## Accepted golden capture

Gate 2 is closed **PASS** for the lifecycle/transport contract.

- ETL SHA-256: `4583C62F0A7AC1B2099AA904FF8F61BF1DE065A2A2EF1AB58397950E57906552`
- Verdict: `docs/GOLDEN-SM.md`
- Normalized rows: `windows-golden.jsonl`
- Upper-layer software synthesis of touchscreen report `0x40` remains explicitly outside the SPB transport claim.
