"""Vector math, curves and easing - the "math" half of the renderer.

Everything is plain ``(x, y)`` tuples in a y-down coordinate system (PIL).
"""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

Vec = Tuple[float, float]
Ctrl = Sequence[Vec]


# --------------------------------------------------------------------------- #
# basic vector helpers
# --------------------------------------------------------------------------- #
def v(x: float, y: float) -> Vec:
    return (float(x), float(y))


def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1])


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1])


def mul(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s)


def mix(a: Vec, b: Vec, t: float) -> Vec:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def length(a: Vec) -> float:
    return math.hypot(a[0], a[1])


def normalise(a: Vec) -> Vec:
    l = length(a) or 1.0
    return (a[0] / l, a[1] / l)


def perp(a: Vec) -> Vec:
    return (-a[1], a[0])


def heading(a: Vec, b: Vec) -> float:
    return math.atan2(b[1] - a[1], b[0] - a[0])


def polar(origin: Vec, angle: float, radius: float) -> Vec:
    return (origin[0] + math.cos(angle) * radius, origin[1] + math.sin(angle) * radius)


def rotate(p: Vec, angle: float, pivot: Vec = (0.0, 0.0)) -> Vec:
    c, s = math.cos(angle), math.sin(angle)
    dx, dy = p[0] - pivot[0], p[1] - pivot[1]
    return (pivot[0] + dx * c - dy * s, pivot[1] + dx * s + dy * c)


def rotate_many(points: Iterable[Vec], angle: float, pivot: Vec = (0.0, 0.0)) -> List[Vec]:
    return [rotate(p, angle, pivot) for p in points]


def mirror_many(points: Iterable[Vec], axis_x: float = 0.0) -> List[Vec]:
    return [(2 * axis_x - p[0], p[1]) for p in points]


# --------------------------------------------------------------------------- #
# curves
# --------------------------------------------------------------------------- #
def bezier(ctrl: Ctrl, t: float) -> Vec:
    """De Casteljau evaluation of a bezier of any order."""
    points = list(ctrl)
    while len(points) > 1:
        points = [mix(points[i], points[i + 1], t) for i in range(len(points) - 1)]
    return points[0]


def sample_bezier(ctrl: Ctrl, samples: int = 24, include_last: bool = True) -> List[Vec]:
    count = samples + 1 if include_last else samples
    return [bezier(ctrl, i / max(1, count - 1)) for i in range(count)]


def catmull_rom(points: Ctrl, samples: int = 12, closed: bool = False) -> List[Vec]:
    """Smooth interpolating spline through *points* (great for organic outlines)."""
    pts = list(points)
    if len(pts) < 3:
        return pts
    if closed:
        extended = [pts[-1]] + pts + [pts[0], pts[1]]
    else:
        extended = [pts[0]] + pts + [pts[-1]]
    out: List[Vec] = []
    for i in range(1, len(extended) - 2):
        p0, p1, p2, p3 = extended[i - 1], extended[i], extended[i + 1], extended[i + 2]
        seg_samples = samples
        for j in range(seg_samples):
            t = j / seg_samples
            t2, t3 = t * t, t * t * t
            out.append(
                (
                    0.5
                    * (
                        2 * p1[0]
                        + (-p0[0] + p2[0]) * t
                        + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                        + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
                    ),
                    0.5
                    * (
                        2 * p1[1]
                        + (-p0[1] + p2[1]) * t
                        + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                        + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
                    ),
                )
            )
    if not closed:
        out.append(pts[-1])
    return out


# --------------------------------------------------------------------------- #
# shape builders
# --------------------------------------------------------------------------- #
def capsule(a: Vec, b: Vec, r0: float, r1: float, segments: int = 14) -> List[Vec]:
    """Tapering capsule (rounded both ends) - the building block for limbs."""
    angle = heading(a, b)
    pts: List[Vec] = []
    for i in range(segments + 1):  # cap around a
        theta = angle + math.pi / 2 + math.pi * i / segments
        pts.append(polar(a, theta, r0))
    for i in range(segments + 1):  # cap around b
        theta = angle - math.pi / 2 + math.pi * i / segments
        pts.append(polar(b, theta, r1))
    return pts


