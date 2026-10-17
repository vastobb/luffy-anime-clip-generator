"""Prompt library for Luffy-flavoured anime clips.

Every prompt is written as a short, concrete "anime key frame" description.
Text-to-video diffusion models (AnimateDiff-Lightning, Wan 2.2, LTX-Video,
HunyuanVideo) follow visual + motion wording far better than abstract wording,
so each scene describes: subject + action + camera + background + motion.

Kept deliberately short: the SD1.5 text encoder used by the free CPU backend
only reads the first 77 CLIP tokens, so scene + style tail must fit in that
window (see ``estimate_clip_tokens`` / ``clip_token_warning``).
"""

from __future__ import annotations

from typing import List, Optional

#: Style tail appended to every scene so all clips share a consistent look.
ANIME_STYLE = (
    "2D cel-shaded anime style, vibrant colours, cinematic lighting, "
    "smooth motion, high quality anime key frame"
)

#: Things that should never show up in the output.
NEGATIVE_PROMPT = (
    "lowres, blurry, jpeg artifacts, bad anatomy, bad hands, extra fingers, "
    "missing fingers, extra limbs, deformed, disfigured, poorly drawn face, "
    "watermark, signature, text, logo, subtitles, photorealistic, photograph, "
    "3d render, live action, frozen frame, flicker, ghosting, duplicate frames"
)

#: CLIP's fixed context window (used by the SD1.5 based CPU backend).
CLIP_MAX_TOKENS = 77

#: Ready-made scene presets (ordered - the workflow exposes them in this order).
SCENES = {
    "gear_second": (
        "Monkey D. Luffy activating Gear Second on a pirate ship deck, steam "
        "bursting from his glowing pink skin, eyes glowing, crouched sprinter "
        "stance, speed lines, dust and wind, ocean behind"
    ),
    "gear_fourth": (
        "Monkey D. Luffy in Gear Fourth Boundman form, inflated muscular body "
        "coated in black haki, floating above a pirate ship deck, glowing red "
        "eyes, swirling dust, low angle camera"
    ),
    "gum_gum_pistol": (
        "Monkey D. Luffy throwing a rubber Gum-Gum Pistol punch, his arm "
        "stretching far across the frame toward the camera, straw hat flying "
        "off, pirate ship and blue ocean behind, impact shockwave"
    ),
    "sunny_figurehead": (
        "Monkey D. Luffy sitting on the lion figurehead of his pirate ship "
        "sailing a bright blue sea, straw hat in hand, wind in his red vest, "
        "seagulls, sparkling waves, wide shot"
    ),
    "sunset_silhouette": (
        "Monkey D. Luffy on a beach at sunset, straw hat raised high, orange "
        "and purple sky, waves reflecting warm light, silhouette rim glow, "
        "seagulls, slow camera tilt up"
    ),
    "meat_feast": (
        "Monkey D. Luffy grinning wide while biting a giant roasted meat "
        "drumstick on a sunny pirate ship deck, comically stretched cheeks, "
        "crumbs flying, barrels and rigging around him"
    ),
    "laughing_sky": (
        "Monkey D. Luffy laughing loudly with arms spread wide on his pirate "
        "ship deck, straw hat on head, huge blue sky, white clouds, warm sun "
        "flare, seagulls, joyful bouncy animation"
    ),
    "marine_chase": (
        "Monkey D. Luffy sprinting across a rocking ship deck while Marine "
        "battleships fire cannonballs behind him, splashes, smoke and sparks, "
        "fast panning camera, high energy action"
    ),
}

DEFAULT_SCENE = "gear_second"


def list_scenes() -> List[str]:
    """Return the scene preset names in declaration order."""
    return list(SCENES)


def resolve_scene(name: Optional[str]) -> str:
    """Return the action text for a scene preset name."""
    key = (name or DEFAULT_SCENE).strip().lower()
    if key not in SCENES:
        raise KeyError(
            "unknown scene {!r}; available scenes: {}".format(
                name, ", ".join(list_scenes())
            )
        )
    return SCENES[key]


def build_prompt(
    scene: Optional[str] = None,
    action: Optional[str] = None,
    extra: Optional[str] = None,
) -> str:
    """Compose the final positive prompt.

    ``action`` (free text) wins over ``scene`` (preset). ``extra`` is appended
    before the shared style tail.
    """
    parts: List[str] = []
    if action and action.strip():
        parts.append(action.strip())
    else:
        parts.append(resolve_scene(scene))
    if extra and extra.strip():
        parts.append(extra.strip())
    parts.append(ANIME_STYLE)
    return ", ".join(part for part in parts if part)


def estimate_clip_tokens(text: str) -> int:
    """Rough CLIP BPE token count.

    Word count underestimates BPE tokens (punctuation and rare words split), so
    each word is charged ~1.3 tokens plus two special tokens - accurate enough
    to warn about the 77 token window without importing transformers.
    """
    words = text.replace(",", " , ").split()
    return int(len(words) * 1.3) + 2


def clip_token_warning(prompt: str, limit: int = CLIP_MAX_TOKENS) -> Optional[str]:
    """Return a warning when *prompt* will be truncated by the SD1.5 encoder."""
    tokens = estimate_clip_tokens(prompt)
    if tokens <= limit:
        return None
    return (
        "prompt is ~{} CLIP tokens but the local SD1.5 backend only reads the "
        "first {}; the tail will be ignored - shorten --prompt/--scene".format(
            tokens, limit
        )
    )
