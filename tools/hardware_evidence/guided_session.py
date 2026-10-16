#!/usr/bin/env python3
"""Audibly guided physical-touch capture with synced markers and read-only evidence.

Runs cue audio as the desktop user; grants root only to the established
read-only evtest/journal collector. No install, reload, or power operations.
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
import wave

# Also import correctly when host CI loads this module with importlib.spec.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_input_gate import GestureGate

ROOT = Path(__file__).resolve().parents[2]
COLLECTOR = ROOT / "tools/hardware_evidence/run_blinded_session.sh"
STATS = Path("/sys/bus/spi/devices/spi-MSHW0231:00/protocol_stats")
MODE = Path("/sys/module/sl4a_spi_hid/parameters/std_raw_transition")
PROTOCOLS = {
    "single": [
        ("one", "Move ONE finger slowly across the screen", 8),
        ("lift", "Lift finger; hold hands off glass", 5),
        ("repeat", "Move one finger again, then lift", 8),
    ],
    "quick": [
        ("one", "Move one finger slowly across the screen, then lift it.", 6),
        ("pinch", "Place two fingers far apart. Move them together without lifting.", 8),
        ("expand", "Keep the same two fingers touching. Move them far apart.", 8),
        ("lift", "Lift both fingers off the screen completely.", 5),
    ],
    "pinch": [
        ("far", "Place two fingers far apart on the screen and hold.", 6),
        ("close", "Move the same two fingers closer together without lifting.", 8),
        ("hold", "Keep both fingers on the glass and hold them still.", 6),
        ("expand", "Move the same two fingers apart without lifting.", 8),
        ("lift", "Lift both fingers completely off the glass.", 5),
    ],
    "contacts": [
        ("one", "Put one finger on the screen and hold it until I tell you to lift.", 6),
        ("two", "Put two fingers on the screen and hold them until I tell you to lift.", 6),
        ("three", "Put three fingers on the screen and hold them until I tell you to lift.", 6),
        ("four", "Put four fingers on the screen and hold them until I tell you to lift.", 6),
        ("five", "Put five fingers on the screen and hold them until I tell you to lift.", 6),
        ("one-lift", "Place two fingers down. Listen for instructions before lifting either one.", 9),
        ("recontact", "Touch with one finger. I will tell you when to lift and touch again.", 6),
    ],
    "stylus": [
        ("hover", "Hover pen just ABOVE glass", 7),
        ("pen", "Draw with pen in contact", 8),
        ("lift", "Lift pen, leave screen untouched", 5),
    ],
}
# One-audio-preflight, one evtest bundle, one timestamped sequence for the
# first full physical qualification on a new source SHA. Subsequent lifecycle
# iterations can use the short "quick" protocol without rerunning everything.
PROTOCOLS["full"] = [
    (f"{protocol}-{label}", prompt, seconds)
    for protocol in ("quick", "pinch", "contacts")
    for label, prompt, seconds in PROTOCOLS[protocol]
]

# Output is private by default: evtest can capture other unintended input.
def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")

def file_sha(path):
    with open(path, "rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()

def txt(path):
    try:
        return path.read_text().strip()
    except OSError:
        return "UNAVAILABLE"

def probe(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5,
                              check=False).stdout.strip() or "UNAVAILABLE"
    except (OSError, subprocess.TimeoutExpired):
        return "UNAVAILABLE"

def wav_tone(path, notes):
    """A real PCM WAV; no terminal-bell-only or network audio dependency."""
    rate = 32000
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        for freq, duration in notes:
            samples = int(rate * duration)
            frames = bytearray()
            for i in range(samples):
                edge = min(1, i / 280, (samples - i) / 280)
                value = int(9500 * edge * math.sin(2 * math.pi * freq * i / rate))
                frames.extend(struct.pack("<h", value))
            out.writeframes(frames)

class Audio:
    """Real spoken instructions; the old tone-only runner was insufficient."""

    def __init__(self, folder, dry=False):
        self.dry = dry
        self.folder = folder
        self.player = next((p for p in ("paplay", "pw-play", "aplay")
                            if shutil.which(p)), None)
        self.tts = next((p for p in ("espeak-ng", "espeak") if shutil.which(p)),
                        None)
        self.sounds = {}
        self.spoken = {}
        for tag, notes in {
            "pre": [(520, .17), (650, .17)],
            "tick": [(680, .12)],
            "go": [(950, .18), (1250, .23)],
            "stop": [(520, .24)],
            "end": [(1100, .18), (780, .24), (540, .42)],
        }.items():
            path = folder / (tag + ".wav")
            wav_tone(path, notes)
            self.sounds[tag] = path

    def play_file(self, path):
        if self.dry:
            print("[DEMO AUDIO]", path, flush=True)
            return
        if not self.player:
            raise RuntimeError("No working audio player found (paplay/pw-play/aplay)")
        p = subprocess.run([self.player, str(path)], capture_output=True,
                           text=True, timeout=35)
        if p.returncode:
            raise RuntimeError("Audio playback failed: " + p.stderr.strip())

    def play(self, name):
        self.play_file(self.sounds[name])

    def speak(self, words):
        """Generate WAV speech offline, then play it through verified audio."""
        print("VOICE:", words, flush=True)
        if self.dry:
            return
        if not self.tts:
            raise RuntimeError("Spoken instructions require espeak-ng. "
                               "Install: sudo apt install espeak-ng")
        if words not in self.spoken:
            path = self.folder / ("voice-" + str(len(self.spoken)) + ".wav")
            p = subprocess.run([self.tts, "-v", "en-us", "-s", "145",
                                "-w", str(path), words], capture_output=True,
                               text=True, timeout=20)
            if p.returncode or not path.is_file() or path.stat().st_size < 44:
                raise RuntimeError("Voice synthesis failed: " + p.stderr.strip())
            self.spoken[words] = path
        self.play_file(self.spoken[words])

    def preflight(self):
        print("VOICE PREFLIGHT: you must HEAR and understand the spoken message.",
              flush=True)
        if not self.dry and not self.tts:
            raise RuntimeError("Install speech synthesis first: "
                               "sudo apt install espeak-ng")
        self.play("pre")
        self.speak("Touchscreen test. I will speak every instruction, "
                   "and I will wait until the computer detects each action.")
        if self.dry:
            return
        if not sys.stdin.isatty():
            raise RuntimeError("Physical tests need a terminal for voice confirmation")
        answer = input("Did you HEAR and UNDERSTAND the spoken words? "
                       "Type YES to proceed: ").strip()
        if answer.upper() != "YES":
            raise RuntimeError("Speech was not confirmed. No test started.")

def safe_sleep(seconds, process=None):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if process and process.poll() is not None:
            raise RuntimeError("Evidence collector exited while cues were running")
        time.sleep(min(.15, end - time.monotonic()))

def mark(fp, event, detail=""):
    line = f"{stamp()}\t{time.monotonic():.6f}\t{event}\t{detail}\n"
    fp.write(line)
    fp.flush()

def countdown(audio, marks, seconds, process=None):
    print(f"\nCOUNTDOWN: {seconds} seconds until recording gestures.", flush=True)
    for remaining in range(seconds, 0, -1):
        print(f"  {remaining} ...", flush=True)
        mark(marks, "countdown", str(remaining))
        audio.play("tick")
        safe_sleep(.78, process)
    audio.play("go")
    mark(marks, "countdown-go")

def guide(audio, marks, phases, process=None):
    for label, prompt, secs in phases:
        print(f"\n>>> {label.upper()}: {prompt} ({secs}s) <<<", flush=True)
        audio.play("go")
        mark(marks, "phase-begin", f"{label}: {prompt}")
        safe_sleep(max(0, secs - 3), process)
        for left in (3, 2, 1):
            print(f"  {label}: {left}...", flush=True)
            mark(marks, "phase-countdown", f"{label}:{left}")
            audio.play("tick")
            safe_sleep(.78, process)
        mark(marks, "phase-end", label)
        audio.play("stop")
    print("\n>>> HANDS OFF — gesture script finished <<<", flush=True)
    audio.play("end")
    mark(marks, "gesture-script-end")


def live_capture(audio, marks, phases, events, evidence_proc):
    """Never mark a gesture PASS based on time alone.

    The monitor reports real kernel input_event frames. A phase advances
    only when GestureGate verifies its required count, movement and/or lift.
    """
    context = {}
    results = []
    for number, (label, prompt, _old_seconds) in enumerate(phases, 1):
        passed = False
        for attempt in range(1, 4):
            gate = GestureGate(label, context)
            audio.speak(f"Test {number} of {len(phases)}. {prompt}")
            mark(marks, "phase-instruction", f"{label};attempt={attempt};{prompt}")
            # Spoken countdown is not an arbitrary test deadline.
            for n in (5, 4, 3, 2, 1):
                audio.speak(str(n))
            audio.speak("Go.")
            mark(marks, "phase-begin", f"{label};attempt={attempt}")
            deadline = time.monotonic() + 22
            while time.monotonic() < deadline:
                if evidence_proc.poll() is not None:
                    raise RuntimeError("Evidence collector exited during live test")
                try:
                    frame = events.get(timeout=.25)
                except queue.Empty:
                    continue
                if frame.get("kind") == "error":
                    raise RuntimeError("live input monitor failed: " +
                                       str(frame.get("error")))
                if frame.get("kind") != "frame":
                    continue
                # Reject frames emitted while we were still saying the prompt.
                if frame.get("monotonic", 0) < deadline - 22:
                    continue
                success, speech = gate.feed(frame)
                for announcement in speech:
                    mark(marks, "gesture-progress", f"{label}:{announcement}")
                    audio.speak(announcement)
                if success:
                    mark(marks, "phase-pass",
                         f"{label};attempt={attempt};last_frame={frame.get('seq')}")
                    audio.play("go")
                    audio.speak("Detected. Test passed.")
                    results.append((label, "PASS", attempt))
                    passed = True
                    break
            if passed:
                break
            mark(marks, "phase-retry", f"{label};attempt={attempt}")
            if attempt < 3:
                audio.speak("I did not detect that gesture correctly. "
                            "Lift your fingers and try again. "
                            "I will repeat the instruction.")
            else:
                audio.speak("Test could not be verified. "
                            "The recording will stop without marking a pass.")
        if not passed:
            results.append((label, "INCONCLUSIVE", 3))
            mark(marks, "phase-inconclusive", label)
            raise RuntimeError(f"Gesture {label} did not meet the event gate; "
                               "evidence retained as INCONCLUSIVE")
    audio.speak("All gestures were detected. The recording is complete.")
    audio.play("end")
    mark(marks, "gesture-script-end", "all live gesture gates passed")
    return results


def read_live_events(proc, q, destination):
    """Drain privileged monitor stdout, keeping raw JSONL proof."""
    try:
        with destination.open("w") as capture:
            for line in proc.stdout:
                capture.write(line)
                capture.flush()
                try:
                    packet = json.loads(line)
                except json.JSONDecodeError:
                    continue
                try:
                    q.put(packet, timeout=1)
                except queue.Full:
                    q.put({"kind": "error", "error": "live monitor event queue overflow"})
                    return
    finally:
        try:
            q.put_nowait({"kind": "error", "error": "live evdev monitor ended"})
        except queue.Full:
            pass


def selected_event_node(path):
    """Use the collector's own discovered eventN, not a hardcoded node."""
    start = time.monotonic()
    while time.monotonic() - start < 25:
        p = subprocess.run(["sudo", "-n", "sed", "-n",
                            "s/^device=\\(\\/dev\\/input\\/event[0-9]*\\)$/\\1/p",
                            str(path)], text=True, capture_output=True,
                           timeout=5)
        match = re.search(r"/dev/input/event[0-9]+", p.stdout)
        if match:
            return match.group(0)
        time.sleep(.3)
    raise RuntimeError("Collector did not identify an input event node")


