#!/usr/bin/env python3
"""Read-only, offline TTS for lifecycle tests. Never load or change a driver."""
import sys
from pathlib import Path
import tempfile

from guided_session import Audio


def main():
    if len(sys.argv) < 2:
        print("usage: speak_operator.py MESSAGE", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="sl4a-lifecycle-audio-") as folder:
        Audio(Path(folder)).speak(" ".join(sys.argv[1:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
