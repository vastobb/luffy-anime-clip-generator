#!/usr/bin/env python3
"""Render the GitHub Release body for a generated clip from out/manifest.json.

Used by .github/workflows/generate-luffy-clip.yml. Reads the manifest, emits
markdown (with an inline GIF preview when the gif asset is attached).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def render(manifest: dict, *, repo: str, tag: str, run_number: str, run_url: str) -> str:
    lines: list[str] = [f"## 🏴‍☠️ Luffy anime clip — run #{run_number}", ""]

    gif = manifest.get("gif")
    if gif and repo and tag:
        lines += [
            f"![clip preview](https://github.com/{repo}/releases/download/{tag}/{gif})",
            "",
        ]

    prompt = manifest.get("prompt", "")
    if prompt:
        lines += ["**Prompt**", "", f"> {prompt}", ""]

    header_fields = [
        ("backend", manifest.get("backend")),
        ("hf provider", manifest.get("hf_provider")),
        ("model", manifest.get("model")),
        ("scene", manifest.get("scene")),
        ("seed", manifest.get("seed")),
        ("segments", manifest.get("segments")),
        ("fps", manifest.get("fps")),
    ]
    video = manifest.get("video") or {}
    video_fields = [
        ("duration (s)", video.get("duration_seconds")),
        ("resolution", _resolution(video)),
        ("frame rate", video.get("frame_rate")),
        ("size (bytes)", manifest.get("file_size_bytes") or video.get("size_bytes")),
    ]
    sha = manifest.get("sha256")

    lines += ["| value | |", "| --- | --- |"]
    for label, value in header_fields + video_fields:
        if value is not None:
            lines.append(f"| {label} | `{value}` |")
    if sha:
        lines.append(f"| sha256 | `{sha[:32]}…` |")

    if run_url:
        lines += ["", f"Workflow run: {run_url}"]

    lines += [
        "",
        "_Fan-made generative experiment. One Piece and Monkey D. Luffy are © "
        "Eiichiro Oda / Shueisha. Not affiliated with or endorsed by the rights holders._",
    ]
    return "\n".join(lines) + "\n"


def _resolution(video: dict) -> str | None:
    width, height = video.get("width"), video.get("height")
    if width and height:
        return f"{width}x{height}"
    return None


def main() -> int:
    manifest_path = Path(os.environ.get("MANIFEST", "out/manifest.json"))
    with manifest_path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    body = render(
        manifest,
        repo=os.environ.get("GITHUB_REPOSITORY", ""),
        tag=os.environ.get("TAG", ""),
        run_number=os.environ.get("RUN_NUMBER", "?"),
        run_url=os.environ.get("RUN_URL", ""),
    )
    sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
