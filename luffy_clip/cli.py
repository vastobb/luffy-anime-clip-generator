"""Command line interface: procedural anime clip renderer.

    python -m luffy_clip.cli --scene all --width 1280 --height 720
    python -m luffy_clip.cli --scene gear_second --seconds 3 --supersample 3

No AI models, no downloads: the frames are drawn from vector math.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__, render
from .scenes import SCENES, get_scene, scene_names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="luffy_clip",
        description="Render a Luffy-style anime clip procedurally (math + ffmpeg, no AI).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=__version__)

    parser.add_argument(
        "--scene",
        default="all",
        choices=["all"] + scene_names(),
        help="which scene to render ('all' stitches every scene into one reel)",
    )
    parser.add_argument("--seconds", type=float, default=None, help="override the scene length")
    parser.add_argument("--out", default="out", help="output directory")

    optics = parser.add_argument_group("frame quality")
    optics.add_argument("--width", type=int, default=1280)
    optics.add_argument("--height", type=int, default=720)
    optics.add_argument(
        "--supersample",
        type=int,
        default=2,
        help="geometry is rendered at N x resolution before downscaling (crisper lines)",
    )
    optics.add_argument("--scale", type=int, default=1, help="extra ffmpeg upscale of the final mp4")
    optics.add_argument("--crf", type=int, default=15, help="x264 quality (lower = better)")

    timing = parser.add_argument_group("timing (anime is shot on twos)")
    timing.add_argument("--fps", type=int, default=24, help="playback frame rate")
    timing.add_argument("--draw-rate", type=int, default=12, help="unique drawings per second")
    timing.add_argument("--seed", type=int, default=42)

    output = parser.add_argument_group("outputs")
    output.add_argument("--gif", action=argparse.BooleanOptionalAction, default=True, help="also write GIF previews")
    output.add_argument("--gif-width", type=int, default=480)
    output.add_argument("--no-progress", action="store_true", help="quiet rendering")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    out_dir = Path(args.out)
    options = dict(
        width=int(args.width),
        height=int(args.height),
        seconds=args.seconds,
        draw_rate=int(args.draw_rate),
        fps=int(args.fps),
        seed=int(args.seed),
        supersample=max(1, int(args.supersample)),
        crf=int(args.crf),
        scale=max(1, int(args.scale)),
        gif=bool(args.gif),
        gif_width=int(args.gif_width),
        verbose=not args.no_progress,
    )
    try:
        if args.scene == "all":
            render.render_all(out_dir, **options)
        else:
            render.render_all(out_dir, scenes=[get_scene(args.scene).name], **options)
    except (KeyError, ValueError, RuntimeError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