def stop_capture(proc, output):
    """Request orderly collector close so manifests and checksums get written."""
    marker = output / "trace/sl4a-guided-complete.flag"
    subprocess.run(["sudo", "-n", "touch", str(marker)], check=True)
    return proc.wait(timeout=25)


def copy_artifacts(output, copies):
    operator = output / "operator"
    for source, dest in copies:
        subprocess.run(["sudo", "-n", "cp", str(source),
                        str(operator / dest)], check=True)
    subprocess.run(["sudo", "-n", "chown", "-R",
                    f"{os.getuid()}:{os.getgid()}", str(output)],
                   check=True)


def read_stats(text):
    """Parse the driver's monotone counters; missing data cannot mean zero."""
    pairs = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if value.isdecimal():
            pairs[key] = int(value)
    for key in ("reset_rsp", "frames_dropped", "data", "raw_observed"):
        if key not in pairs:
            raise RuntimeError(f"missing protocol counter: {key}")
    return pairs


def verify_run_integrity(expected_mode, source):
    """Fail closed when current source/build cannot be tied to the live driver.

    No kernel API supplies an unmodified, post-load .ko to hash. The
    independent live srcversion and build-id (if exposed), module signing
    identity, clean Git source and signed file hash make provenance explicit.
    """
    mode = txt(MODE)
    if mode != expected_mode:
        raise RuntimeError(
            f"loaded transition mode {mode}, expected {expected_mode}")
    if not source.is_file():
        raise RuntimeError("locally built signed module missing: " + str(source))
    dirty = subprocess.run(
        ["git", "-C", str(ROOT), "status", "--porcelain",
         "--untracked-files=no"], capture_output=True, text=True)
    if dirty.returncode or dirty.stdout.strip():
        raise RuntimeError("source worktree is dirty or unreadable: " +
                           (dirty.stdout.strip() or dirty.stderr.strip()))
    revision = probe(["git", "-C", str(ROOT), "rev-parse", "HEAD"])
    if len(revision) != 40:
        raise RuntimeError("could not identify full source commit SHA")
    expected_version = probe(["modinfo", "-F", "srcversion", str(source)])
    live_version = txt(Path("/sys/module/sl4a_spi_hid/srcversion"))
    if (not expected_version or expected_version == "UNAVAILABLE" or
            expected_version != live_version):
        raise RuntimeError("LIVE srcversion does not match built module: " +
                           str(live_version) + " vs " + str(expected_version))
    expected_signer = probe(["modinfo", "-F", "signer", str(source)])
    if not expected_signer or expected_signer == "UNAVAILABLE":
        raise RuntimeError("built module is not signed")
    expected_vermagic = probe(["modinfo", "-F", "vermagic", str(source)])
    kernel = probe(["uname", "-r"])
    if not expected_vermagic.startswith(kernel + " "):
        raise RuntimeError("compiled module vermagic does not match running kernel")
    return {
        "source_commit": revision,
        "live_mode_verified": mode,
        "module_sha256": file_sha(source),
        "module_srcversion_verified": expected_version,
        "module_signer": expected_signer,
        "module_vermagic": expected_vermagic,
        "working_tree_clean_tracked": "YES",
    }


