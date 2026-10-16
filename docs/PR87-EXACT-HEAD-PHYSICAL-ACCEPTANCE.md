# Syax89 PR #87 — exact-head hardware acceptance campaign

**Current status:** prepared, NOT YET physically executed as of 2026-10-16.
PR: https://github.com/Syax89/SL4A_TouchScreen/pull/87
Exact pinned test driver revision:
`18f0fe79623e6de4fdf1ae493f82a7048397386a`.
Expected physical target: Surface Laptop 4 AMD, MSHW0231,
Ubuntu kernel `7.0.0-34-generic`, Secure Boot enabled with existing
enrolled Ubuntu DKMS MOK. Known-working, installed boot fallback:
Gate5 `sl4a-touch/1.7.0` mode1, production driver source identity
`3326E559A916BE5CB52375D` from preceding hardware diagnosis.

## Why a separate campaign?

The GET6-free mode4 path successfully completed a true cold startup
on the user's hardware, but **this PR does not implement mode4**.
PR87 opts into `std_raw_transition=1 raw_input_beta=1`,
which writes GET_FEATURE6 **without synchronously reading it**,
waits 4.5–5.5ms, and then sets feature5. It must be independently
tested on its exact SHA, with a module whose srcversion differs from
installed Gate5.

Reviewer's 2026-10-16 scope finding about unsolicited report 0x0c
in ordinary/default standard mode was fixed at `18f0fe8`:
default post-creation IRQ handling holds report12 for observation,
not HID publication, and the opt-in MT tracker consumes it without
forwarding it to HID. Executable actual-handler regression tests
exercise opt-out `0x0c`, opt-in `0x0c`, non-`0x0c` standard
reports, raw with/without tracker, pre-HID drain ownership and
watchdog policy. Both kernel builds and host tests passed at
https://github.com/avgbob/SL4A_TouchScreen/actions/runs/38952701397.
These are **host/CI results only**.

## First physical step: exact-head WARM 3/3

The source-qualified test harness lives on the *independent*
`experiment/sl4-std-host56-set5` branch in
`tools/experiments/pr87-exact-head.sh`. It does NOT add test
scripts to the upstream PR driver branch.

```bash
cd ~/SL4A_TouchScreen-host56
git fetch https://github.com/avgbob/SL4A_TouchScreen.git experiment/sl4-std-host56-set5
git switch --detach FETCH_HEAD
bash tools/experiments/pr87-exact-head.sh preflight
bash tools/experiments/pr87-exact-head.sh warm3
```

The first command is read-only. The `warm3` command requires
typing **`WARM`** before driver modification. It fetches the
separate PR source into `~/SL4A_TouchScreen-pr87`, insists the
fetched PR head exactly matches `18f0fe8`, refuses tracked
modifications, builds the PR driver once against the current kernel,
signs it using the *already enrolled* Ubuntu MOK, verifies loaded
srcversion against the PR build (distinct from production), checks
both controller and HID bindings, and executes three independent
spoken `quick` gesture captures via the reused evidence collector.

**Important:** the evidence collector now supports
`--source-root ~/SL4A_TouchScreen-pr87`, so exact Git commit,
signed `.ko` hash and loaded srcversion come from the actual PR
driver checkout, not from the separate host56 harness checkout.
The program restores the original installed Gate5 between every
cycle, and in a shell EXIT trap on ordinary errors/interruption.
No DKMS install, persistent modprobe, systemd activation edit or
cold-boot override. As with every runtime module test, SIGKILL or
machine-wide failure can bypass shell EXIT: normal reboot preserves
the installed Gate5 startup path.

On a fully verified run, a successful verdict must include:
3/3 spoken event-gated one- and two-finger gestures, real increasing
CapImg DATA/observed counters, no newly dropped frames/unexpected
resets, identical signed SHA through all three cycles, actual loaded
PR srcversion in each capture, and restored installed Gate5 source
identity/bindings between and after the three cycles.

Evidence will be retained at
`~/sl4a-hardware-runs/pr87-exact-warm3-<timestamp>/`.
Do not claim 3/3 PASS from CI or from this documentation alone.

## Next acceptance categories after warm 3/3

1. **Exact-head full gesture matrix** (all phases with live evdev
   tracking IDs and release semantics); a short quick PASS is not the
   complete matrix.
2. **Two genuine s2idle suspend/resume cycles**, with actual sleep
   timing, postwake audible confirmation, touch, counters, and the
   same signed module identity before/after resume.
3. **True cold poweroff/power-on** using a separately reviewed
   one-shot systemd boot helper which consumes its override before
   experimental insertion, watches for prior HID probes, and has an
   independent timed rollback that reloads *both* AMD and HID
   controllers. Pin the PR code and running/next-boot kernel first.
4. **Default-standard negative control**: load the PR module
   with `std_raw_transition=0 raw_input_beta=0` on the exact
   MSHW0231, check the bridge does not register the MT tracker,
   verify ordinary HID policy/non-`0x0c` reporting, and restore
   Gate5. Default `0x0c` forwarding is separately guarded by
   compiled host tests; field control must not incorrectly infer
   lack of device output proves the conditional behavior.
5. **Spontaneous post-DONE reset/rearm** remains NOT EXERCISED
   unless it happens without explicitly forcing/reloading a module;
   do not re-label a warm reload as spontaneous-reset coverage.

The PR should remain a draft until relevant exact-head physical
checks and reviewer's remaining concerns are resolved. Source commits
made after `18f0fe8` invalidate the tester's hardcoded SHA pin
until re-reviewed and updated. Do not re-stage unrelated mode4
coldboot tests while doing PR87 tests.
