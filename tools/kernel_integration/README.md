# Experimental in-tree kernel integration (Surface Laptop AMD)

**Status: Stage 0 / build preparation.** Not a proven bootable kernel, an upstream patch
series, or an automatic ACPI activation solution. This is an opt-in research branch.
Do **not** merge this branch into the qualified Gate5 production branch or use it
as a replacement for the installed driver yet.

## Scope

The `stage-in-tree.sh` script creates two isolated subtrees in a *clean, separate*
Linux source checkout:

| Location in Linux checkout | Configuration | Produced module |
| --- | --- | --- |
| `drivers/spi/sl4a/` | `CONFIG_SL4A_AMD_SPI=m` | `sl4a-spi-amd.ko` |
| `drivers/hid/sl4a/` | `CONFIG_SL4A_HID_SPI=m` | `sl4a-spi-hid.ko` |

It copies the existing source files rather than changing the qualified Gate5
state machine. `spi-amd.h` is duplicated inside the HID subtree because the
current HID driver includes it directly; this is a **temporary staging
compromise**, not a proposed mainline architecture. Both Kconfig entries are
**module-only and off by default**, because the qualified Gate5 path depends on
specific module parameters. The existing `AMDI0060` controller code deliberately
does **not** export an ACPI modalias; this stage does not change that.

## 1. Start on a development Linux machine

Install a suitable C compiler, kernel build dependencies, Git, make, Python,
flex, bison, OpenSSL development headers, ELF development headers, and ncurses
build headers for your distribution. A full Linux source checkout and sufficient
free disk space are required. **Do not test this on the only bootable kernel.**

```bash
# Clone your own fork and select this isolated branch.
git clone https://github.com/avgbob/SL4A_TouchScreen.git
cd SL4A_TouchScreen
git switch experiment/in-tree-kernel

# Read-only inventory of the Surface host, if running this on that machine.
bash tools/kernel_integration/check-host.sh

# Run staging tests without changing a real Linux source tree.
bash tools/kernel_integration/selftest.sh
```

Acquire a **separate clean kernel source checkout** of the version you intend
to test (ideally the source corresponding to a kernel configuration already
known to boot on the machine). Track its exact Git commit. Do not confuse
`/usr/src/linux-headers-*` with a complete Linux source tree.

```bash
# Substitute the absolute directory of that clean Linux Git checkout.
KERNEL_SRC="$HOME/src/linux-sl4a-experiment"

bash tools/kernel_integration/stage-in-tree.sh --check "$KERNEL_SRC"
bash tools/kernel_integration/stage-in-tree.sh --apply "$KERNEL_SRC"

git -C "$KERNEL_SRC" diff --check
git -C "$KERNEL_SRC" diff -- drivers/hid/Makefile drivers/hid/Kconfig \
    drivers/spi/Makefile drivers/spi/Kconfig
```

Staging intentionally leaves the Linux checkout dirty and refuses a second
application. To start again, discard the *dedicated experimental checkout* and
create a new one. Never run `git clean -fdx` or `git reset --hard` in a checkout
with valuable work or uncommitted changes.

## 2. Configure the custom kernel

The first build should use **modules**, not built-in drivers. On a matching
x86-64 machine with an already working kernel config available:

```bash
cd "$KERNEL_SRC"
cp "/boot/config-$(uname -r)" .config

# This must be a source tree providing scripts/config.
./scripts/config --enable MODULES \
    --module SL4A_AMD_SPI --module SL4A_HID_SPI
make olddefconfig

grep -E '^CONFIG_(SL4A_AMD_SPI|SL4A_HID_SPI)=' .config
# Both should read =m. If not, stop and resolve Kconfig dependencies.
```

The copied running-kernel config is only a starting point; it is not a guarantee
that your new source version will boot the machine. For the prototype the
configuration requires `ACPI`, `SPI_MASTER`, `HID`, `INPUT`, `X86`, and `MODULES`.

## 3. Build, inspect, and stop short of installation

```bash
cd "$KERNEL_SRC"
make -j"$(nproc)" bzImage modules

# A successful build should leave both custom modules in the source tree.
test -s drivers/spi/sl4a/sl4a-spi-amd.ko
test -s drivers/hid/sl4a/sl4a-spi-hid.ko
modinfo drivers/spi/sl4a/sl4a-spi-amd.ko | head
modinfo drivers/hid/sl4a/sl4a-spi-hid.ko | head
```

**Checkpoint:** A successful compilation is not a successful probe, let alone
verified touch input. Preserve build logs and the kernel/SL4A Git SHAs. Don't
install or boot this build until a fallback kernel, console access and a
Secure Boot signing plan are documented. A custom kernel image may require
separate signing even when your existing DKMS MOK process works for modules.

## 4. Follow-up experiments (not performed by this stage)

1. Validate isolated module binding on the real `AMDI0060`/`MSHW0231` Surface,
   with its working driver unloaded **only in a planned recovery session**.
   Check for an existing `spi-amd` binding and conflicting module aliases first.
2. Preserve the known-good Gate5 parameter set from
   [`docs/GATE5-QUALIFICATION.md`](../../docs/GATE5-QUALIFICATION.md):
   `raw_mode=N`, `raw_input_beta=Y`, `wire_double_opcode=1`,
   `skip_std_getfeat=1`, `std_raw_transition=1`, and other pinned options.
3. Verify descriptor discovery, real touch, warm reload, s2idle suspend/resume,
   and frame/reset counters on the exact test hardware.
4. Only then design **automatic ACPI module loading** and removal of the
   activation service. Exporting a controller modalias too early could change
   device-claim timing and interfere with the current working installation.
5. Upstream work remains separate: review the AMD SPI integration, possible
   reuse of a generic HID-over-SPI transport, CapImg tracking placement, and
   safety fixes with subsystem maintainers before proposing mainline code.

## Safety and validation boundaries

- `main` and the known-good Gate5 hardware checkpoint are unchanged.
- The staging script never executes `modprobe`, `insmod`, `dkms`, `make install`,
  `make modules_install`, `update-grub`, `mokutil`, or firmware writes.
- No new module autoload alias or systemd activation unit is installed.
- `MSHW0230` is not added or qualified by this prototype.
- Build results must not be represented as hardware validation.
- The staging layout is intentionally temporary and **not ready for a Linux
  kernel mailing-list submission**.
