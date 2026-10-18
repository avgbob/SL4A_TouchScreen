# Windows 0C19 candidate-score typing — 2026-10-17

## Result

`userspace/surface-processor/windows_classifier.py` is a clean-room,
parameterized implementation of the arithmetic directly visible in
`FUN_180601690`. It decodes the ten consumed candidate fields, constructs the
configuration-controlled suppression mask, evaluates four gated
upper-triangular quadratic score blocks, and applies the recovered score-3 edge
penalty.

It is **not a complete Windows classifier**. It does not assign semantic class
names, choose a winning score, implement the special override paths, or emit a
contact. Most importantly, no valid post-initialization runtime coefficient
snapshot has been recovered. The module therefore has no invented default
model and is not connected to replay, Gate 5, uinput, or the kernel driver.

## Pinned sources

The source is preserved at historical commit
`c94c399618b23588c95711ab4449d9400036ffd0`:

| Function | Git blob | Direct role |
|---|---|---|
| `FUN_180600c40` | `982fd637201fa7751f50d303e3c0d74ed05022fc` | produces candidate fields and derived geometry/signal values |
| `FUN_180601690` | `76723e8825d06f2b25c2a4e3f1b853024ee93036` | builds the ten-value vector and four scores |
| `FUN_1806042f0` | `2d40aaa00f52686398f1cb10fc7b6b5ff71c943a` | produces three byte pairs at candidate `+0x98..+0x9d` |
| `FUN_180605960` | `5cab0e9b6f6a3140f5101103eab417e77cef70ad` | produces candidate float `+0x94` |

The audited `TouchPenProcessor0C19.dll` is 9,770,336 bytes with SHA-256
`f05828f04eb7df02ad5a2eeae136ef19d504f987afe2c06d0375ee1264300b4a`.
The historical decompiler C is evidence, not imported driver source.

## Candidate input contract

The candidate record starts at tracker `+0xca58`, has stride `0xb0`, and the
score kernel consumes fields in this exact order:

| Vector index | Candidate field | Recovered production | Safe name/status |
|---:|---:|---|---|
| 0 | `+0x9e`, `u16` | copied from candidate `+0x38` in the normal path | component-cell/count value; exact population semantics still need detector typing |
| 1 | `+0x99`, `u8` | second output of segmentation pass 0 | neutral byte feature 1 |
| 2 | `+0x9b`, `u8` | second output of segmentation pass 1 | neutral byte feature 2 |
| 3 | `+0x9d`, `u8` | second output of segmentation pass 2 | neutral byte feature 3 |
| 4 | `+0x98`, `u8` | first output of segmentation pass 0 | neutral byte feature 4 |
| 5 | `+0x9a`, `u8` | first output of segmentation pass 1 | neutral byte feature 5 |
| 6 | `+0x9c`, `u8` | first output of segmentation pass 2 | neutral byte feature 6 |
| 7 | `+0x8c`, `f32` | eigenvalue/axis-derived ratio in `FUN_180600c40` | derived moment ratio; human meaning unproved |
| 8 | `+0x90`, `f32` | trace/count-derived statistic in `FUN_180600c40` | derived moment statistic; human meaning unproved |
| 9 | `+0x94`, `f32` | normalized accumulation in `FUN_180605960`, or `100.0` outside its size gate | normalized signal/neighbour statistic; exact meaning unproved |

Candidate `+0x38` separately gates each score block. Candidate bytes `+0x4c`
and `+0x4d` condition the post-score penalty. Using offset names is deliberate:
terms such as finger, palm, confidence, or coalesced are not established.

## Recovered score equation

For feature index `i`, the effective suppression byte is:

```text
suppress[i] = (config[0x11c+i] & tracker[0x163ac]) |
              config[0x10c+i]
delta[i] = 0                                      if suppress[i] != 0
           feature[i] - block.mean[i]             otherwise
```

There are four blocks. Block `k` starts at `config + 0x134 + k*0x1d0` and is
eligible when candidate `u16 +0x38 <= config.u32[0x870 + 4*k]`. An ineligible
block receives the DLL constant `-9999.0`.

The transform is upper triangular and **packed at the start of each 0x2c-byte
row**, rather than stored with a dense column offset:

```text
transformed[row] = sum(block[row*0x2c + 4*(column-row)] * delta[column]
                       for column in row..9)
norm = sum(transformed[row]^2 for row in 0..9)
limit = block.f32[0x1c4] if tracker[0x163f8] == 1 else block.f32[0x1c0]
score = limit - 0.5*block.f32[0x190] + tracker.f32[0x194ac] - 0.5*norm
```

Means are ten floats at block `+0x198`. After all four scores are written to
candidate `+0xa0..+0xac`, score 3 is reduced by `config.f32[0x8d0]` when byte
`+0x4c == 1`; otherwise it is reduced by `config.f32[0x8d4]` when byte
`+0x4d == 1`.

## Static-image audit and missing runtime state

The selector for product `0x0c19` points to `DAT_1808e0460`, whose PE file
offset is `0x8df060`. Reinterpreting its on-disk bytes using the runtime layout
does not produce a usable model:

- forced mask bytes at `+0x10c` are `ff 07 00 00 00 00 00 00 01 00`;
- conditional mask bytes at `+0x11c` are `00 47 00 2f 00 00 00 00 00 00`;
- the four apparent `u32` gates at `+0x870` become `10`, `22937850`,
  `39322050`, and `58983150`;
- across the four interpreted score blocks, block 2 contains five NaN float
  values;
- the same region visibly contains byte sequences and `0xffff`-style
  sentinels, consistent with the prior MSI static-image correction.

Therefore the static bytes are initialization/configuration storage that must
not be presented as live classifier coefficients. The exact indirect producer
or mutation path remains unresolved. `classifier_config_from_runtime_bytes()`
accepts only a post-initialization layout and rejects non-finite fields, making
this missing evidence fail closed.

## Deliberately excluded paths

`FUN_180601690` contains behavior beyond the common score kernel:

- mode-0 small-geometry/signal score replacement;
- range-table overrides through `FUN_180605550`;
- a spatial rectangle test through `FUN_180609480` that can add `100.0` to
  score 3 under additional candidate flags.

Those paths are documented but not folded into the kernel because they require
more configuration typing and upstream state. The downstream winner/history
logic also remains separate. Implementing only the visible arithmetic prevents
a structurally correct score function from being mislabeled a complete class
decision.

## Integration gate

Before this stage may influence emitted Linux contacts:

1. capture or otherwise recover the initialized 0C19 configuration region and
   its relevant tracker-mode bytes;
2. independently reproduce at least one candidate vector and four score values
   from Windows;
3. type and test all three override paths;
4. recover how the four scores are selected and propagated through track
   history without assigning guessed class names;
5. replay V4 and far-contact controls, then verify deliberate lift and close
   returned-finger cases against the OS-visible oracle.

Until those gates pass, this module is an executable specification and unit-
tested boundary, not a behavior change.
