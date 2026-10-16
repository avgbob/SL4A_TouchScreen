#!/usr/bin/env python3
"""Fail-closed mock physical-cold-boot state machine; never touches real /sys."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
original = (root / "tools/experiments/host56-pr87-coldboot-once.sh").read_text()
wrapper = (root / "tools/experiments/host56-pr87.sh").read_text()
assert 'coldboot-stage) run_coldboot_stage' in wrapper
assert 'coldboot-finish) run_coldboot_finish' in wrapper
assert 'coldboot-cancel)' in wrapper
assert 'coldboot-diagnose)' in wrapper
assert 'diagnose) diagnose' in original
assert 'INCONCLUSIVE_KERNEL_MISMATCH' in original
assert 'INCONCLUSIVE_STAGING_EXPIRED' in original
assert 'INCONCLUSIVE_BAD_STAGE_EPOCH' in original
assert 'boot default symlink target=' in original
assert 'archive="$BASE-archive-$(date -u +%Y%m%dT%H%M%SZ)-$"' in original
assert 'Type ARM_PR87' in wrapper and 'Type COLD_PR87' in wrapper
assert 'if capture "coldboot" quick; then' in wrapper
assert 'finish FAIL' in wrapper and 'finish PASS' in wrapper

for expected in (
    '[[ -d /sys/module/sl4a_spi_hid ]]',
    '[[ -r "$MODE" ]]',  # checked through mode() wrapper, not necessarily text
):
    if expected.startswith('[[ -r'):
        continue
    assert expected in original, expected
assert 'systemd-run --unit=sl4a-pr87-coldboot-rollback --on-active=20m' in original
assert 'rm -f "$BASE/armed"' in original
assert 'unhook' in original and 'systemctl daemon-reload' in original
assert 'INCONCLUSIVE_PREEXISTING_HID' in original
assert 'INCONCLUSIVE_HID_AUTOLOADED' in original
assert 'if [[ -d /sys/module/sl4a_spi_hid ]]; then' in original
assert 'CANCELLED_OR_RESTORED' in original
# Regression for the physical 2026-10-16 abort: merely loading the
# Gate5 HID module reports mode1 WITHOUT binding the AMD controller.
# Cold-boot recovery must load AMD FIRST and inspect both bindings.
fallback_body = original.split('fallback() {',1)[1].split('\n}',1)[0]
assert fallback_body.index('modprobe sl4a-spi-amd') < fallback_body.index('modprobe sl4a-spi-hid')
assert 'AMD_binding=' in fallback_body and 'HID_binding=' in fallback_body
assert 'touch input NOT yet verified' in fallback_body
assert 'controller_driver" != sl4a_spi_amd_v2_multi' in fallback_body
assert 'touch_driver" != sl4a_spi_hid' in fallback_body
# Do not stage from the exact broken state seen on kernel 7.0.0-34:
# modprobe exposes mode1 but controller and touchscreen are unbound.
stage_body = original.split('\nstage() {',1)[1].split('\nboot() {',1)[0]
assert 'controller_binding" != sl4a_spi_amd_v2_multi' in stage_body
assert 'touch_binding" != sl4a_spi_hid' in stage_body
assert '! -r "$STATS"' in stage_body
assert 'REFUSE staging: working Gate5 needs BOTH driver bindings' in stage_body
assert stage_body.index('REFUSE staging: working Gate5 needs BOTH driver bindings') < stage_body.index('install -m 0755 "$0" "$HELPER"')
assert 'std_raw_transition=1' in original
assert 'modprobe -r sl4a-spi-hid' in original
assert 'modprobe sl4a-spi-hid' in original
assert 'mv "$BASE" "$archive"' in original
assert 'systemctl show -P DropInPaths' in original
assert 'pr87-s2idle' not in original
assert 'update-initramfs' not in original
assert 'dkms install' not in original
assert 'grub-install' not in original

p = root / "tools/experiments/host56-pr87-coldboot-once.sh"
assert subprocess.run(["bash", "-n", str(p)]).returncode == 0
assert subprocess.run([
    "bash", "-n", str(root / "tools/experiments/host56-pr87.sh")
]).returncode == 0

with tempfile.TemporaryDirectory(prefix="pr87-coldboot-state-") as work:
    t = Path(work)
    base = t/"state"
    temp = t/"fake-sysmodule"
    modulepath = base/"signed-pr87.ko"
    dropin = t/"override.conf"
    bootid = t/"boot-id"
    stats = t/"stats.txt"
    helper = t/"helper.sh"
    bindir = t/"bin"
    bindir.mkdir()
    base.mkdir()
    modulepath.write_bytes(b"synthetic signed module binary")
    (base/"module_sha").write_text(hashlib.sha256(modulepath.read_bytes()).hexdigest()+"\n")
    (base/"srcversion").write_text("SIMULATEDREV\n")
    (base/"source_sha").write_text("18f0fe79623e6de4fdf1ae493f82a7048397386a\n")
    (base/"production_srcversion").write_text("PROD\n")
    (base/"stage_boot_id").write_text("staging-boot\n")
    (base/"stage_epoch").write_text(str(int(time.time()))+"\n")
    (base/"kernel").write_text(subprocess.check_output(["uname","-r"],text=True).strip()+"\n")
    (base/"armed").write_text("")
    bootid.write_text("fresh-physical-boot\n")
    stats.write_text("reset_rsp=1\ndata=40\nraw_observed=38\nframes_dropped=0\n")
    dropin.write_text("[Service]\nExecStart=\n")
    simulated = original
    fake_controller = t/"platform/AMDI0060:00"
    fake_touch = t/"acpi/MSHW0231:00/physical_node"
    drivers = t/"drivers"
    (drivers/"sl4a_spi_amd_v2_multi").mkdir(parents=True)
    (drivers/"sl4a_spi_hid").mkdir()
    fake_controller.mkdir(parents=True)
    fake_touch.mkdir(parents=True)
    replacements = {
        "/var/lib/sl4a-pr87-coldboot": str(base),
        "/usr/local/libexec/sl4a-pr87-coldboot-once": str(helper),
        "/etc/systemd/system/sl4a-touch-activate.service.d/90-pr87-once.conf": str(dropin),
        "/sys/module/sl4a_spi_hid": str(temp),
        "/sys/bus/spi/devices/spi-MSHW0231:00/protocol_stats": str(stats),
        "/proc/sys/kernel/random/boot_id": str(bootid),
        "/sys/bus/platform/devices/AMDI0060:": str(t/"platform/AMDI0060:"),
        "/sys/bus/acpi/devices/MSHW0231:00/physical_node/driver": str(fake_touch/"driver"),
        "require_root() { (( EUID == 0 ))": "require_root() { ( true )",
        "sleep 3": "sleep 0.001",
    }
    for old,new in replacements.items():
        assert old in simulated, old
        simulated=simulated.replace(old,new)
    helper.write_text(simulated)
    helper.chmod(0o755)
    assert subprocess.run(["bash","-n",str(helper)]).returncode == 0

    def tool(name, content):
        x=bindir/name
        x.write_text("#!/usr/bin/env bash\nset -eu\n"+content+"\n")
        x.chmod(0o755)
    tool("systemctl", 'echo "systemctl $*" >> "'+str(t/'call.log')+'"\nexit 0')
    tool("systemd-run", 'echo "systemd-run $*" >> "'+str(t/'call.log')+'"\nexit 0')
    tool("modprobe", '\n'.join([
        'echo "modprobe $*" >> "'+str(t/'call.log')+'"',
        'if [[ "$1" == "-r" ]]; then rm -rf "'+str(temp)+'"; exit 0; fi',
        'if [[ "$1" == "sl4a-spi-amd" ]]; then',
        '  ln -sfn "'+str(drivers/'sl4a_spi_amd_v2_multi')+'" "'+
              str(fake_controller/'driver')+'"',
        'fi',
        'if [[ "$1" == "sl4a-spi-hid" ]]; then',
        '  mkdir -p "'+str(temp)+'/parameters"',
        '  echo 1 > "'+str(temp)+'/parameters/std_raw_transition"',
        '  echo N > "'+str(temp)+'/parameters/raw_input_beta"',
        '  echo N > "'+str(temp)+'/parameters/raw_mode"',
        '  echo PROD > "'+str(temp)+'/srcversion"',
        '  ln -sfn "'+str(drivers/'sl4a_spi_hid')+'" "'+str(fake_touch/'driver')+'"',
        'fi',
        'exit 0'
    ]))
    tool("insmod", '\n'.join([
        'echo "insmod $*" >> "'+str(t/'call.log')+'"',
        'mkdir -p "'+str(temp)+'/parameters"',
        'echo 1 > "'+str(temp)+'/parameters/std_raw_transition"',
        'echo Y > "'+str(temp)+'/parameters/raw_input_beta"',
        'echo N > "'+str(temp)+'/parameters/raw_mode"',
        'echo SIMULATEDREV > "'+str(temp)+'/srcversion"',
        'ln -sfn "'+str(drivers/'sl4a_spi_hid')+'" "'+str(fake_touch/'driver')+'"',
        'exit 0'
    ]))
    tool("journalctl", 'if [[ -f "'+str(t/'earlier-hid')+'" ]]; then '+
         'echo "kernel sl4a_spi_hid probe begin"; '+
         'else echo "kernel synthetic MSHW0231"; fi')
    environment=dict(os.environ, PATH=str(bindir)+os.pathsep+os.environ.get("PATH",""))
    def call(verb, want=0):
        r=subprocess.run(["bash",str(helper),verb],env=environment,text=True,
                         capture_output=True,timeout=15)
        assert r.returncode==want,(verb,r.returncode,r.stdout,r.stderr)
        return r

    # Qualified first-boot path: no HID module before the late boot hook.
    r=call("boot")
    assert "first HID insertion exact PR87" in r.stdout,r.stdout
    assert not dropin.exists(),"one-shot systemd override MUST be consumed"
    assert not (base/"armed").exists()
    assert (base/"result").read_text().strip()=="ACTIVE_AWAITING_POSTBOOT_TOUCH"
    assert (temp/"parameters/std_raw_transition").read_text().strip()=="1"
    assert (temp/"parameters/raw_input_beta").read_text().strip()=="Y"
    assert (temp/"srcversion").read_text().strip()=="SIMULATEDREV"
    assert "--on-active=20m" in (t/"call.log").read_text()
    call("verify")
    r=subprocess.run(["bash",str(helper),"finish","PASS"],env=environment,
                     text=True,capture_output=True,timeout=15)
    assert r.returncode==0,(r.stdout,r.stderr)
    assert (base/"result").read_text().strip()=="PASS_COLD_FIRST_HID_AND_POSTBOOT_QUICK"
    assert (temp/"parameters/std_raw_transition").read_text().strip()=="1"
    assert (temp/"srcversion").read_text().strip()=="PROD"
    assert (base/"stats-after-touch.txt").exists()
    assert (base/"kernel-coldboot.log").exists()
    assert (base/"SHA256SUMS.txt").exists()
    check = subprocess.run(["sha256sum", "-c", "SHA256SUMS.txt"],
                           cwd=base,text=True,capture_output=True)
    assert check.returncode == 0, check.stdout + check.stderr

    # Next reboot timer/stale callback MUST NOT unload a different boot.
    bootid.write_text("later-normal-boot\n")
    (t/"call.log").write_text("")
    call("rollback")
    assert "modprobe -r" not in (t/"call.log").read_text(), "stale timer touched later boot"

    # Negative control: first HID instance was already loaded at late service.
    (base/"armed").write_text("")
    (base/"stage_boot_id").write_text("before-test2\n")
    (base/"result").write_text("ARMED_NOT_TESTED\n")
    bootid.write_text("test2-boot\n")
    dropin.write_text("temporary override")
    (temp/"parameters/std_raw_transition").write_text("1\n")
    (t/"call.log").write_text("")
    call("boot")
    assert (base/"result").read_text().strip()=="INCONCLUSIVE_PREEXISTING_HID"
    assert not dropin.exists()
    assert "insmod" not in (t/"call.log").read_text()
    assert "modprobe -r" not in (t/"call.log").read_text()

    # Negative control: changing the signed module bytes refuses insertion.
    (base/"armed").write_text("")
    (base/"stage_boot_id").write_text("before-test3\n")
    (base/"result").write_text("ARMED_NOT_TESTED\n")
    bootid.write_text("test3-boot\n")
    dropin.write_text("temporary override")
    import shutil
    shutil.rmtree(temp)
    modulepath.write_bytes(b"tampered module")
    (t/"call.log").write_text("")
    call("boot",want=1)
    assert not dropin.exists()
    assert "insmod" not in (t/"call.log").read_text()

    # A probe earlier in the SAME boot invalidates first-HID qualification,
    # even if that earlier module was unloaded before the late service runs.
    (base/"armed").write_text("")
    (base/"stage_boot_id").write_text("before-test4\n")
    (base/"result").write_text("ARMED_NOT_TESTED\n")
    bootid.write_text("test4-boot\n")
    if temp.exists():
        shutil.rmtree(temp)  # a fresh physical boot cannot retain old modules
    dropin.write_text("temporary override")
    modulepath.write_bytes(b"synthetic signed module binary")
    (t/"earlier-hid").write_text("prior boot probe")
    (t/"call.log").write_text("")
    call("boot")
    assert (base/"result").read_text().strip() == "INCONCLUSIVE_EARLIER_HID_PROBE"
    assert not dropin.exists()
    assert "insmod" not in (t/"call.log").read_text()
    (t/"earlier-hid").unlink()

    # Independent timer firing before operator confirmation must restore
    # Gate5 and mark the trial INCONCLUSIVE rather than qualify it.
    (base/"armed").write_text("")
    (base/"stage_boot_id").write_text("before-test5\n")
    (base/"result").write_text("ARMED_NOT_TESTED\n")
    bootid.write_text("test5-boot\n")
    if temp.exists():
        shutil.rmtree(temp)
    dropin.write_text("temporary override")
    (t/"call.log").write_text("")
    call("boot")
    assert (base/"result").read_text().strip() == "ACTIVE_AWAITING_POSTBOOT_TOUCH"
    call("rollback")
    assert (temp/"parameters/std_raw_transition").read_text().strip() == "1"
    assert (temp/"srcversion").read_text().strip() == "PROD"
    assert (base/"result").read_text().strip() == "INCONCLUSIVE_WATCHDOG_ROLLBACK"

    # Never unload production Gate5 even when it shares mode=1 with PR87.
    (t/"call.log").write_text("")
    call("rollback")
    assert "modprobe -r" not in (t/"call.log").read_text(), (
        "source-mismatched Gate5 was unloaded merely because mode=1")
    # Regression for 2026-10-16 physical first attempt:
    # 2 minutes after staging, the boot service got a kernel mismatch
    # (previous script mislabeled it generic INCOMPLETE). No module insert.
    import shutil
    (base/"armed").write_text("")
    (base/"stage_boot_id").write_text("previous-boot-6\n")
    (base/"result").write_text("ARMED_NOT_TESTED\n")
    (base/"kernel").write_text("kernel-staged-but-not-booted\n")
    (base/"stage_epoch").write_text(str(int(time.time()) - 120) + "\n")
    bootid.write_text("actual-boot-6\n")
    if temp.exists():
        shutil.rmtree(temp)
    dropin.write_text("temporary override")
    (t/"call.log").write_text("")
    r=call("boot",want=1)
    assert (base/"result").read_text().strip() == "INCONCLUSIVE_KERNEL_MISMATCH",r.stdout
    assert "KERNEL_MISMATCH staged=kernel-staged-but-not-booted" in r.stdout
    assert "module not inserted" in r.stdout
    assert not dropin.exists()
    assert "insmod " not in (t/"call.log").read_text()
    assert "systemd-run" not in (t/"call.log").read_text()
    assert (temp/"parameters/std_raw_transition").read_text().strip() == "1"
    # Diagnosis of retained failed evidence is read-only and actionable.
    r=call("diagnose")
    assert "staged-but-not-booted" in r.stdout and "VERDICT: kernel changed" in r.stdout

    # Genuine elapsed staging timeout has a DIFFERENT status and never
    # reaches the experimental module or recovery watchdog.
    (base/"armed").write_text("")
    (base/"stage_boot_id").write_text("previous-boot-7\n")
    (base/"result").write_text("ARMED_NOT_TESTED\n")
    (base/"kernel").write_text(subprocess.check_output(["uname","-r"],text=True).strip()+"\n")
    (base/"stage_epoch").write_text(str(int(time.time()) - 90000) + "\n")
    bootid.write_text("actual-boot-7\n")
    shutil.rmtree(temp)
    dropin.write_text("temporary override")
    (t/"call.log").write_text("")
    r=call("boot",want=1)
    assert (base/"result").read_text().strip() == "INCONCLUSIVE_STAGING_EXPIRED"
    assert "STAGE_AGE_SECONDS=" in r.stdout
    assert "insmod " not in (t/"call.log").read_text()
    assert "systemd-run" not in (t/"call.log").read_text()
    assert (temp/"parameters/std_raw_transition").read_text().strip() == "1"

print("PR87 exact coldboot consumption, signed identity, Gate5 rollback, stale timer: PASS")
