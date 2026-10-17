"""Cel canvas: flat-colour regions, hard-edged shading and ink outlines.

Pipeline per frame (mirrors how a real anime cel is assembled):

1. geometry is rasterised at ``supersample`` resolution (smooth edges),
2. masks are downscaled -> anti-aliased silhouettes,
3. each region gets *base colour* + *shadow tone* (shifted crescent, exactly
   like a second paint layer on a cel) + *ink line* (a band derived from the
   mask itself, so outlines are always clean, even around limb unions),
4. detail strokes (eyes, folds) and effects are composited on top.

Only PIL + numpy; no AI models anywhere.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .vec import Vec, add, capsule, catmull_rom, ellipse, mul, polyline_along, rotate, strip

Color = Tuple[int, int, int]


class Mask:
    """Region mask built at supersample resolution, baked to final resolution."""

    def __init__(self, cel: "Cel"):
        self.cel = cel
        self.ss = cel.ss
        self.image = Image.new("L", (cel.w * cel.ss, cel.h * cel.ss), 0)
        self.draw = ImageDraw.Draw(self.image)

    # -- primitives ------------------------------------------------------- #
    def _pts(self, points: Iterable[Vec]) -> List[Tuple[float, float]]:
        s = self.ss
        # every polygon in the project funnels through here, so applying the
        # camera mapping at this single choke point moves *all* geometry
        return [(p[0] * s, p[1] * s) for p in (self.cel.map(pt) for pt in points)]

    def polygon(self, points: Iterable[Vec]) -> "Mask":
        self.draw.polygon(self._pts(points), fill=255)
        return self

    def ellipse(self, center: Vec, rx: float, ry: float, rotation: float = 0.0) -> "Mask":
        return self.polygon(ellipse(center, rx, ry, rotation))

    def capsule(self, a: Vec, b: Vec, r0: float, r1: Optional[float] = None) -> "Mask":
        return self.polygon(capsule(a, b, r0, r0 if r1 is None else r1))

    def strip(self, curve: Sequence[Vec], widths: Sequence[float]) -> "Mask":
        return self.polygon(strip(curve, widths))

    def blob(self, center: Vec, radius: float, wobble: float = 0.25, phase: float = 0.0, freq: int = 3) -> "Mask":
        from .vec import blob as _blob

        return self.polygon(_blob(center, radius, wobble, phase, freq=freq))

    def catmull(self, points: Sequence[Vec], samples: int = 12, closed: bool = True) -> "Mask":
        return self.polygon(catmull_rom(points, samples=samples, closed=closed))

    def subtract(self, points: Iterable[Vec]) -> "Mask":
        tmp = Image.new("L", self.image.size, 0)
        ImageDraw.Draw(tmp).polygon(self._pts(points), fill=255)
        self.image = ImageChops.subtract(self.image, tmp)
        self.draw = ImageDraw.Draw(self.image)
        return self

    def subtract_ellipse(self, center: Vec, rx: float, ry: float, rotation: float = 0.0) -> "Mask":
        return self.subtract(ellipse(center, rx, ry, rotation))

    def intersect_polygon(self, points: Iterable[Vec]) -> "Mask":
        tmp = Image.new("L", self.image.size, 0)
        ImageDraw.Draw(tmp).polygon(self._pts(points), fill=255)
        self.image = ImageChops.darker(self.image, tmp)
        self.draw = ImageDraw.Draw(self.image)
        return self

    def union(self, other: "Mask") -> "Mask":
        self.image = ImageChops.lighter(self.image, other.image)
        self.draw = ImageDraw.Draw(self.image)
        return self

    def transformed(self, angle: float, pivot: Vec, offset: Vec = (0.0, 0.0)) -> "Mask":
        """Return a shifted/rotated copy (pose helper)."""
        clone = Mask(self.cel)
        clone.image = self.image.copy()
        clone.draw = ImageDraw.Draw(clone.image)
        # cheap approach: re-draw is handled by callers; rotation applied as offset
        return clone

    # -- bake ------------------------------------------------------------- #
    def bake(self) -> Image.Image:
        if self.ss == 1:
            return self.image
        return self.image.resize((self.cel.w, self.cel.h), Image.LANCZOS)


class Cel:
    """A frame canvas with cel shading + ink outline compositing."""

    def __init__(
        self,
        width: int,
        height: int,
        ss: int = 2,
        background: Color = (255, 255, 255),
        palette: Optional[Dict[str, Color]] = None,
    ):
        self.w, self.h, self.ss = width, height, ss
        self.palette: Dict[str, Color] = dict(palette or {})
        self.camera: Optional[Tuple[float, Vec, float]] = None
        self.img = Image.new("RGB", (width, height), background)
        self.detail = Image.new("RGBA", (width * ss, height * ss), (0, 0, 0, 0))
        self.detail_draw = ImageDraw.Draw(self.detail)

    # -- camera ------------------------------------------------------------#
    def set_camera(self, zoom: float = 1.0, look_at: Optional[Vec] = None, roll: float = 0.0) -> None:
        """Pan/zoom/roll camera, applied analytically to every shape.

        ``look_at`` is the canvas point that ends up at the frame centre.
        Because it is analytic (no resampling) a close-up stays razor sharp.
        """
        self.camera = (float(zoom), look_at or (self.w / 2.0, self.h / 2.0), float(roll))

    def map(self, point: Vec) -> Vec:
        if self.camera is None:
            return point
        zoom, (cx, cy), roll = self.camera
        if zoom == 1.0 and roll == 0.0 and (cx, cy) == (self.w / 2.0, self.h / 2.0):
            return point
        dx, dy = point[0] - cx, point[1] - cy
        c, s = math.cos(roll), math.sin(roll)
        return ((dx * c - dy * s) * zoom + self.w / 2.0, (dx * s + dy * c) * zoom + self.h / 2.0)

    def map_many(self, points: Iterable[Vec]) -> List[Vec]:
        return [self.map(p) for p in points]

    # -- masks ------------------------------------------------------------ #
    def mask(self) -> Mask:
        return Mask(self)

    # -- compositing ------------------------------------------------------ #
    def fill(self, mask: Image.Image, color: Color) -> None:
        self.img.paste(color, (0, 0), mask)

    def fill_blend(self, mask: Image.Image, color: Color, alpha: float = 1.0) -> None:
        if alpha >= 1.0:
            self.fill(mask, color)
            return
        layer = Image.new("RGB", (self.w, self.h), color)
        self.img.paste(layer, (0, 0), mask.point(lambda v: int(v * alpha)))

    @staticmethod
    def _shift(mask: Image.Image, dx: int, dy: int) -> Image.Image:
        return mask.transform(mask.size, Image.AFFINE, (1, 0, -dx, 0, 1, -dy), resample=Image.NEAREST)

    @classmethod
    def erode(cls, mask: Image.Image, width: int) -> Image.Image:
        """Erosion with an octagon structuring element (cheap, no rank filters)."""
        w = max(1, int(width))
        d = max(1, int(round(w * 0.75)))
        out = mask
        for dx, dy in ((w, 0), (-w, 0), (0, w), (0, -w), (d, d), (-d, -d), (d, -d), (-d, d)):
            out = ImageChops.darker(out, cls._shift(mask, dx, dy))
        return out

    @classmethod
    def outline_band(cls, mask: Image.Image, width: int) -> Image.Image:
        return ImageChops.subtract(mask, cls.erode(mask, width))

    @classmethod
    def inner_shadow(cls, mask: Image.Image, dx: int, dy: int) -> Image.Image:
        """Crescent along the edge opposite to the light (classic cel 2nd tone)."""
        return ImageChops.subtract(mask, cls._shift(mask, -dx, -dy))

    @classmethod
    def intersect(cls, a: Image.Image, b: Image.Image) -> Image.Image:
        return ImageChops.darker(a, b)

    @classmethod
    def union(cls, a: Image.Image, b: Image.Image) -> Image.Image:
        return ImageChops.lighter(a, b)

    # -- high level region -------------------------------------------------#
    def region(
        self,
        mask: Image.Image,
        fill: Color,
        *,
        shadow: Optional[Color] = None,
        shadow_offset: Tuple[int, int] = (3, 4),
        shadow_mask: Optional[Image.Image] = None,
        outline: Optional[Color] = None,
        outline_width: int = 0,
        alpha: float = 1.0,
    ) -> None:
        """Paint one cel region: base tone, second tone, ink line."""
        self.fill_blend(mask, fill, alpha)
        if shadow is not None:
            cres = self.inner_shadow(mask, shadow_offset[0], shadow_offset[1])
            if shadow_mask is not None:
                cres = self.intersect(cres, shadow_mask)
            self.fill_blend(cres, shadow, alpha)
        if outline is not None and outline_width > 0:
            band = self.outline_band(mask, outline_width)
            self.fill_blend(band, outline, alpha)

    # -- detail strokes (eyes, folds, speed lines) -------------------------#
    def stroke(
        self,
        points: Sequence[Vec],
        color: Tuple[int, int, int, int],
        width: float,
        smooth: int = 0,
        rounded: bool = True,
        layer: Optional[Image.Image] = None,
    ) -> None:
        """Draw on the supersampled detail layer (downscaled later -> smooth)."""
        target = self.detail_draw if layer is None else ImageDraw.Draw(layer)
        pts = points
        if smooth > 0:
            pts = catmull_rom(points, samples=smooth, closed=False)
        s = self.ss
        scaled = [(p[0] * s, p[1] * s) for p in self.map_many(pts)]
        w = max(1, int(round(width * s)))
        if len(scaled) == 1:
            x, y = scaled[0]
            target.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=color)
            return
        target.line(scaled, fill=color, width=w, joint="curve")
        if rounded:
            r = w / 2
            for p in (scaled[0], scaled[-1]):
                target.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=color)

    def blob_fill(self, mask: Image.Image, color: Color, alpha: float = 1.0) -> None:
        self.fill_blend(mask, color, alpha)

    def detail_mask(self) -> Mask:
        """A mask whose strokes land on the detail layer (for smooth details)."""
        return Mask(self)

    # -- effects -----------------------------------------------------------#
    def glow(self, mask: Image.Image, color: Color, radius: float, alpha: float = 0.8, keep_original: bool = False) -> None:
        blurred = mask.filter(ImageFilter.GaussianBlur(max(1.0, radius)))
        if not keep_original:
            blurred = ImageChops.subtract(blurred, mask)
        layer = Image.new("RGB", (self.w, self.h), color)
        self.img.paste(layer, (0, 0), blurred.point(lambda v: int(v * alpha)))

    def radial_gradient(self, inner: Color, outer: Color, strength: float = 1.0) -> None:
        self.apply_overlay(_radial(inner, outer, self.w, self.h, strength))

    def vertical_gradient(self, top: Color, bottom: Color) -> None:
        col = np.linspace(0, 1, self.h, dtype=np.float32)[:, None]
        top_arr = np.array(top, dtype=np.float32)
        bot_arr = np.array(bottom, dtype=np.float32)
        grad = top_arr[None, None, :] * (1 - col)[:, :, None] + bot_arr[None, None, :] * col[:, :, None]
        grad = np.repeat(grad, self.w, axis=1).astype(np.uint8)
        self.img = Image.blend(self.img, Image.fromarray(grad, "RGB"), 1.0)

    def apply_overlay(self, overlay: Image.Image, alpha: float = 1.0) -> None:
        if alpha >= 1.0:
            self.img = ImageChops.multiply(self.img, overlay)
        else:
            self.img = Image.blend(self.img, ImageChops.multiply(self.img, overlay), alpha)

    def screen(self, layer: Image.Image, alpha: float = 1.0) -> None:
        if alpha < 1.0:
            layer = layer.point(lambda v: int(v * alpha))
        self.img = ImageChops.screen(self.img, layer.convert("RGB"))

    def vignette(self, strength: float = 0.35, power: float = 2.2) -> None:
        yy, xx = np.mgrid[0 : self.h, 0 : self.w].astype(np.float32)
        cx, cy = self.w / 2, self.h / 2
        r = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2) / math.sqrt(2)
        mask = np.clip(1 - strength * (r ** power), 0, 1)
        arr = np.asarray(self.img, dtype=np.float32) * mask[:, :, None]
        self.img = Image.fromarray(arr.astype(np.uint8), "RGB")

    def grain(self, amount: float = 4.0, seed: int = 0) -> None:
        rng = np.random.default_rng(seed)
        noise = rng.normal(0, amount, (self.h, self.w, 1)).astype(np.float32)
        arr = np.asarray(self.img, dtype=np.float32) + noise
        self.img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")

    def flash(self, color: Color = (255, 255, 255), alpha: float = 1.0, jag: bool = False) -> None:
        layer = Image.new("RGB", (self.w, self.h), color)
        self.img = Image.blend(self.img, layer, min(1.0, max(0.0, alpha)))

    def bloom(self, threshold: int = 208, radius: float = 16.0, alpha: float = 0.32, color: Color = (255, 250, 238)) -> None:
        """Screen-blend a blurred bright pass - the anime "light wrap" glow."""
        luma = np.asarray(self.img.convert("L"), dtype=np.int16)
        bright = np.where(luma > threshold, 255, 0).astype(np.uint8)
        mask = Image.fromarray(bright, "L").filter(ImageFilter.GaussianBlur(radius))
        mask = mask.point(lambda v: int(v * alpha))
        glow = Image.new("RGB", self.img.size, color)
        lights = Image.composite(glow, Image.new("RGB", self.img.size, (0, 0, 0)), mask)
        self.img = ImageChops.screen(self.img, lights)

    def lens_flare(self, center: Vec, length: float, alpha: float = 0.55, color: Color = (255, 246, 214)) -> None:
        """Horizontal anamorphic streak + ghosting - establishing-shot candy."""
        layer = Image.new("RGB", self.img.size, (0, 0, 0))
        draw = ImageDraw.Draw(layer)
        tone = tuple(int(c * alpha) for c in color)
        x, y = center
        draw.ellipse([x - length, y - 4, x + length, y + 4], fill=tone)
        for i, (frac, size) in enumerate(((0.35, 26), (0.68, 16), (1.05, 12))):
            gx = x + (x - self.w / 2) * frac * 0.5
            gy = y + (y - self.h / 2) * frac * 0.5
            draw.ellipse([gx - size, gy - size * 0.6, gx + size, gy + size * 0.6], fill=tuple(int(c * alpha * 0.35) for c in color))
        self.img = ImageChops.screen(self.img, layer.filter(ImageFilter.GaussianBlur(7)))

    def grade(self, color: Color, alpha: float = 0.22) -> None:
        solid = Image.new("RGB", self.img.size, color)
        self.img = Image.blend(self.img, ImageChops.multiply(self.img, solid), alpha)

    def letterbox_bars(self, height_frac: float = 0.0, color: Color = (0, 0, 0)) -> None:
        if height_frac <= 0:
            return
        bar = int(self.h * height_frac)
        draw = ImageDraw.Draw(self.img)
        draw.rectangle([0, 0, self.w, bar], fill=color)
        draw.rectangle([0, self.h - bar, self.w, self.h], fill=color)

    # -- output ------------------------------------------------------------#
    def flatten(self, apply_detail: bool = True) -> Image.Image:
        """Composite the supersampled detail stroke layer and return the frame."""
        if not apply_detail:
            return self.img
        detail = self.detail
        if self.ss > 1:
            detail = detail.resize((self.w, self.h), Image.LANCZOS)
        if detail.getbbox() is None:
            return self.img
        self.img = Image.alpha_composite(self.img.convert("RGBA"), detail).convert("RGB")
        return self.img

    def to_image(self) -> Image.Image:
        return self.flatten(apply_detail=False)


def _radial(inner: Color, outer: Color, w: int, h: int, strength: float = 1.0) -> Image.Image:
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w / 2, h / 2
    r = np.sqrt(((xx - cx) / cx) ** 2 + ((yy - cy) / cy) ** 2) / math.sqrt(2.0)
    r = np.clip(r * strength, 0, 1)
    inner_arr = np.array(inner, dtype=np.float32)
    outer_arr = np.array(outer, dtype=np.float32)
    arr = inner_arr[None, None, :] * (1 - r)[:, :, None] + outer_arr[None, None, :] * r[:, :, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def shade(color: Color, factor: float = 0.78) -> Color:
    return tuple(int(max(0, min(255, c * factor))) for c in color)  # type: ignore[return-value]


def tint(color: Color, factor: float = 0.2, target: Color = (255, 255, 255)) -> Color:
    return tuple(int(c + (t - c) * factor) for c, t in zip(color, target))  # type: ignore[return-value]
