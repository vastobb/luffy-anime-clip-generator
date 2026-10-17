"""Pure-python tests (no torch, no network) for the prompt + CLI layer."""

from __future__ import annotations

import pytest

from luffy_clip import cli
from luffy_clip.prompts import (
    ANIME_STYLE,
    CLIP_MAX_TOKENS,
    DEFAULT_SCENE,
    NEGATIVE_PROMPT,
    SCENES,
    build_prompt,
    clip_token_warning,
    estimate_clip_tokens,
    list_scenes,
    resolve_scene,
)


def test_scene_list_is_presets_in_order():
    assert list_scenes() == list(SCENES)
    assert DEFAULT_SCENE in SCENES
    assert len(list_scenes()) >= 5


def test_every_scene_mentions_luffy():
    for name, action in SCENES.items():
        assert "Luffy" in action, name


def test_build_prompt_appends_style():
    prompt = build_prompt(scene=DEFAULT_SCENE)
    assert prompt.startswith(resolve_scene(DEFAULT_SCENE))
    assert prompt.endswith(ANIME_STYLE)


def test_free_text_action_wins_over_scene():
    prompt = build_prompt(scene="meat_feast", action="Luffy doing a backflip")
    assert prompt.startswith("Luffy doing a backflip")
    assert "drumstick" not in prompt


def test_extra_is_kept_before_style():
    prompt = build_prompt(scene=DEFAULT_SCENE, extra="night time, rain")
    assert "night time, rain" in prompt
    assert prompt.endswith(ANIME_STYLE)


def test_unknown_scene_raises_keyerror():
    with pytest.raises(KeyError):
        resolve_scene("not-a-scene")


def test_negative_prompt_is_populated():
    assert "watermark" in NEGATIVE_PROMPT


def test_every_scene_fits_the_clip_window():
    for name in list_scenes():
        prompt = build_prompt(scene=name)
        assert estimate_clip_tokens(prompt) <= CLIP_MAX_TOKENS, name
        assert clip_token_warning(prompt) is None


def test_long_prompt_triggers_clip_token_warning():
    prompt = "Monkey D. Luffy " + "very dynamic anime action " * 30
    warning = clip_token_warning(prompt)
    assert warning is not None
    assert str(CLIP_MAX_TOKENS) in warning
    assert estimate_clip_tokens(prompt) > CLIP_MAX_TOKENS


def test_resolve_provider_auto_prefers_hf_when_token_present():
    assert cli.resolve_provider("auto", {"HF_TOKEN": "hf_x"}) == "hf"
    assert cli.resolve_provider("auto", {}) == "cpu"
    assert cli.resolve_provider("hf", {}) == "hf"
    assert cli.resolve_provider("cpu", {"HF_TOKEN": "hf_x"}) == "cpu"


def test_cli_rejects_bad_steps():
    with pytest.raises(SystemExit):
        cli.main(["--provider", "cpu", "--steps", "3"])


def test_cli_help_exits_zero():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--help"])
    assert excinfo.value.code == 0
