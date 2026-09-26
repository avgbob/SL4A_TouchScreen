# Validation Procedure

## Host Gate

Run from a clean checkout before every change:

```sh
git diff --check
make -C tests test
make -C tests clean
make -C tests SANITIZE=1 test
make -C tests clean
```

The protocol, CapImg decoder, replay-fixture, raw-capture-export, Gate4
activation, Gate5 mode-1 publication, Gate5 DATA-drain race, and Gate5
installer-profile source guards are required host coverage. `replay_fixture_test.py` has no success-by-skip path:
it verifies the eight tracked V0 bodies, deterministic malformed inputs, and
the recorded lifecycle-evidence classifications.

Six research checks (raw_transition_safety_test, isolated_set_safety_test,
post_set_timeline_test, surface_tracker_oracle_test, raw_corpus_test, and
v0_capimg_decoder_test) call `skip_optional_contract()` when their untracked
corpus, analyzer, or harness is absent, and `real_frame_replay_test` skips the
same way when the Windows frame corpus is missing. Because a skip is a pass,
they are **not** part of `make test`: they live in `make local-checks`, which is
what to run on a machine that has the corpora, and where a SKIP or a FAIL is
information rather than a green tick that means nothing.

## CI

GitHub Actions checks tracked whitespace, runs the `make test` host gate twice
(plain and with `SANITIZE=1`), and compiles the modules out-of-tree: once
against Ubuntu generic headers and once inside an Arch container, so the
version-guarded signatures are pinned from both sides of the kernel API change
(`kernel-build`, `kernel-build-current`). `SANITIZE=1` instruments the C
targets built from `$(CFLAGS)`/`$(LDFLAGS)`; the raw-pipeline and replay targets
carry their own flags and are not instrumented — their coverage comes from the
replay fixtures instead. The kernel jobs are compile smoke tests only: they do
not load modules or qualify a kernel, DKMS lifecycle, Secure Boot, or Surface
hardware behavior.

## Hardware Evidence Helpers

Validate the shell syntax without collecting host evidence:

```sh
bash -n tools/hardware_evidence/collect.sh
bash -n tools/hardware_evidence/capture_direct_touch.sh
bash -n tools/hardware_evidence/capture_linux_trace_bundle.sh
bash -n tools/hardware_evidence/run_blinded_session.sh
```

On target hardware, use a new output path and a short bounded session. This is
read-only, but journal and input permissions may require the caller to invoke
the helper with `sudo`; it never escalates itself:

```sh
sudo ./tools/hardware_evidence/capture_linux_trace_bundle.sh --duration 20 \
  --capture-direct-touch --output evidence/<run-id>/p1-touch-session
```

Check `manifest.txt` for the UTC bounds, journal exit status, and checksums.
Retain the complete listed bundle, including a permission-error journal artifact
when journal access was unavailable.

## DKMS Build

On a supported Linux target with matching kernel headers:

```sh
sudo ./tools/sl4a-touch.sh install --standard
dkms status
modinfo sl4a-spi-amd
modinfo sl4a-spi-hid
# The alias queries must print no output.
modinfo -F alias sl4a-spi-amd
modinfo -F alias sl4a-spi-hid
```

For a direct kernel build against a Clang-built kernel, add `LLVM=1`.

Record the exact kernel, compiler, DKMS version, distribution, Secure Boot
state, and build output in `COMPATIBILITY.md`.

## Target Hardware Matrix

Run each case only after login and after retaining a local console or remote
shell for recovery: the install step binds the out-of-tree controller itself
(Step 7) and enables the boot unit. Activation refuses to displace existing
AMDI0060 or touchscreen (MSHW0231/MSHW0162) drivers and verifies both bindings;
`sudo ./tools/sl4a-touch.sh activate` runs the same checks by hand.
Recover with `sudo modprobe -r sl4a-spi-hid sl4a-spi-amd` followed by a reboot.

The installer selects a device-aware standard profile by default: MSHW0231
gets the Gate5 mode-1 bridge while MSHW0162 keeps conservative standard HID.
Since `raw_mode` and the bridge controls are read-only after module load,
install the selected profile, then reboot before testing:

```sh
# Standard profile
sudo ./tools/sl4a-touch.sh install --standard

# Raw experimental profile
sudo ./tools/sl4a-touch.sh install --raw
```

Do not run the raw matrix unless the raw profile is recorded in the result.

| Case | Procedure | Expected evidence |
| --- | --- | --- |
| Cold boot | Fully power off, start, wait for the HID device. | `ready`, `protocol_stats`, dmesg excerpt. |
| Warm boot | Reboot without power removal. | Same as cold boot. |
| Reload | Unload/reload only when no input client uses the device. | No kernel warning, one controller/device binding. |
| Suspend/resume | Suspend for at least 30 seconds, resume, test input. | Lifecycle status before/after and dmesg. |
| Standard/Gate5 contacts | On MSHW0231 exercise the CapImg MT node (input-quality beta): one/two fingers, close-contact continuity, crossing/identity, rapid lift/re-contact, accidental third contact, then 3/4/5 fingers. On MSHW0162 exercise the conservative standard coordinate path. | evtest/libinput record plus `protocol_stats`; record the exact installed profile. |
| Legacy raw contacts | Only when explicitly testing `--raw`, exercise the intended contact matrix separately. | Contact recording plus raw profile and frame counters. |
| Stress | Run mixed touch input for 30 minutes. | Start/end counters, error count, and dmesg. |
| Secure Boot — enrolled-key reuse | Install and reboot with Secure Boot enabled while reusing the active enrolled DKMS MOK. | Resolved key/cert paths, `modinfo -F signer` for both modules, MOK state, service result, bound device. |
| Secure Boot — fresh enrollment | Generate/import a new DKMS certificate, complete firmware MOK Manager enrollment, reboot and verify automatic activation. | New identity paths, enrollment evidence, signer/load result and service result. |

Useful sysfs attributes are exposed by the SPI HID device: `ready`,
`protocol_stats`, `baseline_status`, `lifecycle_status`, and `heatmap_debug`.
Their path is platform-assigned; discover it under `/sys/bus/spi/devices/`.

## Result Template

```text
Date:
Surface model:
BIOS/firmware:
Kernel and distribution:
Secure Boot:
Profile and module parameters:
Cases run:
Observed result:
Capture/log checksum and path:
Evidence level:
```
