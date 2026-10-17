"""Renderer/CLI plumbing tests (no ffmpeg needed)."""

from __future__ import annotations

from pathlib import Path

from luffy_clip import render
from luffy_clip.cli import build_parser


def test_frame_count_matches_draw_rate(tmp_path: Path):
    info = render.render_frames(
        "gear_second",
        tmp_path,
        width=96,
        height=54,
        seconds=0.5,
        draw_rate=6,
        supersample=1,
        verbose=False,
    )
    frames = sorted(Path(info["frames_dir"]).glob("frame_*.png"))
    assert len(frames) == 3
    assert info["seconds"] == 0.5


def test_frames_are_unique_drawings(tmp_path: Path):
    info = render.render_frames(
        "marine_chase",
        tmp_path,
        width=96,
        height=54,
        seconds=0.4,
        draw_rate=5,
        supersample=1,
        verbose=False,
    )
    frames = sorted(Path(info["frames_dir"]).glob("frame_*.png"))
    blobs = [f.read_bytes() for f in frames]
    assert len(set(blobs)) == len(blobs), "frames repeated - animation would look frozen"


def test_cli_defaults():
    args = build_parser().parse_args([])
    assert args.scene == "all"
    assert args.fps == 24
    assert args.draw_rate == 12
    assert args.supersample == 2
    assert args.width == 1280 and args.height == 720
    assert args.gif is True


def test_cli_accepts_scene_and_quality_flags():
    args = build_parser().parse_args(
        ["--scene", "gum_gum_pistol", "--supersample", "3", "--seconds", "2.5", "--no-gif"]
    )
    assert args.scene == "gum_gum_pistol"
    assert args.supersample == 3
    assert args.seconds == 2.5
    assert args.gif is False
