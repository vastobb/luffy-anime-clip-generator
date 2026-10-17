"""Command line interface: ``python -m luffy_clip.cli``.

Examples
--------
Free, no-secret CPU run (slow, small clip):
    python -m luffy_clip.cli --provider cpu --scene gear_second --segments 2

Hosted, best-quality run through the HF router (needs HF_TOKEN):
    python -m luffy_clip.cli --provider hf --hf-provider fal-ai \\
        --model Wan-AI/Wan2.2-TI2V-5B --scene marine_chase
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import __version__, postprocess, providers
from .prompts import DEFAULT_SCENE, NEGATIVE_PROMPT, build_prompt, list_scenes


def resolve_provider(requested: str, env: Optional[Dict[str, str]] = None) -> str:
    """``auto`` -> hosted inference when HF_TOKEN exists, otherwise free CPU."""
    env = os.environ if env is None else env
    if requested in ("hf", "cpu"):
        return requested
    return "hf" if env.get("HF_TOKEN") else "cpu"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="luffy_clip",
        description="Generate a Luffy-style anime clip with a generative video model.",
    )
    parser.add_argument("--version", action="version", version=__version__)

    content = parser.add_argument_group("clip content")
    content.add_argument(
        "--scene",
        choices=list_scenes(),
        default=DEFAULT_SCENE,
        help="scene preset (default: %(default)s)",
    )
    content.add_argument(
        "--prompt",
        default="",
        help="free-text action override, wins over --scene",
    )
    content.add_argument(
        "--negative-prompt",
        default=None,
        help="override the built-in negative prompt",
    )

    backend = parser.add_argument_group("backend selection")
    backend.add_argument(
        "--provider",
        choices=("auto", "hf", "cpu"),
        default="auto",
        help="auto = HF router when HF_TOKEN is set, else CPU diffusion (default: %(default)s)",
    )
    backend.add_argument(
        "--hf-provider",
        choices=("fal-ai", "replicate", "wavespeed"),
        default=providers.DEFAULT_HF_PROVIDER,
        help="Hugging Face inference provider to route through (default: %(default)s)",
    )
    backend.add_argument(
        "--model",
        default=providers.DEFAULT_HF_MODEL,
        help="text-to-video model id on the Hub (default: %(default)s)",
    )
    backend.add_argument(
        "--base-model",
        default=providers.DEFAULT_CPU_BASE_MODEL,
        help="anime SD1.5 checkpoint for the CPU backend (default: %(default)s)",
    )
    backend.add_argument(
        "--motion-adapter",
        default=providers.DEFAULT_MOTION_ADAPTER,
        help="AnimateDiff-Lightning repo for the CPU backend (default: %(default)s)",
    )

    sampling = parser.add_argument_group("sampling")
    sampling.add_argument("--seed", type=int, default=42)
    sampling.add_argument(
        "--segments", type=int, default=1, help="number of consecutive clips to render"
    )
    sampling.add_argument("--fps", type=int, default=8, help="playback fps")
    sampling.add_argument(
        "--frames", type=int, default=16, help="frames per segment (CPU backend)"
    )
    sampling.add_argument("--width", type=int, default=384)
    sampling.add_argument("--height", type=int, default=256)
    sampling.add_argument(
        "--steps",
        type=int,
        default=4,
        choices=list(providers.CPU_STEPS_CHOICES),
        help="denoising steps for the CPU backend (default: %(default)s)",
    )
    sampling.add_argument(
        "--guidance", type=float, default=1.2, help="guidance scale (CPU backend)"
    )
    sampling.add_argument(
        "--hf-frames",
        type=float,
        default=None,
        help="num_frames passed to the hosted model (only if set)",
    )
    sampling.add_argument(
        "--hf-steps",
        type=int,
        default=None,
        help="num_inference_steps passed to the hosted model (only if set)",
    )
    sampling.add_argument(
        "--hf-guidance",
        type=float,
        default=None,
        help="guidance_scale passed to the hosted model (only if set)",
    )

    output = parser.add_argument_group("output")
    output.add_argument("--out", default="out/luffy_clip.mp4", help="output mp4 path")
    output.add_argument(
        "--workdir",
        default=None,
        help="scratch directory for frames/raw segments (default: <out dir>/_work)",
    )
    output.add_argument(
        "--scale",
        type=int,
        default=2,
        help="upscale factor applied by ffmpeg (default: %(default)s)",
    )
    output.add_argument("--crf", type=int, default=18, help="x264 quality (lower = better)")
    output.add_argument(
        "--gif",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="also render a small GIF preview",
    )
    output.add_argument("--gif-width", type=int, default=480)
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _runner_info() -> Dict[str, str]:
    keys = (
        "GITHUB_REPOSITORY",
        "GITHUB_RUN_ID",
        "GITHUB_RUN_NUMBER",
        "GITHUB_SERVER_URL",
        "GITHUB_SHA",
        "GITHUB_WORKFLOW",
    )
    return {key.lower(): os.environ[key] for key in keys if key in os.environ}


def run(args: argparse.Namespace) -> Dict[str, Any]:
    out_path = Path(args.out)
    work_dir = Path(args.workdir) if args.workdir else out_path.parent / "_work"
    segments = max(1, int(args.segments))

    prompt = build_prompt(scene=args.scene, action=args.prompt or None)
    negative = args.negative_prompt if args.negative_prompt is not None else NEGATIVE_PROMPT
    provider = resolve_provider(args.provider)

    manifest: Dict[str, Any] = {
        "tool": "luffy-anime-clip-generator",
        "tool_version": __version__,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "provider": provider,
        "scene": "custom" if (args.prompt or "").strip() else args.scene,
        "prompt": prompt,
        "negative_prompt": negative,
        "seed": int(args.seed),
        "segments": segments,
        "fps": int(args.fps),
        "runner": _runner_info(),
    }

    print("provider : {}".format(provider))
    print("prompt   : {}".format(prompt))
    print("output   : {}".format(out_path))

    if provider == "hf":
        raw_parts: List[Path] = []
        for segment in range(segments):
            part = work_dir / "hf_raw_segment{:02d}.mp4".format(segment)
            info = providers.generate_with_hf_router(
                prompt,
                part,
                model=args.model,
                provider=args.hf_provider,
                negative_prompt=negative,
                seed=int(args.seed) + segment,
                num_frames=args.hf_frames,
                num_inference_steps=args.hf_steps,
                guidance_scale=args.hf_guidance,
            )
            print(
                "segment {}/{}: {:.1f} MB -> {}".format(
                    segment + 1, segments, info["bytes"] / 1e6, part
                )
            )
            raw_parts.append(part)
        merged = work_dir / "hf_merged.mp4"
        postprocess.concat_mp4(raw_parts, merged)
        postprocess.normalize_mp4(
            merged, out_path, scale=max(1, int(args.scale)), crf=int(args.crf)
        )
        manifest.update(
            {
                "backend": "hf-router",
                "hf_provider": args.hf_provider,
                "model": args.model,
                "provider_segments": len(raw_parts),
            }
        )
    else:
        frames_dir = work_dir / "frames"
        if frames_dir.exists():
            shutil.rmtree(frames_dir)
        cpu_info: Dict[str, Any] = {}
        for segment in range(segments):
            cpu_info = providers.generate_with_cpu(
                prompt,
                frames_dir,
                base_model=args.base_model,
                motion_adapter_repo=args.motion_adapter,
                steps=int(args.steps),
                num_frames=int(args.frames),
                width=int(args.width),
                height=int(args.height),
                guidance_scale=float(args.guidance),
                seed=int(args.seed) + segment,
                negative_prompt=negative,
                frame_offset=segment * int(args.frames),
            )
            print("segment {}/{} rendered".format(segment + 1, segments))
        postprocess.frames_to_mp4(
            frames_dir,
            out_path,
            fps=int(args.fps),
            scale=max(1, int(args.scale)),
            crf=int(args.crf),
        )
        manifest.update({"backend": "cpu-diffusion", "cpu": cpu_info})
        manifest["model"] = cpu_info.get("base_model", args.base_model)

    gif_path: Optional[Path] = None
    if args.gif:
        gif_path = out_path.with_suffix(".gif")
        postprocess.mp4_to_gif(
            out_path, gif_path, fps=int(args.fps), width=int(args.gif_width)
        )

    manifest["video"] = postprocess.probe_video(out_path)
    manifest["file_size_bytes"] = out_path.stat().st_size
    manifest["sha256"] = _sha256(out_path)
    manifest["gif"] = gif_path.name if gif_path else None

    manifest_path = out_path.parent / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    video = manifest["video"]
    print("")
    print("done: {}".format(out_path))
    print(
        "      {}x{} @ {}fps, {}s, {:.1f} MB".format(
            video.get("width", "?"),
            video.get("height", "?"),
            args.fps,
            video.get("duration_seconds", "?"),
            manifest["file_size_bytes"] / 1e6,
        )
    )
    print("manifest: {}".format(manifest_path))
    return manifest


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        run(args)
    except (KeyError, ValueError, RuntimeError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
