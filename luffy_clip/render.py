"""Frame renderer + encoder: math -> PNG frames -> mp4/gif via ffmpeg.

Anime timing is baked in: drawings are rendered at ``draw_rate`` (12/s by
default) and the mp4 is encoded at ``fps`` (24/s), which is exactly how classic
2D animation is shot "on twos" - each drawing is held for two frames.
"""

from __future__ import annotations

import hashlib
import json
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import postprocess
from .cel import Cel
from .scenes import SCENES, get_scene, scene_names


def _stable_hash(text: str) -> int:
    """Deterministic across processes (Python's str hash() is salted)."""
    return int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_frames(
    scene_name: str,
    work_dir: Path,
    *,
    width: int,
    height: int,
    seconds: Optional[float] = None,
    draw_rate: int = 12,
    seed: int = 42,
    supersample: int = 2,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Draw every unique drawing of a scene to ``work_dir/<scene>_frames``."""
    scene = get_scene(scene_name)
    duration = float(seconds or scene.seconds)
    drawings = max(2, int(round(duration * draw_rate)))
    frames_dir = Path(work_dir) / "{}_frames".format(scene_name)
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)

    for index in range(drawings):
        t = index / drawings
        rng = random.Random((seed * 1_000_003) ^ (index * 7919) ^ _stable_hash(scene_name))
        cel = Cel(width, height, ss=supersample, background=(255, 255, 255))
        scene.render(cel, t, index, rng)
        cel.flatten().save(frames_dir / "frame_{:04d}.png".format(index))
        if verbose and (index % 12 == 0 or index == drawings - 1):
            print("  drawing {}/{} (t={:.2f})".format(index + 1, drawings, t), flush=True)

    return {
        "scene": scene_name,
        "title": scene.title,
        "loop": scene.loop,
        "drawings": drawings,
        "seconds": round(drawings / float(draw_rate), 3),
        "frames_dir": str(frames_dir),
    }


def render_scene(
    scene_name: str,
    out_dir: Path,
    *,
    width: int = 1280,
    height: int = 720,
    seconds: Optional[float] = None,
    draw_rate: int = 12,
    fps: int = 24,
    seed: int = 42,
    supersample: int = 2,
    crf: int = 15,
    scale: int = 1,
    gif: bool = True,
    gif_width: int = 480,
    verbose: bool = True,
) -> Dict[str, Any]:
    """Render one scene to mp4 (+ optional gif) and return its manifest entry."""
    out_dir = Path(out_dir)
    info = render_frames(
        scene_name,
        out_dir / "_work",
        width=width,
        height=height,
        seconds=seconds,
        draw_rate=draw_rate,
        seed=seed,
        supersample=supersample,
        verbose=verbose,
    )
    mp4 = out_dir / "{}.mp4".format(scene_name)
    postprocess.frames_to_mp4(
        Path(info["frames_dir"]),
        mp4,
        fps=draw_rate,
        out_fps=fps,
        scale=scale,
        crf=crf,
    )
    if verbose:
        print("  encoded {}".format(mp4), flush=True)
    entry: Dict[str, Any] = {
        "scene": scene_name,
        "title": info["title"],
        "loop": info["loop"],
        "drawings": info["drawings"],
        "draw_rate": draw_rate,
        "fps": fps,
        "duration_seconds": info["seconds"],
        "video": postprocess.probe_video(mp4),
        "file": mp4.name,
        "file_size_bytes": mp4.stat().st_size,
        "sha256": _sha256(mp4),
    }
    if gif:
        gif_path = out_dir / "{}.gif".format(scene_name)
        postprocess.mp4_to_gif(mp4, gif_path, fps=draw_rate, width=gif_width)
        entry["gif"] = gif_path.name
        entry["gif_size_bytes"] = gif_path.stat().st_size
    return entry


def render_all(
    out_dir: Path,
    *,
    scenes: Optional[List[str]] = None,
    gif: bool = True,
    verbose: bool = True,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Render several scenes, then concat them into one reel (mp4 + gif)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    names = list(scenes or scene_names())
    entries: List[Dict[str, Any]] = []
    for name in names:
        print("scene: {}".format(name), flush=True)
        entries.append(render_scene(name, out_dir, gif=gif, verbose=verbose, **kwargs))

    parts = [out_dir / entry["file"] for entry in entries]
    reel = out_dir / "luffy_reel.mp4"
    if len(parts) > 1:
        postprocess.concat_mp4(parts, reel)
    else:
        shutil.copyfile(parts[0], reel)
    reel_entry: Dict[str, Any] = {
        "file": reel.name,
        "video": postprocess.probe_video(reel),
        "file_size_bytes": reel.stat().st_size,
        "sha256": _sha256(reel),
    }
    if gif:
        reel_gif = out_dir / "luffy_reel.gif"
        postprocess.mp4_to_gif(reel, reel_gif, fps=kwargs.get("fps", 24) // 2 or 12, width=kwargs.get("gif_width", 480))
        reel_entry["gif"] = reel_gif.name
        reel_entry["gif_size_bytes"] = reel_gif.stat().st_size

    manifest = {
        "tool": "luffy-anime-clip-generator",
        "tool_version": "2.0.0",
        "pipeline": "procedural-cel-animation (math + PIL masks, ffmpeg encode) - no AI models",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "settings": {
            key: value
            for key, value in kwargs.items()
            if key in ("width", "height", "draw_rate", "fps", "seed", "supersample", "crf", "scale", "gif_width")
        },
        "scenes": entries,
        "reel": reel_entry,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if verbose:
        video = reel_entry["video"]
        print(
            "reel: {}  {}x{}  {}s  {:.1f} MB  ({} scenes)".format(
                reel,
                video.get("width", "?"),
                video.get("height", "?"),
                video.get("duration_seconds", "?"),
                reel_entry["file_size_bytes"] / 1e6,
                len(entries),
            ),
            flush=True,
        )
        print("manifest: {}".format(manifest_path), flush=True)
    return manifest
