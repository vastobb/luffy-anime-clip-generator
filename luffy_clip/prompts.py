"""Prompt library for Luffy-flavoured anime clips.

Every prompt is written as a short, concrete "anime key frame" description.
Text-to-video diffusion models (AnimateDiff-Lightning, Wan 2.2, LTX-Video,
HunyuanVideo) follow visual + motion wording far better than abstract wording,
so each scene describes: subject + action + camera + background + motion.
"""

from __future__ import annotations

from typing import List, Optional

#: Style tail appended to every scene so all clips share a consistent look.
ANIME_STYLE = (
    "2D anime style, cel-shaded animation, Eiichiro Oda inspired art style, "
    "clean line art, vibrant saturated colours, cinematic lighting, dynamic "
    "camera work, smooth fluid motion, high quality anime key frame"
)

#: Things that should never show up in the output.
NEGATIVE_PROMPT = (
    "lowres, blurry, jpeg artifacts, bad anatomy, bad hands, extra fingers, "
    "missing fingers, extra limbs, deformed, disfigured, poorly drawn face, "
    "watermark, signature, text, logo, subtitles, photorealistic, photograph, "
    "3d render, live action, frozen frame, flicker, ghosting, duplicate frames"
)

#: Ready-made scene presets (ordered - the workflow exposes them in this order).
SCENES = {
    "gear_second": (
        "Monkey D. Luffy activating Gear Second on a wooden pirate ship deck, "
        "steam bursting from his body, skin glowing hot pink, eyes glowing, "
        "crouched low in a sprinter's stance, speed lines and dust kicked up, "
        "dramatic wind, ocean in the background"
    ),
    "gear_fourth": (
        "Monkey D. Luffy in Gear Fourth Boundman form, muscular inflated body "
        "coated in glossy black haki, floating above a pirate ship deck, fists "
        "clenched, glowing red eyes, debris and dust swirling in the air, "
        "epic low angle camera push-in"
    ),
    "gum_gum_pistol": (
        "Monkey D. Luffy throwing a rubber Gum-Gum Pistol punch, his stretched "
        "arm rocketing across the frame toward the camera, straw hat flying "
        "off, pirate ship and blue ocean behind him, impact shockwave, dynamic "
        "foreshortening"
    ),
    "sunny_figurehead": (
        "Monkey D. Luffy sitting cross-legged on the lion figurehead of his "
        "pirate ship while it sails a bright blue sea, straw hat in hand, wind "
        "blowing his red vest and black hair, seagulls circling, sparkling "
        "waves, wide establishing shot"
    ),
    "sunset_silhouette": (
        "Monkey D. Luffy standing on a beach at sunset, straw hat raised high "
        "in one hand, orange and purple sky, waves reflecting warm sunlight, "
        "silhouette rim light, seagulls, slow camera tilt up"
    ),
    "meat_feast": (
        "Monkey D. Luffy grinning wide while biting a giant roasted meat "
        "drumstick on a sunny pirate ship deck, comically stretched cheeks, "
        "crumbs flying, barrels and rigging around him, cheerful bouncy "
        "animation"
    ),
    "laughing_sky": (
        "Monkey D. Luffy laughing loudly with both arms spread wide on the "
        "deck of his pirate ship, straw hat on his head, huge blue sky and "
        "white clouds, warm sun flare, seagulls, joyful dynamic animation"
    ),
    "marine_chase": (
        "Monkey D. Luffy sprinting across a rocking ship deck while Marine "
        "battleships fire cannonballs behind him, cannonballs splashing into "
        "the sea, smoke and sparks, camera panning fast to follow him, "
        "high-energy action"
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
