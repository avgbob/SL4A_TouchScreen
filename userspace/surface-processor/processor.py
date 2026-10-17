# SPDX-License-Identifier: GPL-2.0
"""Offline MSHW0231 CapImg research processor. Not a kernel/HID driver.

Reference-derived stages and experimental policies are deliberately separated.
No live device, feature reports, kernel modules or uinput are accessed here.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from math import isfinite
from struct import unpack_from
from typing import Iterable

COLS, ROWS = 72, 48
CELLS = COLS * ROWS
MAX_TRACKS = 48
# TouchPenProcessor0C19.dll DAT_1808e0460; these are DLL values,
# NOT evidence that our simplified detector/classifier matches Windows.
ASSOCIATION_RADII = (0.5450090169906616, 1.2180980443954468,
                     0.5450090169906616, 1.549246, 1.845492, 2.161228)
COALESCE_D2 = 36.0


def decode_frame(raw: bytes) -> bytes:
    """Extract 72x48 raster from validated V0 report or raw raster.

    Accepts the exact V0 section layout used in spi_hid_capimg_decode_v0,
    a 4300-byte numbered hidraw 0x0c report, or an SPB hex-line prefix of
    five 0xff bytes followed by the V0 body. Ambiguous byte offsets are rejected.
    """
    if len(raw) == CELLS:
        return raw
    if raw.startswith(b'\xff' * 5):
        raw = raw[5:]
    if len(raw) == 4300 and raw[0] == 0x0c:
        raw = (4302).to_bytes(2, 'little') + raw
    if not (4300 <= len(raw) <= 4400 and raw[:3] == b'\xce\x10\x0c'):
        raise ValueError('not a supported CapImg V0 frame')
    payload = memoryview(raw)[5:]
    if len(payload) < 7:
        raise ValueError('truncated V0 payload')
    length = unpack_from('<I', payload)[0]
    if (length < 7 or length > min(len(payload), 4297)
            or unpack_from('<H', payload, 4)[0] != 0 or payload[6] != 0):
        raise ValueError('invalid V0 container header')
    off, heat, vendor = 7, None, False
    while off < length:
        if length - off < 7:
            raise ValueError('truncated CapImg section header')
        n, typ = unpack_from('<IH', payload, off)
        if n < 7 or n > length - off:
            raise ValueError('invalid CapImg section length')
        if typ == 0x100:
            if (heat is not None or n != 16 + CELLS or payload[off + 6] != 1
                    or payload[off + 7] != 8 or unpack_from('<I', payload, off + 8)[0] != 0
                    or unpack_from('<I', payload, off + 12)[0] != CELLS):
                raise ValueError('invalid or duplicate heatmap section')
            heat = bytes(payload[off + 16:off + 16 + CELLS])
        elif typ == 0xff00:
            if vendor:
                raise ValueError('duplicate vendor section')
            vendor = True
        off += n
    if off != length or heat is None or not vendor:
        raise ValueError('missing required heatmap/vendor section')
    return heat


def c590(byte: int) -> int:
    """Fixed-point LUT translated from recovered c590 float transform."""
    return max(0, 10000 - ((byte * 22204 + 500) // 1000 + 6000))


LUT = tuple(c590(i) for i in range(256))


@dataclass(frozen=True)
class Config:
    baseline_frames: int = 30             # per-device SL4 record
    minimum_rise: int = 200              # 0.02 (verified value; mapping approximate)
    absolute_gate: int = 1000            # 0.1 detector gate (application provisional)
    minimum_pixels: int = 2              # recovered threshold
    minimum_weight: int = 1000           # experimental current Linux policy
    association_scale: float = 1.0       # 1.0 means exact recovered DLL radii
    birth_frames: int = 3                # experimental mapping of 3-frame age gate
    hold_frames: int = 0                 # unimplemented Windows quality-gated hold
    max_candidates: int = 48

    def __post_init__(self) -> None:
        if (self.baseline_frames < 1 or self.minimum_rise < 0 or
                self.absolute_gate < 0 or self.minimum_pixels < 1 or
                self.minimum_weight < 0 or not isfinite(self.association_scale) or
                self.association_scale <= 0 or self.association_scale > 100 or
                self.birth_frames < 1 or self.hold_frames < 0 or
                not 1 <= self.max_candidates <= MAX_TRACKS):
            raise ValueError('invalid processor configuration')


class Signal:
    """Asymmetric max-byte baseline: update policy adapted from fork Linux.

    The c590 transform and nominal 30-frame baseline are Windows-derived;
    asymmetric decay every 256 frames is a Linux heuristic, not DLL parity.
    """
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.frames = 0
        self.baseline = [0] * CELLS
        self.drift = 0

    def process(self, raster: bytes) -> tuple[list[int], list[int]] | None:
        if len(raster) != CELLS:
            raise ValueError('expected 3456 raster bytes')
        if self.frames < self.cfg.baseline_frames:
            for i, b in enumerate(raster):
                if b > self.baseline[i]:
                    self.baseline[i] = b
            self.frames += 1
            return None
        self.drift += 1
        decay = self.drift % 256 == 0
        rise = [0] * CELLS
        current = [0] * CELLS
        for i, b in enumerate(raster):
            old = self.baseline[i]
            if b >= old:
                self.baseline[i] = (old * 7 + b) // 8
            elif decay:
                self.baseline[i] = max(0, old - 1)
            current[i] = LUT[b]
            rise[i] = current[i] - LUT[self.baseline[i]]
        self.frames += 1
        return rise, current


@dataclass(frozen=True)
class Candidate:
    x: float
    y: float
    weight: int
    pixels: int
    peak: int
    # Windows FUN_180601690 candidate class is not recovered.
    classification: str = 'unknown'


class Detector:
    """Bounded 4-connected candidate extraction. NOT DLL classifier parity.

    Avoids destructive proximity/ghost suppression. Detection is separated
    from assignment, and each accepted component is visible to diagnostics.
    """
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    def detect(self, rise: list[int], absolute: list[int]) -> list[Candidate]:
        if len(rise) != CELLS or len(absolute) != CELLS:
            raise ValueError('invalid signal grid size')
        mask = bytearray(CELLS)
        for i in range(CELLS):
            mask[i] = int(rise[i] >= self.cfg.minimum_rise and
                          absolute[i] >= self.cfg.absolute_gate)
        result: list[Candidate] = []
        for i in range(CELLS):
            if not mask[i]:
                continue
            mask[i] = 0
            queue = [i]
            count = 0
            mass = 0
            sx = sy = 0
            peak = 0
            head = 0
            while head < len(queue):
                j = queue[head]
                head += 1
                x, y = j % COLS, j // COLS
                w = max(0, rise[j])
                count += 1
                mass += w
                sx += x * w
                sy += y * w
                peak = max(peak, w)
                for k in (j - 1 if x else -1, j + 1 if x + 1 < COLS else -1,
                          j - COLS if y else -1, j + COLS if y + 1 < ROWS else -1):
                    if k >= 0 and mask[k]:
                        mask[k] = 0
                        queue.append(k)
            if mass > 0 and count >= self.cfg.minimum_pixels and mass >= self.cfg.minimum_weight:
                result.append(Candidate(sx / mass, sy / mass, mass, count, peak))
        return sorted(result, key=lambda c: (-c.weight, c.y, c.x))[:self.cfg.max_candidates]


def assignment(cost: list[list[float]]) -> list[int]:
    """Rectangular Hungarian minimization (rows <= columns), deterministic."""
    n = len(cost)
    if n == 0:
        return []
    m = len(cost[0])
    if m < n or any(len(row) != m for row in cost):
        raise ValueError('expected rectangular cost matrix, columns >= rows')
    u, v = [0.0] * (n + 1), [0.0] * (m + 1)
    p, way = [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float('inf')] * (m + 1)
        used = [False] * (m + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta, j1 = float('inf'), 0
            for j in range(1, m + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta, j1 = minv[j], j
            if j1 == 0:
                raise ValueError('no feasible assignment')
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    assigned = [-1] * n
    for j in range(1, m + 1):
        if p[j]:
            assigned[p[j] - 1] = j - 1
    return assigned


@dataclass
class Track:
    id: int
    x: float
    y: float
    age: int = 1
    missed: int = 0
    history: deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=10))

    def __post_init__(self) -> None:
        self.history.append((self.x, self.y))


@dataclass
class Contact:
    id: int
    x: float
    y: float
    age: int
    # Class and merge-group cannot be inferred from the tracker ID. They
    # must be supplied by an independently verified classification/emission
    # stage before Windows report grouping is meaningful.
    group: int | None = None
    status: int | None = None


class Tracker:
    """One-to-one in-radius association, history and optional hold policy.

    No class inference, occlusion guesses, identity swaps or ghost deletion.
    Track IDs are monotonic; mutable merge groups NEVER become tracking IDs.
    """
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.tracks: dict[int, Track] = {}
        self.next_id = 1
        self.previous_frame: int | None = None

    def reset(self) -> None:
        self.tracks.clear()
        self.previous_frame = None

    def update(self, frame: int, candidates: list[Candidate]) -> tuple[list[Contact], bool]:
        if not isinstance(frame, int) or isinstance(frame, bool) or frame < 0:
            raise ValueError('frame sequence must be nonnegative integers')
        if len(candidates) > min(MAX_TRACKS, self.cfg.max_candidates):
            raise ValueError('too many candidates')
        if any(not isfinite(c.x) or not isfinite(c.y) for c in candidates):
            raise ValueError('nonfinite candidate coordinates')
        if frame < 0 or (self.previous_frame is not None and frame <= self.previous_frame):
            raise ValueError('frame sequence must be strictly increasing')
        gap = self.previous_frame is not None and frame - self.previous_frame > 5
        if gap:
            self.tracks.clear()
        self.previous_frame = frame
        tracks = [self.tracks[k] for k in sorted(self.tracks)]
        n, nt = len(candidates), len(tracks)
        # DLL values are strict squared-distance gates, not guessed pixel radii.
        active_count = sum(1 for t in tracks if t.missed == 0)
        radius = ASSOCIATION_RADII[min(active_count, 5)] * self.cfg.association_scale
        r2 = radius * radius
        # Real edges forbidden outside the radius, with one independent birth
        # column per observation. Padding cannot create a contact by mistake.
        invalid, birth = 1e9, r2 + 1.0
        cost = []
        for i, c in enumerate(candidates):
            row = []
            for t in tracks:
                d2 = (c.x - t.x)**2 + (c.y - t.y)**2
                row.append(d2 if d2 < r2 else invalid)
            row.extend(birth if j == i else invalid for j in range(n))
            cost.append(row)
        chosen = assignment(cost)
        matched_ids = set()
        unmatched = []
        # Update existing tracks first. Expire old tracks before admitting
        # new observations so full capacity does not lose an entire frame.
        for i, slot in enumerate(chosen):
            c = candidates[i]
            if slot < nt and cost[i][slot] < invalid:
                t = tracks[slot]
                t.x, t.y = c.x, c.y
                t.age += 1
                t.missed = 0
                t.history.append((c.x, c.y))
                matched_ids.add(t.id)
            else:
                unmatched.append(c)
        for t in tracks:
            if t.id not in matched_ids:
                t.missed += 1
                if t.missed > self.cfg.hold_frames:
                    del self.tracks[t.id]
        for c in unmatched:
            if len(self.tracks) >= MAX_TRACKS:
                continue
            tid = self.next_id
            self.next_id += 1
            self.tracks[tid] = Track(tid, c.x, c.y)
        # No Windows class or merge group is available yet: do not invent
        # status=1 or use our Linux/local track IDs as Windows group labels.
        contacts = [Contact(t.id, t.x, t.y, t.age) for t in self.tracks.values()
                    if t.missed == 0 and t.age >= self.cfg.birth_frames]
        return self._group(contacts), gap

    @staticmethod
    def _group(records: list[Contact]) -> list[Contact]:
        """FUN_1806025c0: rewrite groups and mark class-1 pairs class 7.

        Both local records remain. Do not claim their external Windows/HID
        validity, which requires unrecovered classifier/emission semantics.
        """
        for i, a in enumerate(records):
            if a.status not in (1, 3) or a.group is None:
                continue
            for b in records[i + 1:]:
                if b.status not in (1, 3) or b.group is None or b.group == a.group:
                    continue
                if (a.x - b.x)**2 + (a.y - b.y)**2 >= COALESCE_D2:
                    continue
                old = b.group
                for rec in records:
                    if rec.group == old:
                        rec.group = a.group
                if a.status == 1:
                    a.status = 7
                if b.status == 1:
                    b.status = 7
        return records


class Processor:
    """Read-only staged experiment; process raw raster or CapImg V0 frames."""
    def __init__(self, cfg: Config | None = None) -> None:
        self.cfg = cfg or Config()
        self.signal = Signal(self.cfg)
        self.detector = Detector(self.cfg)
        self.tracker = Tracker(self.cfg)
        self.previous_frame: int | None = None

    def process(self, frame: int, raw: bytes) -> dict:
        # Validate before processing signal; malformed sequences must not
        # alter baseline, track history or frame state even during calibration.
        if (not isinstance(frame, int) or isinstance(frame, bool) or frame < 0 or
                (self.previous_frame is not None and frame <= self.previous_frame)):
            raise ValueError('frame sequence must be strictly increasing nonnegative integers')
        raster = decode_frame(raw)
        values = self.signal.process(raster)
        if values is None:
            self.previous_frame = frame
            # Frame counter still advances; no stale tracks during calibration.
            return {'frame': frame, 'stage': 'baseline', 'contacts': [], 'candidates': []}
        candidates = self.detector.detect(*values)
        contacts, reset = self.tracker.update(frame, candidates)
        self.previous_frame = frame
        return {'frame': frame, 'stage': 'tracking', 'discontinuity_reset': reset,
                'candidates': [vars(c) for c in candidates],
                'contacts': [vars(c) for c in contacts],
                'track_count': len(self.tracker.tracks)}
