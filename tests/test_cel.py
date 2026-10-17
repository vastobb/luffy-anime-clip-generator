"""Cel canvas tests: mask baking, fills, ink outlines, shading crescents."""

from __future__ import annotations

import math

from luffy_clip.cel import Cel, shade, tint


def _square_mask(cel: Cel, x0: int = 20, y0: int = 20, x1: int = 80, y1: int = 60):
    m = cel.mask()
    m.polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
    return m.bake()


def test_mask_bakes_to_final_resolution():
    cel = Cel(100, 80, ss=3)
    mask = _square_mask(cel)
    assert mask.size == (100, 80)
    assert mask.getpixel((50, 40)) == 255
    assert mask.getpixel((5, 5)) == 0


def test_region_fills_base_colour_and_outline():
    cel = Cel(100, 80, ss=2, background=(255, 255, 255))
    mask = _square_mask(cel)
    cel.region(mask, (200, 40, 40), outline=(0, 0, 0), outline_width=3)
    img = cel.flatten(apply_detail=False)
    assert img.getpixel((50, 40)) == (200, 40, 40)  # interior
    edge = img.getpixel((21, 40))  # just inside the left edge
    assert sum(edge) < 200  # ink line


def test_inner_shadow_only_darkens_inside_the_mask():
    cel = Cel(100, 80, ss=1, background=(255, 255, 255))
    mask = _square_mask(cel)
    shadow = Cel.inner_shadow(mask, 6, 6)
    # the light comes from the top-left, so the second tone hugs the
    # bottom-right rim of the shape ...
    assert shadow.getpixel((78, 58)) > 0
    # ... and never leaks outside the silhouette or into the lit corner
    assert shadow.getpixel((5, 5)) == 0
    assert shadow.getpixel((21, 21)) == 0
    assert shadow.getpixel((95, 70)) == 0


def test_outline_band_is_a_band_not_a_fill():
    cel = Cel(100, 80, ss=1)
    mask = _square_mask(cel)
    band = Cel.outline_band(mask, 4)
    assert band.getpixel((50, 40)) == 0  # hollow middle
    assert band.getpixel((21, 40)) == 255  # ink on the edge


def test_erode_shrinks():
    cel = Cel(100, 80, ss=1)
    mask = _square_mask(cel)
    eroded = Cel.erode(mask, 5)
    assert eroded.getpixel((27, 27)) == 255  # 7px inside the square
    assert eroded.getpixel((21, 21)) == 0    # eaten away by the ink line


def test_shade_and_tint_helpers():
    assert shade((200, 100, 50), 0.5) == (100, 50, 25)
    assert tint((0, 0, 0), 1.0, (255, 255, 255)) == (255, 255, 255)


def test_camera_pans_zooms_and_rolls():
    from luffy_clip.vec import rotate

    cel = Cel(200, 100, ss=1)
    # 1) no camera == identity
    assert cel.map((10.0, 20.0)) == (10.0, 20.0)

    # 2) the look-at point lands exactly at the frame centre
    cel.set_camera(zoom=2.0, look_at=(40.0, 30.0))
    assert cel.map((40.0, 30.0)) == (100.0, 50.0)

    # 3) zoom scales the distance from the look-at point
    assert cel.map((50.0, 30.0)) == (120.0, 50.0)

    # 4) roll rotates around the look-at point
    cel.set_camera(zoom=1.0, look_at=(100.0, 50.0), roll=math.pi / 2)
    mapped = cel.map((120.0, 50.0))
    assert abs(mapped[0] - 100.0) < 1e-9 and abs(mapped[1] - 70.0) < 1e-9
    rotate  # silence linters about the unused import
