# Surface Laptop 4 AMD — experimental in-tree kernel integration

**Status (2026-10-16):** a reproducible **source-pinned prototype** for Linux
`6.18.57`, **not** a boot-tested or approved kernel for the physical Surface.
The exact out-of-tree [PR #87](https://github.com/Syax89/SL4A_TouchScreen/pull/87)
HID driver passed five defined hardware qualification categories on one SL4 AMD
at **Ubuntu 7.0.0-34-generic**. This does **not** automatically validate the
new in-tree integration, its AMD controller, its Linux kernel version or boot
image. It is crucial not to conflate these environments.

## What changed since the Gate5-only kernel scaffold

- The **default** source for **both** in-kernel layouts is the full, unmodified
  PR #87 C/H driver set from upstream commit
  `18f0fe79623e6de4fdf1ae493f82a7048397386a`. A frozen snapshot of all **14 C/H Git blobs** lives in
  `kernel-pins/pr87/driver/`; the manifest lists exact blob object IDs.
- The source selector verifies the pinned commit, the unchanged manifest,
  individual Git blob identities, file inventory and uniqueness before writing
  to a Linux source tree. CI also tests corrupt source, manifest and identity
  negative controls. **No download of a moving upstream branch occurs.**
- `tools/in-tree/prepare-kernel.sh` (used by the kernel package CI) and
  `tools/kernel_integration/stage-in-tree.sh` now stage the same exact
  PR #87 source by default, including the **PR87 tracker**.
- The branch's original `driver/` files — including the separate Gate5 and
  advanced tracker-lab work — have **not** been overwritten or discarded.
  For a deliberately separate **unqualified** comparison, set
  `SL4A_IN_TREE_SOURCE=legacy-gate5` for either staging script.
  **Do not mix** PR87 core with older experimental tracker files and call
  that exact-head PR87; that would be a new, unqualified hybrid.
- The native kernel build uses `CONFIG_SL4A_SPI_AMD=m` and
  `CONFIG_SL4A_SPI_HID=m`, disables the stock `CONFIG_SPI_AMD`
  to avoid conflicting AMDI0060 ownership, uses
  `CONFIG_LOCALVERSION="-sl4a-pr87"`, and creates two separate native
  `.ko` modules. No ACPI `MODULE_DEVICE_TABLE(acpi)` aliases were added;
  test loading remains manual/opt-in.
- Package artifacts include the exact upstream source commit, local
  integration commit, source-flavor label, kernel config and pinned source
  blob manifest. Existing installed Gate5/DKMS and Secure Boot keys
  remain untouched by this build branch.

## Scope of the two in-tree layouts

| Build path | Destination in a separate kernel source tree | Driver source |
| --- | --- | --- |
| `tools/in-tree/prepare-kernel.sh` | `drivers/staging/sl4a/` | PR87 default |
| `tools/kernel_integration/stage-in-tree.sh --apply` | `drivers/spi/sl4a/`, `drivers/hid/sl4a/` | PR87 default |

These are *alternative staging experiments*, not two sets of drivers
to enable simultaneously. The `drivers/staging/` implementation is
the one exercised by the Debian kernel-package workflow. The
`drivers/spi/` plus `drivers/hid/` version is independently
smoke-tested against disposable Git fixtures, but is **not** bundled
into the staging kernel package.

## Build and inspect without changing the Surface

[GitHub Actions](https://github.com/avgbob/SL4A_TouchScreen/actions/workflows/in-tree-kernel.yml)
on `experiment/in-tree-kernel` runs source audits, fail-closed tamper
controls, both layout simulations and a full pinned-source kernel
`6.18.57` build/package job. **CI compilation does not prove boot
or touch input**; inspect the actual completed run before making claims.

Inspect the downloadable `sl4a-linux-6.18.57-pr87-experimental`
artifact's `source-commit.txt`, `source-flavor.txt`,
`integration-commit.txt`, `pinned-driver-blobs.txt`,
`kernel.config`, warnings, Debian packages and
`SHA256SUMS.txt`. Verify they name
`18f0fe79623e6de4fdf1ae493f82a7048397386a` and `pr87`.

Commands for local **non-installing** source integration:

```bash
git switch experiment/in-tree-kernel
bash tools/in-tree/source-selector-test.sh
bash tools/in-tree/audit.sh
bash tools/kernel_integration/selftest.sh

# Only in a deliberately separate extracted, full Linux kernel source tree:
bash tools/in-tree/prepare-kernel.sh /path/to/linux-6.18.57
bash tools/in-tree/configure-kernel.sh /path/to/linux-6.18.57 \
    "/boot/config-$(uname -r)"
```

`configure-kernel.sh` accepts a copy of the *working* config as
a starting point; GitHub Actions instead uses `x86_64_defconfig`
and is **not** a Surface-specific boot configuration. The kernel
sources must be obtained separately with pinned archive checksum.

## Hardware and mainline limitations

**Do not install/boot unsigned CI packages with Secure Boot enabled.**
A new kernel *image* requires its own signing/trust plan, distinct
from the existing MOK-signing process for DKMS modules.

Before ever rebooting the SL4 with this kernel: verify a complete
hardware-specific config (storage, display, firmware, networking,
keyboard, PM); native module precedence vs DKMS; module loading
order and ACPI binding conflicts; trusted bootloader entry; backup
known-good kernel; independent mouse/keyboard or recovery path.
First physical gate is a **manual native-controller-then-HID load**,
not automatic ACPI binding. Then rerun real cold first-HID,
warm, guided multitouch and s2idle acceptance **on that exact
kernel**, recording the new module hashes and source pin.

A Linux in-tree build is not a mainline upstreaming patch by
itself. For eventual kernel-mainline work, the AMD SPI controller,
HID-over-SPI architectural boundaries, CapImg tracker location,
interface duplication, ACPI matching and Kconfig policy need
separate subsystem maintainer review and supported hardware data.

**Unqualified despite PR #87's out-of-tree hardware PASS:** this
custom kernel's boot, driver autoload, native module load on the
machine, native cold/PM behavior, broader Surface models, stylus,
spontaneous post-DONE reset/rearm and long-running stability.
