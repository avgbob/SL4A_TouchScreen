# Windows CapImg section staging — 2026-10-19

This note records the structurally reproduced `0x0100` section-staging boundary
for the pinned `TouchPenProcessor0C19.dll`:

- SHA-256:
  `f05828f04eb7df02ad5a2eeae136ef19d504f987afe2c06d0375ee1264300b4a`
- recovered function: `FUN_18068e990`, virtual address
  `0x18068e990..0x18068ecee`, 863 bytes;
- sole recovered caller: `FUN_18068d620`;
- private REA evidence identifier:
  `ev_b146878402863229723d6afd562fa42e36ae8621658563ac435fa239601a1cc7`.

The DLL and private REA snapshot are not committed. The public implementation
contains only derived control flow, layouts, tests, and digests.

## Recovered section contract

Every section starts with a little-endian `u32` section length, `u16` type and
`u8` encoding. Type `0x0100` has these two observed code paths:

| Encoding | Additional header | Run start | Sample representation |
| --- | --- | --- | --- |
| `1` | byte `+7` must equal `8` | `+8` | unsigned 8-bit |
| `0` | none recovered | `+7` | little-endian unsigned 16-bit |

Each run is `u32 destination`, `u32 sample_count`, then `sample_count`
samples. Runs continue until the declared section length is exhausted.

For encoding 1, if the first run count equals configured `width * height`, the
function returns a direct pointer to that first run's sample data rather than
copying or reordering it. Otherwise, each run is copied contiguously to:

```text
destination + (288 - width) * floor(destination / width)
```

The adjustment is applied once at the beginning of the run, not independently
to every sample.

For encoding 0, each u16 sample is converted in binary32 operation order as
`trunc(float(sample) * scale + bias)`, clamped to `0..255`, and written at
`destination + sample_index`.

The recovered return lengths are `0xb468` for encoding 1 and `0xb467` for
encoding 0. They are frame-object lengths and must not be interpreted as the
active pixel count.

## Selected 0C19 geometry

The `0x0100` section does not contain width or height. Related initialization
and selection functions establish their source:

| Function | Recovered relationship |
| --- | --- |
| `FUN_18060d340` | returns the singleton whose first qword is the selected configuration pointer |
| `FUN_180625d60` | registers product/config key `0x0c19` with `DAT_1808e0460` |
| `0x180627980` | looks up the key and stores the map-node value at `+0x28` as the selected configuration pointer |
| `FUN_18068d3c0` | selected configuration `+0x3c` supplies height and `+0x3e` supplies width |
| `FUN_1805ff7e0` | writes height to context `+0x1639c` from geometry `+0x1a`, and width to context `+0x1639e` from geometry `+0x18` |
| `FUN_18068bfc0` | calls configuration selection and then initialization |

The selected static record is at virtual address `0x1808e0460`. In the pinned
DLL, `.data` maps virtual address `0x180858000` to file offset `0x856c00`, so
the stream-0 geometry fields are independently reproducible at file offsets
`0x8df09c` and `0x8df09e`. Their little-endian u16 values are:

| Stream | Record fields | Height | Width | Status |
| --- | --- | ---: | ---: | --- |
| 0 | selected config `+0x3c/+0x3e` | 48 | 72 | configured |
| 1 | selected config `+0x78/+0x7a` | 0 | 0 | unconfigured |

This closes the earlier geometry uncertainty for the exact hash-pinned 0C19
profile: the captured 3,456-byte raster and the Windows stream-0 detector are
both 72×48. It does not establish geometry for a different product ID or DLL.

The recovered 288-byte stride applies only when Windows copies partial or
multi-run 8-bit data into its staging object. A complete 72×48 8-bit run takes
the fast path and remains a packed 3,456-byte direct view. Converted 16-bit
runs are also written at packed destinations. Treating either packed path as
288-byte-strided was an implementation error and is corrected in the public
model and tests.

## Verification and remaining gate

`windows_section_staging.py` strictly parses both encodings, exposes the PSDB
geometry-field layout, and distinguishes packed direct/converted grids from
288-byte-strided copied 8-bit grids. A separately compiled C11 oracle checks
randomized destination and binary32 calibration arithmetic.

This is **structural and numerical reproduction**, not Windows-output
comparison. For the pinned 0C19 stream 0, `packed_active_grid()` now produces
the correctly shaped 72×48 input boundary for the reconstructed initial CCL.
The next stronger gate is a Windows-runtime capture of internal staged or
candidate records, which would compare outputs rather than infer behavior from
the binary.
