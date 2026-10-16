#!/usr/bin/env python3
"""Audibly guided physical-touch capture with synced markers and read-only evidence.

Runs cue audio as the desktop user; grants root only to the established
read-only evtest/journal collector. No install, reload, or power operations.
"""
import argparse
import datetime as dt
import hashlib
import math
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import wave

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
        ("one", "Move ONE finger around the screen", 6),
        ("pinch", "Place TWO fingers far apart; PINCH together", 8),
        ("expand", "Keep both down; EXPAND apart", 8),
        ("lift", "Lift BOTH fingers completely", 5),
    ],
    "pinch": [
        ("far", "Place TWO fingers far apart and HOLD", 6),
        ("close", "PINCH slowly together WITHOUT lifting", 8),
        ("hold", "HOLD the close position WITHOUT lifting", 6),
        ("expand", "EXPAND the same two fingers, no lift", 8),
        ("lift", "LIFT both fingers", 5),
    ],
    "contacts": [
        ("one", "ONE finger down, then lift", 6),
        ("two", "TWO fingers down, then lift", 6),
        ("three", "THREE fingers down, then lift", 6),
        ("four", "FOUR fingers down, then lift", 6),
        ("five", "FIVE fingers down, then lift", 6),
        ("one-lift", "TWO fingers close; lift ONLY one, then the other", 9),
        ("recontact", "Rapid one-finger lift and re-contact", 6),
    ],
    "stylus": [
        ("hover", "Hover pen just ABOVE glass", 7),
        ("pen", "Draw with pen in contact", 8),
        ("lift", "Lift pen, leave screen untouched", 5),
    ],
}
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
    def __init__(self, folder, dry=False):
        self.dry = dry
        self.player = next((p for p in ("paplay", "pw-play", "aplay")
                            if shutil.which(p)), None)
        self.sounds = {}
        self.folder = folder
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

    def play(self, name):
        if self.dry:
            print("[DEMO AUDIO]", name, flush=True)
            return
        if not self.player:
            raise RuntimeError("No audio player found: install paplay/pw-play/aplay, "
                               "and connect working speakers or headphones.")
        done = subprocess.run([self.player, str(self.sounds[name])],
                              capture_output=True, text=True, timeout=5)
        if done.returncode:
            raise RuntimeError(f"Audio playback failed: {done.stderr.strip()}")

    def preflight(self):
        print("AUDIO CHECK: you must actually HEAR two tones.", flush=True)
        self.play("pre")
        if self.dry:
            return
        if not sys.stdin.isatty():
            raise RuntimeError("Physical tests need an interactive TTY for audio confirmation")
        answer = input("Did you HEAR both tones? Type YES to proceed: ").strip()
        if answer.upper() != "YES":
            raise RuntimeError("No audible cue confirmation: recording not started")

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

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", choices=sorted(PROTOCOLS), default="quick")
    parser.add_argument("--case", help="Unique run label (e.g. mode4-warm-01)")
    parser.add_argument("--output", type=Path, help="NEW session folder (never overwritten)")
    parser.add_argument("--period", choices=("p1", "p2", "p3"), default="p1")
    parser.add_argument("--input-source", choices=("beta", "direct", "stylus"),
                        help="evtest source; defaults to beta MT (stylus for pen protocol)")
    parser.add_argument("--demo", action="store_true", help="Preview cues only, no hardware or sudo")
    parser.add_argument("--audio-check", action="store_true",
                        help="Require audible playback confirmed by operator; no hardware changes")
    args = parser.parse_args()
    if not (args.demo or args.audio_check) and (not args.output or not args.case):
        parser.error("--case and --output are required outside --demo")
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
        mode = txt(MODE)
        if mode not in ("0", "1", "2", "3", "4"):
            raise RuntimeError(f"unexpected module mode: {mode}")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # The collector is deliberately a root-run read-only script; the
        # prompts/playback must stay in this (desktop-user) process.
        subprocess.run(["sudo", "-v"], check=True)
        props = {
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
        built = ROOT / "driver/sl4a-spi-hid.ko"
        if built.is_file():
            props["worktree_module_sha256"] = file_sha(built)
        # Duration includes countdown, cue playback, collector startup and a
        # post-gesture margin; SIGINT is not used to truncate evidence.
        total = sum(seconds for _, _, seconds in phases) + len(phases) * 2 + 5 + 20
        cmd = ["sudo", "-n", str(COLLECTOR),
               "--period", args.period, "--case", args.case,
               "--duration", str(total), "--output", str(args.output)]
        cmd.append({"stylus": "--capture-stylus",
                    "direct": "--capture-direct-touch",
                    "beta": "--capture-beta-multitouch"}[input_source])
        markers_file = Path(temp) / "cues.tsv"
        with markers_file.open("w") as marks:
            marks.write("utc\tmonotonic_seconds\tevent\tdetail\n")
            marks.flush()
            with (Path(temp) / "collector.log").open("w") as collector_log:
                proc = subprocess.Popen(cmd, stdout=collector_log,
                                        stderr=subprocess.STDOUT)
                try:
                    # The collector first snapshots sysfs before starting
                    # evtest. Wait for the actual event capture file instead of guessing.
                    start = time.monotonic()
                    event_capture = args.output / "trace/input" / {
                        "stylus": "stylus.evtest.txt",
                        "direct": "direct-touch.evtest.txt",
                        "beta": "beta-multitouch.evtest.txt",
                    }[input_source]
                    while subprocess.run(["sudo", "-n", "test", "-s",
                                           str(event_capture)], check=False).returncode != 0:
                        if proc.poll() is not None:
                            raise RuntimeError("collector exited before event capture started")
                        if time.monotonic() - start > 20:
                            raise RuntimeError("event capture did not begin within 20 seconds")
                        time.sleep(.3)
                    # The collector owns its output directory as root (0700).
                    # Checking it without sudo falsely reports "not found".
                    safe_sleep(2, proc)
                    mark(marks, "capture-ready", f"mode={mode}")
                    countdown(audio, marks, 5, proc)
                    guide(audio, marks, phases, proc)
                    print("Recording remaining idle window; keep hands off...", flush=True)
                    exit_code = proc.wait(timeout=total + 20)
                except (Exception, KeyboardInterrupt):
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)
                    # Fail closed but do not strand root-owned partial
                    # captures and cue timestamps behind a 0700 directory.
                    if args.output.is_dir():
                        operator = args.output / "operator"
                        for source, target in (
                            (markers_file, operator / "cues.tsv"),
                            (Path(temp) / "collector.log", operator / "collector.log"),
                        ):
                            subprocess.run(["sudo", "-n", "cp",
                                            str(source), str(target)], check=False)
                        subprocess.run(["sudo", "-n", "chown", "-R",
                                        f"{os.getuid()}:{os.getgid()}",
                                        str(args.output)], check=False)
                    raise
        props["utc_end"] = stamp()
        props["stats_after"] = txt(STATS)
        props["collector_exit_code"] = str(exit_code)
        operator = args.output / "operator"
        # Only the new directory created for this run is chowned; original
        # driver, MOK and persistent configuration remain untouched.
        subprocess.run(["sudo", "cp", str(markers_file), str(operator/"cues.tsv")], check=True)
        metadata = Path(temp) / "run-metadata.txt"
        metadata.write_text("".join(f"{k}={v}\n" for k, v in props.items()))
        subprocess.run(["sudo", "cp", str(metadata), str(operator/"run-metadata.txt")], check=True)
        subprocess.run(["sudo", "cp", str(Path(temp)/"collector.log"),
                        str(operator/"collector.log")], check=True)
        subprocess.run(["sudo", "chown", "-R", f"{os.getuid()}:{os.getgid()}",
                        str(args.output)], check=True)
        status = txt(args.output/"session-status.txt")
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
              "This is evidence capture, not an automatic hardware PASS.",
              flush=True)
        return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.CalledProcessError, OSError,
            subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
        print(f"\nSTOP: {exc}", file=sys.stderr)
        sys.exit(1)
