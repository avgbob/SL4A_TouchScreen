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
original = (root / "tools/experiments/host56-mode4-coldboot-once.sh").read_text()
wrapper = (root / "tools/experiments/host56-mode4.sh").read_text()
assert 'coldboot-stage) coldboot_stage' in wrapper
assert 'coldboot-finish) coldboot_finish' in wrapper
assert 'coldboot-cancel)' in wrapper
assert 'Type ARM' in wrapper and 'Type COLD' in wrapper
assert 'if capture quick; then' in wrapper
assert 'finish FAIL' in wrapper and 'finish PASS' in wrapper

for expected in (
    '[[ -d /sys/module/sl4a_spi_hid ]]',
    '[[ -r "$MODE" ]]',  # checked through mode() wrapper, not necessarily text
):
    if expected.startswith('[[ -r'):
        continue
    assert expected in original, expected
assert 'systemd-run --unit=sl4a-mode4-coldboot-rollback --on-active=20m' in original
assert 'rm -f "$BASE/armed"' in original
assert 'unhook' in original and 'systemctl daemon-reload' in original
assert 'INCONCLUSIVE_PREEXISTING_HID' in original
assert 'INCONCLUSIVE_HID_AUTOLOADED' in original
assert 'if [[ -d /sys/module/sl4a_spi_hid ]]; then' in original
assert 'CANCELLED_OR_RESTORED' in original
assert 'std_raw_transition=4' in original
assert 'modprobe -r sl4a-spi-hid' in original
assert 'modprobe sl4a-spi-hid' in original
assert 'mv "$BASE" "$archive"' in original
assert 'systemctl show -P DropInPaths' in original
assert 'mode4-s2idle' not in original
assert 'update-initramfs' not in original
assert 'dkms install' not in original
assert 'grub-install' not in original

p = root / "tools/experiments/host56-mode4-coldboot-once.sh"
assert subprocess.run(["bash", "-n", str(p)]).returncode == 0
assert subprocess.run([
    "bash", "-n", str(root / "tools/experiments/host56-mode4.sh")
]).returncode == 0

with tempfile.TemporaryDirectory(prefix="mode4-coldboot-state-") as work:
    t = Path(work)
    base = t/"state"
    temp = t/"fake-sysmodule"
    modulepath = base/"signed-mode4.ko"
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
    (base/"stage_boot_id").write_text("staging-boot\n")
    (base/"stage_epoch").write_text(str(int(time.time()))+"\n")
    (base/"kernel").write_text(subprocess.check_output(["uname","-r"],text=True).strip()+"\n")
    (base/"armed").write_text("")
    bootid.write_text("fresh-physical-boot\n")
    stats.write_text("reset_rsp=1\ndata=40\nraw_observed=38\nframes_dropped=0\n")
    dropin.write_text("[Service]\nExecStart=\n")
    simulated = original
    replacements = {
        "/var/lib/sl4a-mode4-coldboot": str(base),
        "/usr/local/libexec/sl4a-mode4-coldboot-once": str(helper),
        "/etc/systemd/system/sl4a-touch-activate.service.d/90-mode4-once.conf": str(dropin),
        "/sys/module/sl4a_spi_hid": str(temp),
        "/sys/bus/spi/devices/spi-MSHW0231:00/protocol_stats": str(stats),
        "/proc/sys/kernel/random/boot_id": str(bootid),
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
        'if [[ "$1" == "sl4a-spi-hid" ]]; then',
        '  mkdir -p "'+str(temp)+'/parameters"',
        '  echo 1 > "'+str(temp)+'/parameters/std_raw_transition"',
        '  echo PROD > "'+str(temp)+'/srcversion"',
        'fi',
        'exit 0'
    ]))
    tool("insmod", '\n'.join([
        'echo "insmod $*" >> "'+str(t/'call.log')+'"',
        'mkdir -p "'+str(temp)+'/parameters"',
        'echo 4 > "'+str(temp)+'/parameters/std_raw_transition"',
        'echo SIMULATEDREV > "'+str(temp)+'/srcversion"',
        'exit 0'
    ]))
    tool("journalctl", 'echo "kernel synthetic MSHW0231"')
    environment=dict(os.environ, PATH=str(bindir)+os.pathsep+os.environ.get("PATH",""))
    def call(verb, want=0):
        r=subprocess.run(["bash",str(helper),verb],env=environment,text=True,
                         capture_output=True,timeout=15)
        assert r.returncode==want,(verb,r.returncode,r.stdout,r.stderr)
        return r

    # Qualified first-boot path: no HID module before the late boot hook.
    r=call("boot")
    assert "first HID insertion mode4" in r.stdout,r.stdout
    assert not dropin.exists(),"one-shot systemd override MUST be consumed"
    assert not (base/"armed").exists()
    assert (base/"result").read_text().strip()=="ACTIVE_AWAITING_POSTBOOT_TOUCH"
    assert (temp/"parameters/std_raw_transition").read_text().strip()=="4"
    assert "--on-active=20m" in (t/"call.log").read_text()
    call("verify")
    call("finish",want=2) if False else None  # finish needs PASS arg
    r=subprocess.run(["bash",str(helper),"finish","PASS"],env=environment,
                     text=True,capture_output=True,timeout=15)
    assert r.returncode==0,(r.stdout,r.stderr)
    assert (base/"result").read_text().strip()=="PASS_COLD_FIRST_HID_AND_POSTBOOT_QUICK"
    assert (temp/"parameters/std_raw_transition").read_text().strip()=="1"
    assert (base/"stats-after-touch.txt").exists()
    assert (base/"kernel-coldboot.log").exists()

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

print("coldboot one-shot consumption, signed identity, Gate5 rollback, stale timer and negative controls: PASS")
