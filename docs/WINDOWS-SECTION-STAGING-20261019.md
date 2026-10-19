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

## Geometry correction

The `0x0100` section does not contain width or height. Related initialization
and selection functions establish their source:

| Function | Recovered relationship |
| --- | --- |
| `FUN_18068d3c0` | selected configuration `+0x3c` supplies height and `+0x3e` supplies width |
| `FUN_1805ff7e0` | writes height to context `+0x1639c` from geometry `+0x1a`, and width to context `+0x1639e` from geometry `+0x18` |
| `FUN_18068bfc0` | calls configuration selection and then initialization |

Therefore, the 3,456 captured bytes can remain a 72×48 **capture-analysis
view**, but they do not prove that Windows configures a 72×48 logical detector.
The detector's recovered row accesses use a 288-byte stride. A direct 3,456-byte
run is compatible with multiple factorizations; for example, 288×12 is
indexable at that stride while 72×48 is not. This example is not a claim that
288×12 is the actual configuration.

## Verification and remaining gate

`windows_section_staging.py` strictly parses both encodings, models the direct
view and staging paths, and refuses geometry that cannot index the returned
buffer. A separately compiled C11 oracle checks randomized destination and
binary32 calibration arithmetic.

This is **structural and numerical reproduction**, not Windows-output
comparison. The next gate is to recover the actual selected runtime
configuration record and its `+0x3c/+0x3e` values. Until then, the staged bytes
must not be automatically fed into the reconstructed CCL as Windows detector
coordinates.
