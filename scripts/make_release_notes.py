#!/usr/bin/env python3
"""Render the GitHub Release body for a generated clip from manifest.json."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def _resolution(video: dict) -> str | None:
    width, height = video.get("width"), video.get("height")
    return f"{width}x{height}" if width and height else None


def render(manifest: dict, *, repo: str, tag: str, run_number: str, run_url: str) -> str:
    lines: list[str] = [f"## 🏴‍☠️ Luffy anime clip — run #{run_number}", ""]
    lines += [
        "_Procedurally animated: every frame is drawn from vector math and rasterised "
        "into cel masks, then encoded with ffmpeg. No AI models._",
        "",
    ]

    reel = manifest.get("reel") or {}
    gif = reel.get("gif")
    if gif and repo and tag:
        lines += [f"![clip preview](https://github.com/{repo}/releases/download/{tag}/{gif})", ""]

    settings = manifest.get("settings") or {}
    scenes = manifest.get("scenes") or []

    if scenes:
        lines += ["| scene | drawings | duration | resolution | video |", "| --- | --- | --- | --- | --- |"]
        for entry in scenes:
            video = entry.get("video") or {}
            res = _resolution(video) or "—"
            lines.append(
                "| `{scene}` — {title} | {drawings} | {dur}s | {res} | [{f}]({url}) |".format(
                    scene=entry.get("scene", "?"),
                    title=entry.get("title", ""),
                    drawings=entry.get("drawings", "?"),
                    dur=video.get("duration_seconds", entry.get("duration_seconds", "?")),
                    res=res,
                    f=entry.get("file", "?"),
                    url=f"https://github.com/{repo}/releases/download/{tag}/{entry.get('file', '')}",
                )
            )
        lines.append("")

    reel_video = reel.get("video") or {}
    if reel_video:
        lines += [
            "**Reel** `{}` — {}x{}, {}s, {}fps".format(
                reel.get("file", "?"),
                reel_video.get("width", "?"),
                reel_video.get("height", "?"),
                reel_video.get("duration_seconds", "?"),
                settings.get("fps", "?"),
            ),
            "",
        ]

    if settings:
        lines += ["| setting | value |", "| --- | --- |"]
        for key in ("width", "height", "supersample", "draw_rate", "fps", "seed", "crf"):
            if settings.get(key) is not None:
                lines.append(f"| {key} | `{settings[key]}` |")
        lines.append("")

    sha = reel.get("sha256")
    if sha:
        lines += [f"`sha256(reel) = {sha}`", ""]
    if run_url:
        lines += [f"Workflow run: {run_url}", ""]

    lines += [
        "_Fan-made animation experiment. One Piece and Monkey D. Luffy are © "
        "Eiichiro Oda / Shueisha. Not affiliated with or endorsed by the rights holders._",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    manifest_path = Path(os.environ.get("MANIFEST", "out/manifest.json"))
    with manifest_path.open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    sys.stdout.write(
        render(
            manifest,
            repo=os.environ.get("GITHUB_REPOSITORY", ""),
            tag=os.environ.get("TAG", ""),
            run_number=os.environ.get("RUN_NUMBER", "?"),
            run_url=os.environ.get("RUN_URL", ""),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