def strip(curve: Ctrl, widths: Sequence[float], segments: int = 10) -> List[Vec]:
    """Offset a curve into a closed ribbon (used for cloth, stretched arms)."""
    curve = list(curve)
    if len(curve) < 2:
        return curve
    widths = list(widths)
    if len(widths) == 1:
        widths = widths * len(curve)
    elif len(widths) != len(curve):
        # resample the width profile along the curve
        last = len(widths) - 1
        resampled: List[float] = []
        for i in range(len(curve)):
            pos = (i / (len(curve) - 1)) * last
            i0 = int(math.floor(pos))
            i1 = min(i0 + 1, last)
            frac = pos - i0
            resampled.append(widths[i0] * (1 - frac) + widths[i1] * frac)
        widths = resampled
    left: List[Vec] = []
    right: List[Vec] = []
    for i, p in enumerate(curve):
        if i == 0:
            tangent = sub(curve[1], curve[0])
        elif i == len(curve) - 1:
            tangent = sub(curve[-1], curve[-2])
        else:
            tangent = sub(curve[i + 1], curve[i - 1])
        n = perp(normalise(tangent))
        half = widths[i] * 0.5
        left.append(add(p, mul(n, half)))
        right.append(add(p, mul(n, -half)))
    return left + list(reversed(right))


def ellipse(center: Vec, rx: float, ry: float, rotation: float = 0.0, segments: int = 48) -> List[Vec]:
    pts = []
    for i in range(segments):
        theta = 2 * math.pi * i / segments
        p = (math.cos(theta) * rx, math.sin(theta) * ry)
        pts.append(add(center, rotate(p, rotation)))
    return pts


def arc(center: Vec, rx: float, ry: float, start: float, end: float, segments: int = 24) -> List[Vec]:
    pts = []
    for i in range(segments + 1):
        theta = start + (end - start) * i / segments
        pts.append((center[0] + math.cos(theta) * rx, center[1] + math.sin(theta) * ry))
    return pts


def star(center: Vec, outer: float, inner: float, spikes: int = 12, rotation: float = 0.0) -> List[Vec]:
    pts: List[Vec] = []
    for i in range(spikes * 2):
        r = outer if i % 2 == 0 else inner
        theta = rotation + math.pi * i / spikes
        pts.append(polar(center, theta, r))
    return pts


def blob(center: Vec, radius: float, wobble: float, phase: float, segments: int = 32, freq: int = 3) -> List[Vec]:
    """Slightly irregular circle - clouds, dust, steam."""
    pts = []
    for i in range(segments):
        theta = 2 * math.pi * i / segments
        r = radius * (1.0 + wobble * math.sin(freq * theta + phase))
        pts.append(polar(center, theta, r))
    return pts


def polyline_along(points: Ctrl, count: int) -> List[Vec]:
    """Resample a polyline into *count* evenly spaced points."""
    if len(points) < 2:
        return list(points)
    seglen = [length(sub(points[i + 1], points[i])) for i in range(len(points) - 1)]
    total = sum(seglen) or 1.0
    out: List[Vec] = []
    for k in range(count):
        target = total * k / max(1, count - 1)
        walked = 0.0
        for i, l in enumerate(seglen):
            if walked + l >= target or i == len(seglen) - 1:
                t = (target - walked) / (l or 1.0)
                out.append(mix(points[i], points[i + 1], min(1.0, max(0.0, t))))
                break
            walked += l
    return out


# --------------------------------------------------------------------------- #
# timing / easing (anime timing: snappy in, slow out, holds)
# --------------------------------------------------------------------------- #
def clamp01(t: float) -> float:
    return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)


def ease_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 1 - (1 - t) ** 3


def ease_in_cubic(t: float) -> float:
    t = clamp01(t)
    return t ** 3


def ease_in_out(t: float) -> float:
    t = clamp01(t)
    return 3 * t * t - 2 * t * t * t


def ease_out_back(t: float, overshoot: float = 1.70158) -> float:
    t = clamp01(t)
    return 1 + (overshoot + 1) * (t - 1) ** 3 + overshoot * (t - 1) ** 2


def ease_out_elastic(t: float, period: float = 0.35) -> float:
    t = clamp01(t)
    if t in (0.0, 1.0):
        return t
    return 1 + (2 ** (-10 * t)) * math.sin((t - period / 4) * (2 * math.pi) / period)


def pingpong(t: float) -> float:
    """Triangle wave in [0, 1]."""
    t = t % 1.0
    return 2 * t if t < 0.5 else 2 * (1 - t)


def pulse(t: float, sharpness: float = 2.0) -> float:
    """0 -> 1 -> 0 hump with adjustable sharpness."""
    return math.sin(math.pi * clamp01(t)) ** sharpness


def hold(progress: float, start: float, end: float) -> float:
    """Map a timeline position inside [start, end] onto [0, 1]."""
    if end <= start:
        return 1.0 if progress >= end else 0.0
    return clamp01((progress - start) / (end - start))


def two_bone(origin: Vec, angle0: float, angle1: float, length0: float, length1: float) -> Tuple[Vec, Vec, Vec]:
    """Forward kinematics for a two-bone limb. Returns (origin, mid, tip)."""
    mid = polar(origin, angle0, length0)
    tip = polar(mid, angle0 + angle1, length1)
    return origin, mid, tip
