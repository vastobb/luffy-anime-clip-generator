"""Procedural背景 toolkit: anime skies, sea, ship deck and action FX.

Everything here is drawn with analytic shapes (masks + cel fills), so it stays
in the same flat-colour, hard-edged style as the character.
"""

from __future__ import annotations

import math
import random
from typing import List, Optional, Sequence, Tuple

from .cel import Cel, Color, shade, tint
from .vec import (
    Vec,
    add,
    blob,
    catmull_rom,
    ellipse,
    mul,
    normalise,
    polar,
    star,
    strip,
    sub,
)

# --------------------------------------------------------------------------- #
# sky / atmosphere
# --------------------------------------------------------------------------- #
def sky_gradient(cel: Cel, top: Color, bottom: Color) -> None:
    cel.vertical_gradient(top, bottom)


def haze(cel: Cel, y0: float, y1: float, color: Color, alpha: float = 0.35) -> None:
    m = cel.mask()
    m.polygon([(-20, y0), (cel.w + 20, y0), (cel.w + 20, y1), (-20, y1)])
    cel.fill_blend(m.bake(), color, alpha)


def cloud(cel: Cel, center: Vec, scale: float, rng: random.Random, fill: Color = (255, 255, 255), shadow: Color = (206, 228, 244), alpha: float = 1.0) -> None:
    """Fluffy anime cloud built from a handful of overlapping blobs."""
    m = cel.mask()
    parts = 4 + rng.randrange(3)
    for i in range(parts):
        dx = (i - parts / 2) * 0.55 * scale + rng.uniform(-0.1, 0.1) * scale
        dy = rng.uniform(-0.12, 0.12) * scale
        r = scale * rng.uniform(0.42, 0.62)
        m.polygon(blob((center[0] + dx, center[1] + dy), r, wobble=0.16, phase=rng.uniform(0, 6), freq=3))
    img = m.bake()
    cel.region(img, fill, shadow=shadow, shadow_offset=(2, 3), outline=tint(fill, 0.5, shadow), outline_width=2, alpha=alpha)


def sun_disc(cel: Cel, center: Vec, radius: float, color: Color = (255, 246, 214), glow: Color = (255, 224, 150), alpha: float = 1.0) -> None:
    m = cel.mask()
    m.ellipse(center, radius, radius)
    img = m.bake()
    cel.region(img, color, outline=None, alpha=alpha)
    cel.glow(img, glow, radius=radius * 0.9, alpha=0.45 * alpha)


