# Rollback Procedure

`sl4a-touch` modules do not auto-load during kernel boot: nothing binds them by
kernel alias. The systemd activation service runs after `multi-user.target` is
reached — at the login prompt, not during early boot and not "after login" — so
if activation hangs you always have a shell to recover with. Recovery from a
failed activation is bounded and deterministic.

## After a failed or hung activation

Keep local console or remote shell access available before every activation.

```sh
sudo modprobe -r sl4a-spi-hid sl4a-spi-amd
sudo reboot
```

If the controller unload fails, force a reboot. The system will boot with the
in-tree `spi-amd` and no SL4A module loaded.

## Uninstalling the package

```sh
sudo ./tools/sl4a-touch.sh uninstall
sudo reboot
```

This removes the package-owned modprobe config and DKMS tree. The git repo is
left intact. After reboot, no SL4A artefact remains active.

## Upgrading between versions

```sh
git checkout <release-tag>
sudo ./tools/sl4a-touch.sh install
sudo reboot
```

The installer detects an existing DKMS registration for the same `PACKAGE_NAME`
and replaces it — building and installing the new version first, then dropping
any other registered version and re-installing once (so a failed build cannot
leave the machine with no registered driver, and two versions still cannot both
build the same module names); it stages the new version and activates
it in the same run, so a reboot is only needed when the profile changes a
load-time parameter (`raw_mode`) or when the MOK key still has to be enrolled for
Secure Boot, and the boot unit repeats the activation after
every boot. `activate` remains available for doing it by hand.

## Kernel updates

DKMS `AUTOINSTALL="yes"` rebuilds both modules for every new kernel. If a
kernel update breaks the build, DKMS leaves the existing modules and logs
the failure. Recover by installing the matching kernel headers and retrying
from the repository checkout.

## Secure Boot and MOK

Running `sudo ./tools/sl4a-touch.sh install` manages the DKMS signing identity
when Secure Boot is enabled.

A usable identity is a **matching pair**:

- `/var/lib/dkms/mok.key` — private key used to sign rebuilt modules;
- `/var/lib/dkms/mok.pub` — X.509 certificate enrolled through MOK Manager.

The installer validates both files, verifies that their public keys match, and
requires the certificate in DER form for `mokutil`. A valid existing pair is
reused by default, so normal driver upgrades do not force a new MOK enrollment.

Interactive installs offer four useful paths when a valid pair exists:

1. reuse the existing pair (recommended);
2. generate a new pair;
3. import another existing private-key/certificate pair;
4. abort.

When no pair exists, the installer first tries `dkms generate_mok`, validates
what DKMS produced, and falls back to an OpenSSL-generated RSA key pair if
needed.

When existing MOK material is incomplete, invalid, or mismatched, the installer
does **not** silently treat a lone certificate as usable. Interactive installs
offer repair or import; non-interactive installs stop. To deliberately replace
existing material from a scripted install, use:

```sh
sudo ./tools/sl4a-touch.sh install --rotate-mok
```

Before a generated or imported pair replaces anything already in the standard
DKMS paths, the installer copies the previous material into a root-only backup
directory:

```text
/var/lib/dkms/sl4a-mok-backup-<timestamp>-<pid>/
```

The old certificate remains enrolled in firmware unless you explicitly remove
it with your platform's MOK tooling; rotation changes which key DKMS will use
for future builds, not the firmware trust database by itself.

### Enroll the active DKMS MOK certificate manually

```sh
sudo mokutil --import /var/lib/dkms/mok.pub
sudo reboot
```

Set a temporary one-time password when prompted. At the MOK Manager screen,
select `Enroll MOK`, continue, confirm, enter that password, and reboot.

Until the active certificate is enrolled, the installer deliberately skips
immediate SL4A driver activation because Secure Boot would reject the newly
signed modules. The installed boot service retries activation after the
enrollment reboot.

### Verify the active signing identity

```sh
mokutil --sb-state
mokutil --test-key /var/lib/dkms/mok.pub

sudo openssl pkey \
  -in /var/lib/dkms/mok.key \
  -pubout -outform DER 2>/dev/null | openssl dgst -sha256

sudo openssl x509 \
  -in /var/lib/dkms/mok.pub -inform DER \
  -pubkey -noout 2>/dev/null |
  openssl pkey -pubin -outform DER 2>/dev/null |
  openssl dgst -sha256
```

The two SHA-256 values should match. The installer performs the same key-pair
consistency check automatically before it allows the DKMS build to continue.

Secure Boot signing/enrollment support is implemented, but the complete
install → MOK enrollment → reboot → automatic activation path remains a
separate hardware-qualification item in the compatibility matrix.
