"""Episode tests: shot structure, hard cuts, camera maths."""

from __future__ import annotations

import random

import pytest

from luffy_clip.cel import Cel
from luffy_clip.episode import EPISODE_SECONDS, SHOTS, _shot_at, render_episode
from luffy_clip.scenes import SCENES


def test_episode_duration_matches_registered_scene():
    assert SCENES["episode"].seconds == pytest.approx(EPISODE_SECONDS, abs=0.05)


def test_shot_timeline_covers_the_episode():
    seen = []
    for step in range(0, 100):
        index, _, local = _shot_at(step / 100 * EPISODE_SECONDS)
        assert 0.0 <= local <= 1.0
        if not seen or seen[-1] != index:
            seen.append(index)
    assert seen == list(range(len(SHOTS))), "shots must play in order, without gaps"


def test_every_shot_renders_something(tmp_path):
    """Each shot must produce a non-blank frame (guards staging regressions)."""
    times = []
    acc = 0.0
    for duration, _ in SHOTS:
        times.append((acc + duration * 0.6) / EPISODE_SECONDS)
        acc += duration
    for index, t in enumerate(times):
        cel = Cel(160, 90, ss=1, background=(0, 0, 0))
        render_episode(cel, t, index, random.Random(50 + index))
        img = cel.flatten()
        colours = img.getcolors(maxcolors=100000)
        assert colours and len(colours) > 20, "shot {} looks blank".format(index + 1)


def test_cuts_are_hard_cuts():
    """The last frame of a shot and the first frame of the next must not blend."""
    boundaries = []
    acc = 0.0
    for duration, _ in SHOTS[:-1]:
        acc += duration
        boundaries.append(acc / EPISODE_SECONDS)

    def frame(t: float, seed: int) -> bytes:
        cel = Cel(128, 72, ss=1, background=(0, 0, 0))
        render_episode(cel, t, seed, random.Random(seed))
        return cel.flatten().tobytes()

    def delta(a: bytes, b: bytes) -> float:
        return sum(abs(x - y) for x, y in zip(a, b)) / len(a)

    for i, boundary in enumerate(boundaries):
        before = frame(boundary - 0.004, 1)
        after = frame(boundary + 0.004, 2)
        assert delta(before, after) > 6.0, "shot {} -> {} is not a visible cut".format(i + 1, i + 2)


def test_silhouette_shot_uses_rim_light():
    """The ending shot is a silhouette: mostly dark pixels with a bright rim."""
    from luffy_clip.vec import ease_out_cubic  # noqa: F401  (keeps import graph honest)

    cel = Cel(160, 90, ss=1)
    render_episode(cel, 0.97, 5, random.Random(3))
    img = cel.flatten()
    pixels = list(img.getdata())
    dark = sum(1 for r, g, b in pixels if r + g + b < 260)
    bright = sum(1 for r, g, b in pixels if r + g + b > 620)
    assert dark > len(pixels) * 0.05  # the character reads as a dark shape
    assert bright > len(pixels) * 0.02  # the sun / rim keeps it from going flat