def sun_rays(cel: Cel, center: Vec, count: int, length: float, half_width: float, tilt: float = 0.0, tone: int = 26, seed: int = 3) -> None:
    """Rotating god-rays: wedges screened onto the frame (very anime)."""
    from PIL import Image, ImageDraw

    rng = random.Random(seed)
    layer = Image.new("RGB", (cel.w, cel.h), (0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for i in range(count):
        angle = tilt + 2 * math.pi * i / count + rng.uniform(-0.05, 0.05)
        w = half_width * rng.uniform(0.5, 1.3)
        p0 = polar(center, angle - w / max(length, 1.0), length * 0.15)
        p1 = polar(center, angle + w / max(length, 1.0), length * 0.15)
        p2 = polar(center, angle + w, length)
        p3 = polar(center, angle - w, length)
        draw.polygon([p0, p1, p2, p3], fill=(tone, tone, min(255, tone + 10)))
    cel.screen(layer, 1.0)


def birds(cel: Cel, spots: Sequence[Tuple[Vec, float]], color: Color = (48, 56, 70), width: float = 2.2) -> None:
    for center, scale in spots:
        left = [add(center, (-6 * scale, 2 * scale)), add(center, (-3 * scale, -1 * scale)), center]
        right = [center, add(center, (3 * scale, -1 * scale)), add(center, (6 * scale, 2 * scale))]
        cel.stroke(left, color + (220,), width, smooth=4)
        cel.stroke(right, color + (220,), width, smooth=4)


# --------------------------------------------------------------------------- #
# sea
# --------------------------------------------------------------------------- #
def ocean(cel: Cel, horizon: float, deep: Color = (38, 96, 150), mid: Color = (52, 122, 178), near: Color = (66, 142, 196), glints: bool = True, seed: int = 7) -> None:
    rng = random.Random(seed)
    h = cel.h
    band = cel.mask()
    band.polygon([(-20, horizon), (cel.w + 20, horizon), (cel.w + 20, h + 20), (-20, h + 20)])
    cel.fill_blend(band.bake(), near, 1.0)
    # cel-painted depth bands
    for i, (tone, frac) in enumerate(((mid, 0.18), (deep, 0.45), (shade(mid, 0.92), 0.72))):
        y = horizon + (h - horizon) * frac
        th = (h - horizon) * 0.10
        m = cel.mask()
        pts = [(-20, y)]
        for k in range(9):
            xx = cel.w * k / 8
            pts.append((xx, y + math.sin(k * 1.7 + i) * th * 0.55))
        pts += [(cel.w + 20, y), (cel.w + 20, y + th + 40), (-20, y + th + 40)]
        m.polygon(pts)
        cel.fill_blend(m.bake(), tone, 0.5)
    # wave lines
    for i in range(26):
        y = horizon + 10 + rng.random() * (h - horizon - 20)
        depth = (y - horizon) / max(1.0, (h - horizon))
        length = 30 + depth * 150 * rng.uniform(0.5, 1.4)
        x = rng.uniform(-20, cel.w)
        curve = [
            (x, y),
            (x + length * 0.5, y - 2 - depth * 4),
            (x + length, y),
        ]
        cel.stroke(curve, (236, 248, 255, 130), 1.3 + depth * 2.4, smooth=6)
    if glints:
        sea_sparkles(cel, horizon, 0.0, cel.w, count=26, rng=rng)


def sea_sparkles(cel: Cel, y0: float, x0: float, x1: float, count: int = 20, rng: Optional[random.Random] = None, color: Color = (255, 255, 255)) -> None:
    rng = rng or random.Random(11)
    for _ in range(count):
        x = rng.uniform(x0, x1)
        y = y0 + rng.random() ** 1.6 * max(20.0, (cel.h - y0) * 0.9)
        r = rng.uniform(2.0, 6.5)
        m = cel.mask()
        m.polygon(star((x, y), r, r * 0.22, spikes=4, rotation=rng.uniform(0, 1.5)))
        cel.fill_blend(m.bake(), color, rng.uniform(0.35, 0.8))


def sun_path(cel: Cel, center_x: float, horizon: float, width0: float, width1: float, color: Color = (255, 240, 200), alpha: float = 0.45, seed: int = 5) -> None:
    """Golden reflection column under the sun."""
    rng = random.Random(seed)
    y = horizon
    while y < cel.h:
        t = (y - horizon) / max(1.0, cel.h - horizon)
        w = width0 + (width1 - width0) * t
        m = cel.mask()
        jitter = rng.uniform(-0.06, 0.06) * w
        m.polygon(
            [
                (center_x - w / 2 + jitter, y),
                (center_x + w / 2 + jitter, y),
                (center_x + w / 2 * 0.85, y + 6),
                (center_x - w / 2 * 0.85, y + 6),
            ]
        )
        cel.fill_blend(m.bake(), color, alpha * (1 - t * 0.6))
        y += 8 + t * 10


# --------------------------------------------------------------------------- #
# ship deck (perspective planks + railing)
# --------------------------------------------------------------------------- #
def deck(cel: Cel, horizon: float, wood: Color = (216, 178, 130), wood_dark: Color = (198, 160, 114), wood_line: Color = (142, 108, 72), vp_x: Optional[float] = None, scroll: float = 0.0) -> None:
    vp = cel.w * 0.5 if vp_x is None else vp_x
    h = cel.h
    band = cel.mask()
    band.polygon([(-20, horizon), (cel.w + 20, horizon), (cel.w + 20, h + 20), (-20, h + 20)])
    cel.fill_blend(band.bake(), wood, 1.0)
    planks = 9
    for i in range(planks):
        frac = (i + 1) / (planks + 1)
        x_far = vp + (frac - 0.5) * cel.w * 0.55
        x_near = vp + (frac - 0.5) * cel.w * 3.4
        m = cel.mask()
        m.polygon(
            [
                (x_far, horizon),
                (x_far + cel.w * 0.03, horizon),
                (x_near + cel.w * 0.16, h + 20),
                (x_near - cel.w * 0.02, h + 20),
            ]
        )
        cel.fill_blend(m.bake(), wood_dark if i % 2 else wood, 0.55 if i % 2 else 0.0)
        cel.stroke(
            [(x_far, horizon), (x_near, h + 20)],
            wood_line + (170,),
            2.4,
        )
    # scrolling plank seams (motion cue)
    rows = 7
    for i in range(rows):
        base = ((i / rows) + (scroll % (1 / rows))) % 1.0
        y = horizon + (h - horizon) * (base ** 1.7)
        m = cel.mask()
        x_far = vp + (base - 0.5) * cel.w * 0.8
        x_near = vp + (base - 0.5) * cel.w * 4.0
        h_thickness = 2 + 6 * base
        m.polygon([(x_far - cel.w * 0.5, y), (x_far + cel.w * 0.5, y), (x_near + cel.w * 0.5, y + h_thickness), (x_near - cel.w * 0.5, y + h_thickness)])
        cel.fill_blend(m.bake(), wood_line, 0.20 + 0.18 * base)


def railing(cel: Cel, y: float, color: Color = (206, 168, 118), post: Color = (176, 138, 92), scroll: float = 0.0) -> None:
    rail = cel.mask()
    rail.polygon([(-20, y), (cel.w + 20, y), (cel.w + 20, y + 7), (-20, y + 7)])
    cel.fill_blend(rail.bake(), color, 1.0)
    cel.stroke([(-20, y + 3.5), (cel.w + 20, y + 3.5)], (110, 76, 40, 200), 2.0)
    spacing = 120
    shift = -(scroll * cel.w) % spacing
    x = -spacing + shift
    while x < cel.w + spacing:
        m = cel.mask()
        m.polygon([(x - 4, y), (x + 4, y), (x + 5, y + 46), (x - 5, y + 46)])
        cel.fill_blend(m.bake(), post, 1.0)
        x += spacing


def mast(cel: Cel, x: float, y0: float, width: float, color: Color = (150, 108, 62)) -> None:
    m = cel.mask()
    m.polygon([(x - width / 2, y0), (x + width / 2, y0), (x + width / 2 * 0.7, cel.h + 20), (x - width / 2 * 0.7, cel.h + 20)])
    img = m.bake()
    cel.region(img, color, shadow=shade(color, 0.82), shadow_offset=(6, 4), outline=(96, 66, 36), outline_width=3)


# --------------------------------------------------------------------------- #
# action FX
# --------------------------------------------------------------------------- #
def speed_lines(cel: Cel, center: Vec, count: int = 46, r0: float = 90.0, r1: float = 900.0, color: Color = (255, 255, 255), alpha: float = 0.75, width: float = 3.0, seed: int = 2, bias: float = 0.0) -> None:
    rng = random.Random(seed)
    m = cel.mask()
    for i in range(count):
        angle = bias + 2 * math.pi * i / count + rng.uniform(-0.05, 0.05)
        inner = r0 * rng.uniform(0.55, 1.25)
        outer = r1 * rng.uniform(0.75, 1.15)
        w0 = width * rng.uniform(0.5, 1.6)
        w1 = w0 * rng.uniform(0.15, 0.5)
        p0 = polar(center, angle, inner)
        p1 = polar(center, angle, outer)
        m.polygon(strip([p0, p1], [w0, w1]))
    cel.fill_blend(m.bake(), color, alpha)


def streaks(cel: Cel, count: int = 22, color: Color = (255, 255, 255), alpha: float = 0.5, seed: int = 4, width: float = 3.0) -> None:
    rng = random.Random(seed)
    for _ in range(count):
        y = rng.uniform(0, cel.h)
        x = rng.uniform(-100, cel.w)
        length = rng.uniform(90, 420)
        cel.stroke([(x, y), (x + length, y - rng.uniform(-6, 6))], color + (int(255 * alpha),), width * rng.uniform(0.6, 1.4))


def impact_star(cel: Cel, center: Vec, radius: float, spikes: int = 12, rotation: float = 0.3, fill: Color = (255, 255, 255), ink: Color = (26, 18, 16)) -> None:
    back = cel.mask()
    back.polygon(star(add(center, (4, 6)), radius * 1.06, radius * 0.36, spikes, rotation))
    cel.fill_blend(back.bake(), ink, 0.9)
    front = cel.mask()
    front.polygon(star(center, radius, radius * 0.32, spikes, rotation))
    cel.fill(front.bake(), fill)


def shockwave(cel: Cel, center: Vec, radius: float, thickness: float = 8.0, color: Color = (255, 255, 255), alpha: float = 0.8) -> None:
    m = cel.mask()
    m.polygon(ellipse(center, radius * 1.25, radius * 0.85))
    inner = cel.mask()
    inner.polygon(ellipse(center, max(1.0, radius * 1.25 - thickness), max(1.0, radius * 0.85 - thickness * 0.7)))
    from PIL import ImageChops

    ring = ImageChops.subtract(m.bake(), inner.bake())
    cel.fill_blend(ring, color, alpha)


def dust_cloud(cel: Cel, center: Vec, radius: float, rng: random.Random, color: Color = (226, 214, 196), alpha: float = 0.75, blobs: int = 6) -> None:
    m = cel.mask()
    for i in range(blobs):
        ang = rng.uniform(0, math.tau)
        dist = rng.uniform(0.2, 0.9) * radius
        m.polygon(
            blob(
                add(center, polar((0, 0), ang, dist)),
                radius * rng.uniform(0.35, 0.6),
                wobble=0.22,
                phase=rng.uniform(0, 6),
                freq=3,
            )
        )
    cel.fill_blend(m.bake(), color, alpha)


def steam(cel: Cel, center: Vec, amount: float, rng: random.Random, color: Color = (255, 255, 255), alpha: float = 0.4) -> None:
    for i in range(7):
        t = (i / 7.0 + amount * 0.6) % 1.0
        rise = t * 260.0
        side = rng.uniform(-70, 70) * (0.4 + t)
        radius = 26 + 46 * t
        m = cel.mask()
        m.polygon(blob((center[0] + side, center[1] - rise), radius, wobble=0.3, phase=i * 1.3, freq=3))
        cel.fill_blend(m.bake(), color, alpha * (1.0 - t) * 0.9)


def splash(cel: Cel, center: Vec, progress: float, color: Color = (238, 248, 255), alpha: float = 0.9) -> None:
    """Water crown from a cannonball hit."""
    p = max(0.0, min(1.0, progress))
    height = 30 + 96 * p
    m = cel.mask()
    m.polygon(ellipse((center[0], center[1] + 6), 46 + 30 * p, 12 + 6 * p))
    for i in range(9):
        ang = -math.pi + math.pi * (i / 8.0)
        tip = polar((center[0], center[1]), ang, height * (0.6 + 0.4 * math.cos(ang + math.pi / 2)))
        base = polar((center[0], center[1]), ang, 30)
        m.polygon(strip([base, tip], [16 * (1 - p * 0.4), 4], segments=6))
    cel.fill_blend(m.bake(), color, alpha)
    for i in range(6):
        ang = -math.pi + math.pi * (i / 5.0)
        d = polar((center[0], center[1]), ang, height * 1.3)
        m2 = cel.mask()
        m2.polygon(ellipse(d, 6 + 6 * p, 8 + 6 * p))
        cel.fill_blend(m2.bake(), color, alpha * 0.8)


def cannonball(cel: Cel, center: Vec, radius: float, color: Color = (40, 40, 46)) -> None:
    m = cel.mask()
    m.ellipse(center, radius, radius * 0.92)
    img = m.bake()
    cel.region(img, color, shadow=(20, 20, 24), shadow_offset=(2, 2), outline=(16, 14, 16), outline_width=3)


def sparkles(cel: Cel, spots: Sequence[Vec], size: float = 16.0, color: Color = (255, 250, 220), alpha: float = 0.9) -> None:
    for p in spots:
        m = cel.mask()
        m.polygon(star(p, size, size * 0.16, spikes=4, rotation=0.0))
        m.polygon(star(p, size * 0.55, size * 0.10, spikes=4, rotation=math.pi / 4))
        cel.fill_blend(m.bake(), color, alpha)
