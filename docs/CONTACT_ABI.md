# Windows Contact ABI — evidence-corrected notes

The `TouchPenProcessor0C19.dll` produces candidate, tracker, and emitted plugin
records, *not* one proven C structure with the speculative fields previously
listed here. See `docs/decomp/SURFACE_TRACKER_DECOMP.md` for directly observed
offsets and the August `docs/SL4_MSI_Mining_Report.md` for static-table checks.

## Recovered records (Windows 0x0C19)

| Record | Observed layout | Evidentiary status |
|---|---|---|
| Candidate/blob | at tracker `+0xCA58`, stride `0xB0`, centroid near record `+0x24/+0x28`, validity/class near `+0x40/+0x41` | Decompiled structural observation; full meanings incomplete |
| Persistent track | at tracker `+0xF3D8`, stride `0x254`, up to **48 internal records** | Decompiled structural observation; **not** 48 simultaneous published fingers |
| Track state | track `+0x3C`: `0` free, `1/2` active, `3` transitional, `4` hold/inactive | Inferred names from tested counter transitions, not Linux state numbering |
| Track history | ten entries from `+0x58`, stride `0x30`; ring index `+0x251` | Decompiled structural observation (not the previous eight-entry guess) |
| Emitted plugin contact | frame `+0xAF84`, stride `0x34`; class `+0x2A`, mutable group `+0x2B`, source track `+0x2F` | Local DLL record, **not** a final kernel HID report |

**Do not equate Microsoft's track-state codes with the Linux module's
`0=empty / 1=new / 2=claimed / 3=lift / 4=hold` codes.** Likewise, a mutable
merge group is not a stable tracking ID.

## Candidate classification — `FUN_180601690`

The presence of Windows class/status codes `1`, `3`, `4`, `5`, and `7` in
specific control-flow paths is recovered, but **their human-readable meanings
are not yet established**. In particular the old mapping claiming `1=palm`
and `3=coalesced` was conjectural and must not be used to generate Linux
palm/finger events. The post-emission coalescer `FUN_1806025c0` can rewrite
eligible class `1` to `7` without deleting either local contact record.

**Static config correction:** the prior claim of a runtime-populated **10x11
Mahalanobis float matrix at `+0xD40..+0xD78` is falsified by the Microsoft
MSI binary audit**: the region contains structured bytes and `0xFF`
sentinels, and interpreting the words as floats yields NaNs. Its actual
indices and their use need targeted decompilation xrefs.

The precise classifier, gain adaptation, quality-conditional hold/lift and
Microsoft virtual-HID ID allocator remain unimplemented in the Linux research
processor. Do not substitute estimated coefficients or convert Windows
internal fields to Linux events until their roles are verified.

## Contact limits are layer-specific

- Windows internal tracks: maximum **48** records in the recovered structure.
- Linux beta internal slots: follow `HEATMAP_MAX_SLOTS` in the *actual build*,
  currently **47** in historical documentation.
- Published Windows contact limit: **not established by these two numbers**.
- Historical Linux default `hold_frames=0` is a workaround for release/scroll
  behavior, not a reconstruction of the Windows quality-gated hold state.

## Primary references

- `docs/decomp/SURFACE_TRACKER_DECOMP.md`
- `docs/decomp/MULTITOUCH_STATIC_DECOMP.md`
- `docs/SL4_MSI_Mining_Report.md`
- `docs/WINDOWS-ALIGNMENT.md`
