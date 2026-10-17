"""Tests for the dependency-free MP4 header parser (no ffprobe needed)."""

from __future__ import annotations

import struct
from pathlib import Path

from luffy_clip import postprocess


def _box(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload) + 8) + kind + payload


def _mvhd(timescale: int = 1000, duration: int = 4000) -> bytes:
    payload = b"\x00\x00\x00\x00"  # version 0 + flags
    payload += b"\x00" * 8  # creation + modification
    payload += struct.pack(">I", timescale)
    payload += struct.pack(">I", duration)
    payload += b"\x00" * (100 - len(payload))  # pad to a real mvhd body
    return _box(b"mvhd", payload)


def _tkhd(width: int = 768, height: int = 512) -> bytes:
    payload = b"\x00\x00\x00\x00"
    payload += b"\x00" * (76 - 4)  # up to the width field
    payload += struct.pack(">I", width << 16)
    payload += struct.pack(">I", height << 16)
    return _box(b"tkhd", payload)


def _synthetic_mp4(path: Path) -> None:
    ftyp = _box(b"ftyp", b"isom\x00\x00\x02\x00isomiso2")
    moov = _box(b"moov", _mvhd() + _box(b"trak", _tkhd()))
    path.write_bytes(ftyp + moov)


def test_probe_mp4_header_reads_duration_and_resolution(tmp_path):
    path = tmp_path / "clip.mp4"
    _synthetic_mp4(path)
    info = postprocess.probe_mp4_header(path)
    assert info["container"] == "mp4"
    assert info["duration_seconds"] == 4.0
    assert info["width"] == 768
    assert info["height"] == 512
    assert info["size_bytes"] == path.stat().st_size


def test_probe_mp4_header_handles_64bit_timescale(tmp_path):
    payload = b"\x01\x00\x00\x00"  # version 1 + flags
    payload += b"\x00" * 16  # creation + modification (8 bytes each)
    payload += struct.pack(">I", 24000)  # timescale
    payload += struct.pack(">Q", 48000)  # duration -> 2.0s
    payload += b"\x00" * (112 - len(payload))
    moov = _box(b"moov", _box(b"mvhd", payload))
    path = tmp_path / "v1.mp4"
    path.write_bytes(_box(b"ftyp", b"isom") + moov)
    assert postprocess.probe_mp4_header(path)["duration_seconds"] == 2.0


def test_probe_mp4_header_returns_empty_for_garbage(tmp_path):
    path = tmp_path / "nope.mp4"
    path.write_bytes(b"definitely not an mp4 file")
    assert postprocess.probe_mp4_header(path) == {}
