"""ffmpeg helpers: frames -> mp4, concat, gif preview, ffprobe metadata."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Sequence


def ffmpeg_binary() -> str:
    """System ffmpeg if present, otherwise the bundled imageio-ffmpeg binary."""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover - depends on environment
        raise RuntimeError(
            "ffmpeg is required but was not found on PATH (ubuntu-latest has it "
            "preinstalled, or `pip install imageio-ffmpeg`)"
        ) from exc


def ffprobe_binary() -> Optional[str]:
    return shutil.which("ffprobe")


def _run(cmd: Sequence[object]) -> None:
    cmd = [str(part) for part in cmd]
    process = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    if process.returncode != 0:
        tail = "\n".join((process.stdout or "").splitlines()[-40:])
        raise RuntimeError(
            "command failed (exit {}): {}\n{}".format(
                process.returncode, " ".join(cmd), tail
            )
        )


def _even_scale_filter(scale: int) -> str:
    return (
        "scale=trunc(iw*{0}/2)*2:trunc(ih*{0}/2)*2:flags=lanczos,format=yuv420p".format(
            scale
        )
    )


def frames_to_mp4(
    frames_dir: Path, out_mp4: Path, *, fps: int = 8, scale: int = 2, crf: int = 18
) -> Path:
    """Encode a ``frame_%04d.png`` sequence into a browser-friendly MP4."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            ffmpeg_binary(),
            "-y",
            "-framerate",
            fps,
            "-i",
            frames_dir / "frame_%04d.png",
            "-vf",
            _even_scale_filter(scale),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            crf,
            "-movflags",
            "+faststart",
            out_mp4,
        ]
    )
    return out_mp4


def normalize_mp4(
    src: Path, dst: Path, *, scale: int = 1, fps: Optional[int] = None, crf: int = 20
) -> Path:
    """Re-encode a raw provider MP4 (yuv420p + faststart + optional upscale/fps)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    filters = [_even_scale_filter(scale)]
    if fps:
        filters.append("fps={}".format(fps))
    _run(
        [
            ffmpeg_binary(),
            "-y",
            "-i",
            src,
            "-vf",
            ",".join(filters),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            crf,
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            dst,
        ]
    )
    return dst


def concat_mp4(parts: List[Path], out_mp4: Path) -> Path:
    """Concatenate MP4 segments produced with identical codec settings."""
    if not parts:
        raise ValueError("nothing to concatenate")
    if len(parts) == 1:
        shutil.copyfile(parts[0], out_mp4)
        return out_mp4
    listing = out_mp4.parent / "concat_list.txt"
    listing.write_text(
        "\n".join("file '{}'".format(part.resolve()) for part in parts) + "\n",
        encoding="utf-8",
    )
    _run(
        [
            ffmpeg_binary(),
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            listing,
            "-c",
            "copy",
            out_mp4,
        ]
    )
    return out_mp4


def mp4_to_gif(
    src: Path, dst: Path, *, fps: int = 8, width: int = 480, loops: int = 0
) -> Path:
    """Small looping GIF preview (renders inline on GitHub release pages)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    filters = (
        "fps={fps},scale={width}:-1:flags=lanczos,"
        "split[a][b];[a]palettegen[p];[b][p]paletteuse"
    ).format(fps=fps, width=width)
    _run(
        [
            ffmpeg_binary(),
            "-y",
            "-i",
            src,
            "-vf",
            filters,
            "-loop",
            loops,
            dst,
        ]
    )
    return dst


def probe_video(path: Path) -> Dict[str, object]:
    """Return basic video metadata (empty dict when ffprobe is unavailable)."""
    probe = ffprobe_binary()
    if not probe:
        return {}
    process = subprocess.run(
        [
            probe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,nb_frames:format=duration,size,format_name",
            "-of",
            "json",
            str(path),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if process.returncode != 0:
        return {}
    try:
        data = json.loads(process.stdout or "{}")
    except json.JSONDecodeError:
        return {}
    stream = (data.get("streams") or [{}])[0]
    fmt = data.get("format") or {}
    try:
        duration = round(float(fmt.get("duration") or 0.0), 3)
    except (TypeError, ValueError):
        duration = None
    try:
        size_bytes = int(fmt.get("size") or 0)
    except (TypeError, ValueError):
        size_bytes = None
    return {
        "container": fmt.get("format_name"),
        "duration_seconds": duration,
        "width": stream.get("width"),
        "height": stream.get("height"),
        "frame_rate": stream.get("r_frame_rate"),
        "frame_count": stream.get("nb_frames"),
        "size_bytes": size_bytes,
    }
