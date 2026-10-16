# Experimental custom Linux kernel: Surface Laptop AMD touchscreen

**Status:** integration scaffolding only until the GitHub Actions build completes and its packages are inspected. **Not a qualified hardware release.**

## Goal and boundaries

Produce native Linux packages for a pinned Linux 6.18.57 kernel containing the existing experimental SL4A controller and Gate5 HID drivers **as kernel-tree modules**, not DKMS modules. Do this on the isolated experiment/in-tree-kernel branch without rewriting the Gate5 driver or changing main.

This is a staging integration prototype, not the final location or accepted architecture for mainline kernel patches.

* The existing Gate5 source C/H files are copied unchanged into drivers/staging/sl4a/.
* An opt-in staging Kconfig and Makefile select sl4a-spi-amd and sl4a-spi-hid as separate modules.
* Native CONFIG_SPI_AMD is disabled in this experimental kernel config to avoid competing controller drivers.
* ACPI auto-loading is **intentionally disabled**: neither experimental module exports a MODULE_DEVICE_TABLE(acpi) alias.
* The native kernel package build does not alter a computer until someone explicitly installs the output .deb files.
* The workflow's default x86_64_defconfig is a **build configuration**, not verified hardware support for a Surface laptop.

## What is implemented

- tools/in-tree/prepare-kernel.sh stages driver sources and registers Kconfig/Makefile; it rejects a second application.
- tools/in-tree/configure-kernel.sh selects both modules, disables the stock controller, and fails closed if module config is not retained.
- tools/in-tree/audit.sh validates the staging transform and confirms the modules do not acquire ACPI auto-load aliases.
- .github/workflows/in-tree-kernel.yml builds Linux 6.18.57 with a pinned archive SHA-256 and exports experimental Debian packages, config, source-commit provenance and SHA256SUMS.

## Get build outputs

Open GitHub Actions on experiment/in-tree-kernel, select **Experimental native SL4A kernel**, and confirm both source-audit and kernel-packages succeeded. Download the sl4a-linux-6.18.57-experimental artifact. The artifacts have short retention; do not treat a queued or failed workflow as proof of a build.

Before installing, inspect the build's kernel.config and README warning file, plus SHA256SUMS.txt. You can inspect package contents without changing your system:

    dpkg-deb --contents ./linux-image-*.deb | grep -E 'sl4a-spi-(amd|hid)\.ko'
    sha256sum -c SHA256SUMS.txt

## Reproduce locally from source

These commands stage sources in a throwaway extracted kernel source tree:

    curl -fL -o linux-6.18.57.tar.xz https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.18.57.tar.xz
    echo '5bd9acdc82ec5efc3790ae840e5aaa40dfde7efff261cf6dde902dc570acf98c  linux-6.18.57.tar.xz' | sha256sum -c -
    tar -xf linux-6.18.57.tar.xz
    bash tools/in-tree/audit.sh
    bash tools/in-tree/prepare-kernel.sh ./linux-6.18.57
    bash tools/in-tree/configure-kernel.sh ./linux-6.18.57 /boot/config-$(uname -r)
    make -C linux-6.18.57 -j2 bindeb-pkg KDEB_PKGVERSION=6.18.57-sl4a1

The optional second argument uses the currently working kernel's configuration as a better starting point than the CI generic defconfig, but it still needs an actual boot test. Do not copy the CI defconfig into a laptop and assume Wi-Fi, NVMe, GPU, keyboard, and power management are all enabled.

## Hardware test gate: NOT automatic

**Do not install an unsigned experimental kernel on a Secure Boot-enabled machine.** First plan a reversible test using an appropriately signed kernel or a deliberately disabled Secure Boot test, a known-good existing boot entry, and external input/recovery access.

Before attempting a real boot, review these blockers:

1. Confirm the exact Surface's MSHW0231 and AMDI0060 IDs and preserve the currently working Gate5 DKMS modules/profile and kernel.
2. Confirm a complete bootable machine-specific kernel config rather than relying on x86_64_defconfig.
3. Ensure the existing sl4a-touch-activate.service is not simultaneously binding a DKMS module during the test. Check module file precedence using modinfo -n sl4a-spi-amd and modinfo -n sl4a-spi-hid; kernel-packaged modules must be selected.
4. Confirm the distribution's GRUB/systemd-boot fallback option and available external keyboard/mouse or remote recovery.
5. The expected initial hardware test is **manual** module loading, not automatic ACPI activation. Load the custom controller first and the HID module second with the known-good Gate5 parameters.
6. Capture loaded module paths, firmware/ACPI identity, IRQ and protocol counters, a real touch event, cold boot, warm reload and s2idle evidence. Stop on unexpected resets or boot failures.

Known-good Gate5 module profile from docs/GATE5-QUALIFICATION.md:

    raw_mode=N raw_input_beta=Y wire_double_opcode=1
    gate3_observe_only=1 skip_std_getfeat=1 std_raw_transition=1
    get_noread=0 getfeat_delay_ms=0 std_liveness_ms=0
    std_liveness_recover=0 wait_reset_kick_ms=0

Keep this configuration experimental and explicitly loaded. No automatic controller bind, kernel boot success, or touch function is claimed by the CI compilation alone.

## Acceptance gates

- [ ] Source audit passes.
- [ ] Linux 6.18.57 kernel packages are produced without compiler or link failures.
- [ ] Both sl4a-spi-amd.ko and sl4a-spi-hid.ko exist in the built package.
- [ ] Package provenance and SHA-256 manifest are checked.
- [ ] Kernel configuration matches the test Surface and recovery is rehearsed.
- [ ] Actual laptop boots the native test kernel with no unexpected driver conflict.
- [ ] Manual modprobe starts Gate5, touch events work, and suspend/resume is retested.
- [ ] Only then consider an opt-in ACPI auto-load follow-up.

## Risk notes

The AMD SPI controller is shared with firmware-access functionality. The current branch deliberately retains explicit module loading rather than introducing automatic controller binding. Current upstream opcode restrictions and GET_FEATURE handling should be integrated and independently validated on a separate change before enabling auto-load. This work does not claim to supersede Syax89's upstream repository or any merged upstream kernel code.
