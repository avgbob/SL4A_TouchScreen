#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0
"""Read-only offline CapImg replay to diagnostic JSON Lines (no uinput)."""
import argparse
import json
from pathlib import Path
from processor import Config, Processor


def frames(path: Path):
    """Accept binary Gate3 heat-*.bin collection or SPB-style hex line corpus."""
    if path.is_dir():
        captures = sorted(path.glob('heat-*.bin'))
        if not captures:
            raise ValueError('directory has no heat-*.bin files')
        for capture in captures:
            yield capture.name, capture.read_bytes()
    elif path.suffix.lower() in ('.bin', '.v0', '.raw'):
        yield path.name, path.read_bytes()
    else:
        with path.open('r', encoding='utf-8') as inp:
            for lineno, line in enumerate(inp, 1):
                value = line.strip().replace(' ', '')
                if not value or value.startswith('#'):
                    continue
                try:
                    yield f'line:{lineno}', bytes.fromhex(value)
                except ValueError as exc:
                    raise ValueError(f'hex error at {path}:{lineno}') from exc


def run(argv=None) -> int:
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument('input', type=Path, help='raw .bin, heat-*.bin directory or one-hex-frame-per-line text')
    arg.add_argument('--association-scale', type=float, default=1,
                     help='research multiplier for DLL association radii (default 1 = recovered values)')
    arg.add_argument('--absolute-gate', type=int, default=1000,
                     help='current-signal detector gate, x10000 units; default 0.1 (provisional mapping)')
    arg.add_argument('--birth-frames', type=int, default=3)
    arg.add_argument('--hold-frames', type=int, default=0)
    arg.add_argument('--baseline-frames', type=int, default=30)
    args = arg.parse_args(argv)
    config = Config(association_scale=args.association_scale,
                    absolute_gate=args.absolute_gate,
                    birth_frames=args.birth_frames,
                    hold_frames=args.hold_frames,
                    baseline_frames=args.baseline_frames)
    processor = Processor(config)
    for n, (name, data) in enumerate(frames(args.input)):
        try:
            result = processor.process(n, data)
        except ValueError as e:
            raise ValueError(f'{args.input}: frame {n} ({name}): {e}') from e
        result['source'] = name
        print(json.dumps(result, separators=(',', ':'), allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(run())
