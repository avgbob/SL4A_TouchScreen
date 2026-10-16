#!/usr/bin/env python3
"""User-session offline TTS for lifecycle tests. Never modify a driver.

After wake, an explicit confirmation prevents a silent/muted audio device,
unready PipeWire/PulseAudio session, or locked desktop from being treated
as a successful audible operator prompt.
"""
import argparse
from pathlib import Path
import sys
import tempfile
import time

from guided_session import Audio


def say_and_confirm(message, confirm=False, retries=1,
                    pause_seconds=2.0):
    with tempfile.TemporaryDirectory(prefix="sl4a-lifecycle-audio-") as folder:
        audio = Audio(Path(folder))
        errors = []
        for trial in range(1, retries + 1):
            try:
                audio.speak(message)
                errors = []
                break
            except (RuntimeError, OSError) as exc:
                errors.append(str(exc))
                if trial < retries:
                    print("Audio service unavailable; retrying after desktop wake "
                          f"({trial}/{retries})", flush=True)
                    time.sleep(pause_seconds)
        if errors:
            raise RuntimeError("Speech could not be played after waking: " +
                               errors[-1])
        if confirm:
            if not sys.stdin.isatty():
                raise RuntimeError("Audible post-wake confirmation requires "
                                   "an interactive terminal")
            # "yes", "Yes", and "YES" were already accepted via .upper().
            # Field transcript: "Yes" echoed BEFORE the prompt, then
            # another "yes" after it. Buffered/mixed keystrokes may
            # be read as one invalid line even though user meant YES.
            # Retry typos without ever advancing without explicit consent.
            for attempt in range(1, 4):
                response = input(
                    "Did you actually HEAR the post-wake spoken instructions? "
                    "Type YES (any case) to start touchscreen checks: ").strip()
                if response.casefold() == "yes":
                    break
                if attempt < 3:
                    print("Confirmation not recognized. Please type only YES "
                          "(or yes), then press Enter. No touch PASS yet.",
                          flush=True)
            else:
                raise RuntimeError(
                    "Post-wake speech unconfirmed after 3 attempts: "
                    "stopping without touch PASS")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true",
                        help="do not continue until operator confirms audible speech")
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("words", nargs="+")
    args = parser.parse_args()
    if not 1 <= args.retries <= 8:
        parser.error("--retries must be in the range 1..8")
    try:
        return say_and_confirm(" ".join(args.words),
                               confirm=args.confirm,
                               retries=args.retries)
    except (RuntimeError, EOFError, KeyboardInterrupt) as exc:
        print("VOICE INCOMPLETE: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
