# Windows 0C19 candidate-score typing — 2026-10-17

## Result

`userspace/surface-processor/windows_classifier.py` is a clean-room,
parameterized implementation of the arithmetic directly visible in
`FUN_180601690`. It decodes the ten consumed candidate fields, constructs the
configuration-controlled suppression mask, evaluates four gated
upper-triangular quadratic score blocks, and applies the recovered score-3 edge
penalty.

It is **not a complete Windows classifier**. It does not assign semantic class
names, implement the special override paths, or emit a contact. The later
initialization audit recovered the correct static configuration-object base,
but no Microsoft coefficient bytes are bundled in this repository. The module
therefore still has no implicit default model and is not connected to replay,
Gate 5, uinput, or the kernel driver.

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

## Corrected configuration base

The first static-image audit decoded the enclosing product record from the
wrong address. It is retained as a useful fail-closed test, but its conclusion
was wrong.

The corrected initialization chain is:

1. `FUN_180625d60` maps product `0x0c19` to `DAT_1808e0460`;
2. the PE exception table bounds the previously unidentified device
   initializer at `0x18068bfc0..0x18068d335`;
3. that initializer passes `DAT_1808e0460 + 0xecc` as the fifth argument to
   the tracker initializer at `0x1805ff7e0`;
4. `0x1805ff8f4` stores that argument at tracker context `+0x16480`;
5. `FUN_180601690`, `FUN_180607050`, and `FUN_1806071c0` address their
   classifier and transition fields through that pointer.

Decoding the pinned image from the shifted base produces four finite score
blocks with maximum-component gates `25, 9999, 30, 50`, score-3 penalties
`50.0` and `20.0`, and plausible finite means and transforms. This proves the
address correction; it does not authorize copying proprietary coefficient
bytes into the repository or treating the model as portable to another
processor version. A later write to the shared object has not been completely
excluded, so a live-memory comparison remains useful validation rather than a
prerequisite for understanding this initialization path.

`classifier_config_from_runtime_bytes()` now explicitly accepts a byte view
beginning at the object stored in context `+0x16480`. Supplying the enclosing
`DAT_1808e0460` base still fails on non-finite fields.

## Deliberately excluded paths

`FUN_180601690` contains behavior beyond the common score kernel:

- mode-0 small-geometry/signal score replacement;
- range-table overrides through `FUN_180605550`;
- a spatial rectangle test through `FUN_180609480` that can add `100.0` to
  score 3 under additional candidate flags.

Those paths are documented but not folded into the kernel because they require
more configuration typing and upstream state. The downstream winner/history
gates are implemented separately in `windows_class_transition.py`; the
surrounding state machine remains excluded. Keeping these layers separate
prevents a structurally correct score function from being mislabeled a
complete class decision.

## Integration gate

Before this stage may influence emitted Linux contacts:

1. independently compare the shifted image configuration with a live Windows
   memory view, or prove the pointed-to object is never mutated;
2. independently reproduce at least one candidate vector and four score values
   from Windows;
3. type and test all three override paths;
4. finish the outer class-selection and later correction paths without
   assigning guessed class names;
5. replay V4 and far-contact controls, then verify deliberate lift and close
   returned-finger cases against the OS-visible oracle.

Until those gates pass, this module is an executable specification and unit-
tested boundary, not a behavior change.
