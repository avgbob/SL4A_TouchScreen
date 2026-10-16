# Alternative drivers/spi + drivers/hid kernel layout

**Experimental.** This is a source-staging prototype, not a kernel
mainline submission. It does not touch the installed kernel, DKMS,
MOK or machine bootloader.

Use `stage-in-tree.sh` to copy exact **PR #87**
`18f0fe79623e6de4fdf1ae493f82a7048397386a` sources by default, including its controller,
HID transport and CapImg tracker, to a separate *clean* Git Linux
kernel checkout:

| Destination | Config | Module |
| --- | --- | --- |
| `drivers/spi/sl4a/` | `CONFIG_SL4A_AMD_SPI=m` | `sl4a-spi-amd.ko` |
| `drivers/hid/sl4a/` | `CONFIG_SL4A_HID_SPI=m` | `sl4a-spi-hid.ko` |

The `tools/in-tree/prepare-kernel.sh` **separate staging layout**
under `drivers/staging/sl4a` is the one used for the full
6.18.57 Debian CI build. The SPI/HID layout is tested
against a disposable fixture but is not part of that kernel package.

## Safe, source-only preparation

```bash
git switch experiment/in-tree-kernel
bash tools/in-tree/source-selector-test.sh
bash tools/kernel_integration/selftest.sh
# On a separate, clean, FULL Linux Git source checkout:
KERNEL_SRC="$HOME/src/linux-sl4a-experiment"
bash tools/kernel_integration/stage-in-tree.sh --check "$KERNEL_SRC"
bash tools/kernel_integration/stage-in-tree.sh --apply "$KERNEL_SRC"
git -C "$KERNEL_SRC" diff --check
```

The staging code refuses an already-modified or already-staged
kernel tree, does not export automatic ACPI module aliases, and
does not perform actual module loading, installation, power
management or firmware operations. Staging records `SOURCE-COMMIT`
and `SOURCE-FLAVOR` next to the module source. The explicit
`SL4A_IN_TREE_SOURCE=legacy-gate5` variant copies the untouched
old `driver/` files for *unqualified* comparison; never combine
the two variants to claim PR87 reproducibility.

After inspecting the staged code, building an experimental kernel
with those Kconfig modules still requires complete kernel config,
supported compiler, bootloader fallback, Secure Boot signing and
a separate on-device acceptance campaign. In particular, the HID
module copies `spi-amd.h` into its own subtree for compilation:
that is a temporary architecture compromise, not an upstream-ready
separation of interfaces.

See [full pinned kernel guide](../../docs/IN-TREE-KERNEL.md)
for provenance, safety limits and the main GitHub Actions build.
