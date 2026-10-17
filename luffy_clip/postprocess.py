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


def _box_iter(data: bytes, start: int, end: int):
    """Yield ``(box_type, content_start, content_end)`` for ISO-BMFF boxes."""
    position = start
    while position + 8 <= end:
        size = int.from_bytes(data[position : position + 4], "big")
        box_type = data[position + 4 : position + 8]
        header = 8
        if size == 1:
            if position + 16 > end:
                return
            size = int.from_bytes(data[position + 8 : position + 16], "big")
            header = 16
        elif size == 0:
            size = end - position
        if size < header or position + size > end:
            return
        yield box_type, position + header, position + size
        position += size


def probe_mp4_header(path: Path) -> Dict[str, object]:
    """Read duration / resolution straight from the MP4 boxes (no dependencies)."""
    try:
        data = path.read_bytes()
    except OSError:
        return {}

    moov_index = data.find(b"moov")
    if moov_index < 4:
        return {}

    result: Dict[str, object] = {"container": "mp4"}
    moov_start = moov_index - 4
    moov_size = int.from_bytes(data[moov_start : moov_start + 4], "big")
    moov_end = len(data) if moov_size < 8 else min(len(data), moov_start + moov_size)

    for box_type, start, end in _box_iter(data, moov_start + 8, moov_end):
        if box_type == b"mvhd":
            _read_mvhd(data, start, end, result)
        elif box_type == b"trak":
            for sub_type, sub_start, sub_end in _box_iter(data, start, end):
                if sub_type == b"tkhd":
                    _read_tkhd(data, sub_start, sub_end, result)

    try:
        result["size_bytes"] = path.stat().st_size
    except OSError:
        pass
    return result


def _read_mvhd(data: bytes, start: int, end: int, result: Dict[str, object]) -> None:
    """Movie header: timescale + duration."""
    version = data[start]
    try:
        if version == 1:
            timescale = int.from_bytes(data[start + 20 : start + 24], "big")
            duration = int.from_bytes(data[start + 24 : start + 32], "big")
        else:
            timescale = int.from_bytes(data[start + 12 : start + 16], "big")
            duration = int.from_bytes(data[start + 16 : start + 20], "big")
    except IndexError:  # pragma: no cover - truncated box
        return
    if timescale:
        result["duration_seconds"] = round(duration / timescale, 3)
    result["timescale"] = timescale


def _read_tkhd(data: bytes, start: int, end: int, result: Dict[str, object]) -> None:
    """Track header: width / height as 16.16 fixed point (video track only)."""
    if result.get("width"):
        return
    version = data[start]
    offset = 88 if version == 1 else 76
    if start + offset + 8 > end:
        return
    width = int.from_bytes(data[start + offset : start + offset + 4], "big") / 65536
    height = int.from_bytes(data[start + offset + 4 : start + offset + 8], "big") / 65536
    if width and height:
        result["width"] = int(round(width))
        result["height"] = int(round(height))


def probe_video(path: Path) -> Dict[str, object]:
    """Return basic video metadata.

    Uses ffprobe when available; GitHub runners do not ship it any more, so we
    fall back to a dependency-free MP4 header reader (exactly enough for the
    mp4 files this project writes: faststart, so `moov` is at the front).
    """
    probe = ffprobe_binary()
    if not probe:
        return probe_mp4_header(path)
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
