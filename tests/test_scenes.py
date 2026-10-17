"""Scene smoke tests: every scene must render real (non-blank) frames fast."""

from __future__ import annotations

import random

import pytest

from luffy_clip.cel import Cel
from luffy_clip.scenes import SCENES, get_scene, scene_names


@pytest.mark.parametrize("name", scene_names())
def test_scene_renders_a_non_blank_frame(name):
    scene = get_scene(name)
    cel = Cel(192, 108, ss=1, background=(255, 255, 255))
    scene.render(cel, 0.37, 3, random.Random(1))
    img = cel.flatten()
    colours = img.getcolors(maxcolors=100000)
    assert img.size == (192, 108)
    assert colours is not None and len(colours) > 25, "scene looks blank: {}".format(name)


@pytest.mark.parametrize("name", scene_names())
def test_scene_animation_changes_over_time(name):
    scene = get_scene(name)
    frames = []
    for index, t in enumerate((0.05, 0.5)):
        cel = Cel(160, 90, ss=1, background=(255, 255, 255))
        scene.render(cel, t, index, random.Random(2 + index))
        frames.append(cel.flatten().tobytes())
    assert frames[0] != frames[1], "scene is static: {}".format(name)


def test_scene_metadata_is_sane():
    for name, scene in SCENES.items():
        assert scene.seconds > 0
        assert scene.title
        assert scene.name == name


def test_unknown_scene_raises():
    with pytest.raises(KeyError):
        get_scene("not-a-scene")


@pytest.mark.parametrize("name", scene_names())
def test_loop_scenes_are_seamless(name):
    """The wrap-around step must not be an outlier compared to normal steps."""
    scene = get_scene(name)
    if not scene.loop:
        pytest.skip("scene is a one-shot")

    def delta(a: bytes, b: bytes) -> float:
        return sum(abs(x - y) for x, y in zip(a, b)) / len(a)

    drawings = 12
    frames = []
    for index in range(drawings):
        cel = Cel(96, 54, ss=1)
        scene.render(cel, index / drawings, index, random.Random(5 + index))
        frames.append(cel.to_image().tobytes())
    seam = delta(frames[-1], frames[0])
    biggest_step = max(delta(frames[i], frames[i + 1]) for i in range(drawings - 1))
    assert seam <= biggest_step * 2.0 + 1.0, "loop seam {} vs step {}".format(seam, biggest_step)