def verify_counters(before, after, source):
    a, b = read_stats(before), read_stats(after)
    for key in ("reset_rsp", "frames_dropped"):
        delta = b[key] - a[key]
        if delta != 0:
            raise RuntimeError(f"{key} changed during gesture test ({delta:+d})")
    if source == "beta":
        if b["raw_observed"] <= a["raw_observed"]:
            raise RuntimeError("no new CapImg frames received in MT gesture test")
        if b["data"] <= a["data"]:
            raise RuntimeError("no new DATA frames received in MT gesture test")
    return {f"delta_{name}": b[name] - a[name]
            for name in ("reset_rsp", "frames_dropped", "data", "raw_observed")}


def finalize_manifest(output):
    """Hash every finished artifact including the after-session metadata."""
    manifest = output / "SHA256SUMS.txt"
    with manifest.open("w") as fp:
        for path in sorted(output.rglob("*")):
            if path == manifest or not path.is_file() or path.is_symlink():
                continue
            fp.write(f"{file_sha(path)}  {path.relative_to(output)}\n")
    # Verify the completed manifest, not merely its successful write.
    p = subprocess.run(["sha256sum", "--check", "--status", str(manifest)],
                       cwd=output, capture_output=True, text=True)
    if p.returncode:
        raise RuntimeError("final evidence package checksum verification failed")



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", choices=sorted(PROTOCOLS), default="quick")
    parser.add_argument("--case", help="Unique run label (e.g. mode4-warm-01)")
    parser.add_argument("--output", type=Path, help="NEW session folder (never overwritten)")
    parser.add_argument("--period", choices=("p1", "p2", "p3"), default="p1")
    parser.add_argument("--expected-mode", choices=("0", "1", "2", "3", "4"),
                        help="Required live transition mode for an auditable physical run")
    parser.add_argument("--input-source", choices=("beta", "direct", "stylus"),
                        help="evtest source; defaults to beta MT (stylus for pen protocol)")
    parser.add_argument("--demo", action="store_true", help="Preview cues only, no hardware or sudo")
    parser.add_argument("--audio-check", action="store_true",
                        help="Require audible playback confirmed by operator; no hardware changes")
    args = parser.parse_args()
    if not (args.demo or args.audio_check) and (
            not args.output or not args.case or args.expected_mode is None):
        parser.error("--case, --output and --expected-mode are required for physical tests")
    if args.case and not all(x.isalnum() or x in "._-" for x in args.case):
        parser.error("--case accepts only ASCII letters/digits/._-")
    if args.output and args.output.exists():
        parser.error("output already exists; choose a unique run directory")
    phases = PROTOCOLS[args.protocol]
    input_source = args.input_source or ("stylus" if args.protocol == "stylus"
                                         else "beta")
    if input_source == "direct" and args.protocol != "single":
        parser.error("direct HID control must use the single-finger protocol")
    if input_source == "stylus" and args.protocol != "stylus":
        parser.error("stylus source requires the stylus protocol")
    with tempfile.TemporaryDirectory(prefix="sl4a-audio-") as temp:
        audio = Audio(Path(temp), dry=args.demo)
        audio.preflight()  # Sound MUST be confirmed before sudo or touching driver.
        if args.audio_check:
            print("AUDIO CHECK PASSED; no driver or evidence changes made.")
            return 0
        if args.demo:
            with (Path(temp) / "demo-markers.tsv").open("w") as markers:
                countdown(audio, markers, 5)
                guide(audio, markers, phases)
            return 0
        if not MODE.exists() or not STATS.exists():
            raise RuntimeError("MSHW0231 touch driver is not present")
        if not shutil.which("evtest"):
            raise RuntimeError("evtest is required for meaningful MT event traces")
        # Check the live module and clean source before opening ANY evidence
        # capture. No input trace can qualify a stale or mismatched build.
        built = ROOT / "driver/sl4a-spi-hid.ko"
        verified_identity = verify_run_integrity(args.expected_mode, built)
        mode = verified_identity["live_mode_verified"]
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # The collector is deliberately a root-run read-only script; the
        # prompts/playback must stay in this (desktop-user) process.
        subprocess.run(["sudo", "-v"], check=True)
        props = {
            **verified_identity,
            "utc_start": stamp(),
            "case": args.case, "protocol": args.protocol,
            "input_source": input_source,
            "live_std_raw_transition": mode,
            "kernel": probe(["uname", "-r"]),
            "git_head": probe(["git", "-C", str(ROOT), "rev-parse", "HEAD"]),
            "loaded_srcversion": txt(Path("/sys/module/sl4a_spi_hid/srcversion")),
            "module_file": probe(["modinfo", "-F", "filename", "sl4a-spi-hid"]),
            "module_signer": probe(["modinfo", "-F", "signer", "sl4a-spi-hid"]),
            "boot_profile": txt(Path("/etc/modprobe.d/sl4a-spi-hid.conf")),
            "stats_before": txt(STATS),
        }

        # Dynamic early-stop marker lets the read-only evidence collector
        # close and checksum promptly after all verified gestures. The large
        # duration is only a hard upper bound, not a forced waiting period.
        total = min(3600, max(240, len(phases) * 85 + 180))
        marker = args.output / "trace/sl4a-guided-complete.flag"
        cmd = ["sudo", "-n", str(COLLECTOR),
               "--period", args.period, "--case", args.case,
               "--duration", str(total),
               "--stop-file", str(marker),
               "--output", str(args.output)]
        cmd.append({"stylus": "--capture-stylus",
                    "direct": "--capture-direct-touch",
                    "beta": "--capture-beta-multitouch"}[input_source])
        markers_file = Path(temp) / "cues.tsv"
        live_jsonl = Path(temp) / "live-evdev.jsonl"
        monitor_errors = Path(temp) / "live-monitor-stderr.txt"
        phase_results = []
        guide_error = None
        exit_code = -1
        with markers_file.open("w") as marks:
            marks.write("utc\tmonotonic_seconds\tevent\tdetail\n")
            marks.flush()
            with (Path(temp) / "collector.log").open("w") as collector_log, \
                 monitor_errors.open("w") as monitor_err:
                proc = subprocess.Popen(cmd, stdout=collector_log,
                                        stderr=subprocess.STDOUT)
                monitor = None
                try:
                    # Wait until the original evtest helper has discovered
                    # the actual dynamic eventN device, not just a file name.
                    event_capture = args.output / "trace/input" / {
                        "stylus": "stylus.evtest.txt",
                        "direct": "direct-touch.evtest.txt",
                        "beta": "beta-multitouch.evtest.txt",
                    }[input_source]
                    event_device = selected_event_node(event_capture)
                    monitor = subprocess.Popen(
                        ["sudo", "-n", sys.executable, "-u",
                         str(ROOT / "tools/hardware_evidence/live_input_gate.py"),
                         "--stream", "--source", input_source,
                         "--device", event_device],
                        stdout=subprocess.PIPE, stderr=monitor_err,
                        text=True, bufsize=1, start_new_session=True)
                    frames = queue.Queue(maxsize=4096)
                    reader = threading.Thread(
                        target=read_live_events,
                        args=(monitor, frames, live_jsonl), daemon=True)
                    reader.start()
                    # Fail closed unless the monitor itself confirms the
                    # validated MSHW0231 event node was opened.
                    try:
                        ready = frames.get(timeout=9)
                    except queue.Empty as e:
                        raise RuntimeError("live input monitor did not start") from e
                    if ready.get("kind") != "ready":
                        # Reader EOF is only a symptom. The subprocess writes
                        # the actionable cause (e.g. permission, sysfs identity,
                        # or Python startup failure) to its stderr log.
                        try:
                            monitor.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            pass
                        monitor_err.flush()
                        diagnostic = monitor_errors.read_text(
                            errors="replace").strip()[-3000:]
                        raise RuntimeError(
                            f"live monitor startup failed (rc={monitor.poll()}): " +
                            (diagnostic or str(ready)))
                    if ready.get("device") != event_device:
                        raise RuntimeError("monitored device differs from evtest device")
                    mark(marks, "capture-ready",
                         f"mode={mode};device={event_device};source={input_source}")
                    audio.speak("Recording is ready. Keep the test screen clear. "
                                "Follow my spoken instructions. "
                                "I will not advance until the requested "
                                "touch gesture is detected.")
                    phase_results = live_capture(audio, marks, phases, frames, proc)
                except (Exception, KeyboardInterrupt) as e:
                    guide_error = str(e)
                    if monitor is not None:
                        monitor_err.flush()
                        detail = monitor_errors.read_text(
                            errors="replace").strip()[-3000:]
                        if detail and detail not in guide_error:
                            guide_error += f"; monitor stderr: {detail}"
                    mark(marks, "session-incomplete", guide_error)
                finally:
                    # Close the evtest/journal collector normally even on
                    # failure, preserving all completed partial evidence.
                    if monitor is not None:
                        monitor.terminate()
                        try:
                            monitor.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            monitor.kill()
                            monitor.wait(timeout=5)
                    if proc.poll() is None:
                        try:
                            exit_code = stop_capture(proc, args.output)
                        except (OSError, subprocess.CalledProcessError,
                                subprocess.TimeoutExpired) as e:
                            if guide_error is None:
                                guide_error = f"collector stop failed: {e}"
                            proc.terminate()
                            try:
                                proc.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                                proc.wait(timeout=5)
                            exit_code = proc.returncode or -1
                    else:
                        exit_code = proc.returncode
        props["phase_results"] = ";".join(
            f"{name}:{verdict}:{attempt}" for name, verdict, attempt
            in phase_results)
        props["guide_error"] = guide_error or ""
        props["audio_instructions_confirmed"] = "YES"
        props["utc_end"] = stamp()
        props["stats_after"] = txt(STATS)
        props["collector_exit_code"] = str(exit_code)
        # An unchanged Git tree doesn't rule out a replaced .ko file, so
        # recheck the exact same binary and live kernel module after capture.
        try:
            check = verify_run_integrity(args.expected_mode, built)
            if (check["module_sha256"] != verified_identity["module_sha256"]
                    or check["source_commit"] != verified_identity["source_commit"]):
                raise RuntimeError("signed module or source changed during capture")
            props.update(verify_counters(
                props["stats_before"], props["stats_after"], input_source))
            props["integrity_and_counters"] = "PASS"
        except RuntimeError as e:
            if guide_error is None:
                guide_error = str(e)
            props["integrity_and_counters"] = "FAIL: " + str(e)
        props["guide_error"] = guide_error or ""
        operator = args.output / "operator"
        # Only the new directory created for this run is chowned; original
        # driver, MOK and persistent configuration remain untouched.
        subprocess.run(["sudo", "cp", str(markers_file), str(operator/"cues.tsv")], check=True)
        metadata = Path(temp) / "run-metadata.txt"
        metadata.write_text("".join(f"{k}={v}\n" for k, v in props.items()))
        subprocess.run(["sudo", "cp", str(metadata), str(operator/"run-metadata.txt")], check=True)
        subprocess.run(["sudo", "cp", str(Path(temp)/"collector.log"),
                        str(operator/"collector.log")], check=True)
        for artifact, title in ((live_jsonl, "live-evdev.jsonl"),
                                (monitor_errors, "live-monitor-stderr.txt")):
            if artifact.exists():
                subprocess.run(["sudo", "-n", "cp", str(artifact),
                                str(operator/title)], check=True)
        subprocess.run(["sudo", "chown", "-R", f"{os.getuid()}:{os.getgid()}",
                        str(args.output)], check=True)
        # The base collector hashes its files before the guide copies
        # supplemental cue/monitor evidence. Hash those artifacts separately,
        # without invalidating the collector's immutable manifest.
        extra_files = ("cues.tsv", "run-metadata.txt", "collector.log",
                       "live-evdev.jsonl", "live-monitor-stderr.txt")
        with (operator / "guided-sha256.txt").open("w") as manifest:
            for name in extra_files:
                artifact = operator / name
                if artifact.is_file():
                    manifest.write(f"{file_sha(artifact)}  {name}\n")
        finalize_manifest(args.output)
        status = txt(args.output/"session-status.txt")
        if guide_error:
            raise RuntimeError("LIVE GATE INCOMPLETE: " + guide_error +
                               "; evidence saved, do not mark PASS")
        if len(phase_results) != len(phases):
            raise RuntimeError("LIVE GATE INCOMPLETE: some gestures were never verified")
        if exit_code != 0 or "status=completed" not in status:
            raise RuntimeError("CAPTURE INCOMPLETE; evidence saved, do not mark PASS")
        captured = args.output / "trace/input" / {
            "stylus": "stylus.evtest.txt",
            "direct": "direct-touch.evtest.txt",
            "beta": "beta-multitouch.evtest.txt",
        }[input_source]
        if not captured.is_file() or "Event: time" not in captured.read_text(errors="replace"):
            raise RuntimeError("No captured evtest input events; do not mark PASS")
        print(f"\nCAPTURE SAVED: {args.output}\n"
              f"Run metadata and cue timestamps: {operator}\n"
              "All live gesture gates, source identity, resets, "
              "frame drops and evidence checksums passed for this session. "
              "Cold boot/reload/suspend still require separate qualification.",
              flush=True)
        return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.CalledProcessError, OSError,
            subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        print(f"\nSTOP: {exc}", file=sys.stderr)
        sys.exit(1)
