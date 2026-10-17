"""Scene timelines: the animation itself, driven by nothing but math.

Each scene is a pure function ``render(cel, t, frame, rng)`` where ``t`` is the
normalised timeline position [0, 1).  Timing follows anime convention: snappy
ease-out bursts, holds on impact poses ("on twos/threes") and looping cycles
built from sine waves so the GIF loops seamlessly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from . import bg
from .cel import Cel, shade, tint
from .rig import HEAD_SCALE, PALETTE, Pose, Rig, blend_pose
from .vec import Vec, add, ease_out_cubic, ease_out_elastic, hold, polar, pulse

DOWN = math.pi / 2
TAU = math.tau

#: character height in rig units (head-top .. sole) - used for framing
RIG_HEIGHT = 0.70


@dataclass
class Scene:
    name: str
    title: str
    seconds: float
    loop: bool
    render: Callable[[Cel, float, int, "object"], None]


def place_rig(
    cel: Cel,
    pose: Pose,
    *,
    height_frac: float = 0.55,
    x_frac: float = 0.5,
    ground_frac: float = 0.92,
    zoom: float = 1.0,
    facing: int = 1,
    shake: Tuple[float, float] = (0.0, 0.0),
) -> Rig:
    """Frame the character: ``height_frac`` of the frame height, feet on the ground."""
    scale = (cel.h * height_frac / RIG_HEIGHT) * zoom
    origin = (
        cel.w * x_frac + shake[0] * cel.w,
        cel.h * ground_frac + shake[1] * cel.h,
    )
    return Rig(pose, scale, origin, facing=facing)


# --------------------------------------------------------------------------- #
# 1. Gear Second
# --------------------------------------------------------------------------- #
def scene_gear_second(cel: Cel, t: float, frame: int, rng) -> None:
    horizon = cel.h * 0.58
    bg.sky_gradient(cel, (104, 166, 216), (208, 232, 244))
    bg.haze(cel, horizon - cel.h * 0.12, horizon, (234, 245, 251), 0.5)
    bg.ocean(cel, horizon, seed=5)
    bg.deck(cel, horizon + cel.h * 0.20, scroll=0.18, vp_x=cel.w * 0.44)
    bg.railing(cel, horizon + cel.h * 0.05, scroll=0.18)

    burst = ease_out_cubic(hold(t, 0.20, 0.30))
    shake_amt = 0.014 * (1.0 - hold(t, 0.20, 0.42)) if 0.20 <= t <= 0.42 else 0.0
    shake = (rng.uniform(-shake_amt, shake_amt), rng.uniform(-shake_amt, shake_amt))

    if burst > 0.05:
        aura = cel.mask()
        aura.ellipse((cel.w * 0.47, cel.h * 0.68), cel.w * 0.26, cel.h * 0.34)
        cel.glow(aura.bake(), (255, 84, 66), radius=cel.w * 0.045, alpha=0.55 * burst)
        bg.speed_lines(
            cel,
            (cel.w * 0.47, cel.h * 0.58),
            count=54,
            r0=cel.w * 0.14,
            r1=cel.w * 0.85,
            alpha=0.5 * burst,
            seed=2,
        )

    crouch = Pose(
        lean=0.36,
        arm_front=(DOWN - 1.05, 1.45),
        arm_back=(DOWN + 0.85, 1.60),
        leg_front=(DOWN - 0.42, 0.95),
        leg_back=(DOWN + 0.30, 1.05),
        face="determined",
        bob=0.020,
    )
    sprint = Pose(
        lean=0.44,
        arm_front=(DOWN + 0.80, 1.15),
        arm_back=(DOWN - 0.95, 1.05),
        leg_front=(DOWN - 0.62, 0.30),
        leg_back=(DOWN + 0.66, 1.10),
        face="determined",
        bob=-0.014,
    )
    pose = blend_pose(crouch, sprint, ease_out_cubic(hold(t, 0.18, 0.30)))
    pose.skin_tint = burst
    pose.steam = 0.95 * hold(t, 0.24, 0.55)
    pose.sash_flow = t * 14.0
    pose.hair_flow = t * 10.0

    rig = place_rig(
        cel,
        pose,
        height_frac=0.54,
        x_frac=0.50,
        ground_frac=0.90,
        zoom=1.0 + 0.10 * burst,
        shake=shake,
    )
    rig.draw_ground_shadow(cel, rx=0.20, ry=0.034)
    rig.draw(cel, gear=burst)
    bg.steam(cel, (rig.j["pelvis"][0] + 0.06 * rig.S, rig.j["pelvis"][1] - 0.10 * rig.S), pose.steam, rng, alpha=0.30)
    if burst > 0.5:
        bg.sparkles(
            cel,
            [
                (rig.j["chest"][0] + rng.uniform(-0.18, 0.18) * rig.S, rig.j["chest"][1] + rng.uniform(-0.22, 0.06) * rig.S)
                for _ in range(3)
            ],
            size=0.02 * rig.S,
            alpha=0.5 * burst,
        )
    if 0.20 <= t <= 0.235:  # the activation flash
        cel.flash((255, 255, 255), 0.8)
    elif 0.235 < t <= 0.265:
        cel.flash((255, 210, 200), 0.35)
    cel.vignette(0.34)


# --------------------------------------------------------------------------- #
# 2. Gum-Gum Pistol (rubber arm stretch with smears + impact star)
# --------------------------------------------------------------------------- #
def scene_gum_gum_pistol(cel: Cel, t: float, frame: int, rng) -> None:
    horizon = cel.h * 0.52
    bg.sky_gradient(cel, (118, 176, 224), (212, 236, 246))
    bg.haze(cel, horizon - cel.h * 0.10, horizon, (236, 246, 252), 0.5)
    bg.ocean(cel, horizon, seed=13)
    bg.deck(cel, horizon + cel.h * 0.24, scroll=0.1, vp_x=cel.w * 0.60)

    wind = hold(t, 0.0, 0.16)
    stretch = hold(t, 0.18, 0.42)
    impact = hold(t, 0.44, 0.50)
    recoil = hold(t, 0.50, 0.68)
    settle = hold(t, 0.68, 1.0)

    shake_amt = 0.0
    if 0.42 <= t <= 0.60:
        shake_amt = 0.022 * (1.0 - hold(t, 0.42, 0.60))
    shake = (rng.uniform(-shake_amt, shake_amt), rng.uniform(-shake_amt, shake_amt))

    if t > 0.40:
        centre = (cel.w * 0.62, cel.h * 0.52)
        bg.speed_lines(cel, centre, count=40, r0=cel.w * 0.18, r1=cel.w * 0.9, alpha=0.35 * hold(t, 0.40, 0.55), seed=6)

    stance = Pose(
        lean=0.10,
        arm_front=(DOWN - 0.95, 0.85),
        arm_back=(DOWN + 0.55, 1.30),
        leg_front=(DOWN - 0.30, 0.28),
        leg_back=(DOWN + 0.34, 0.42),
        face="determined",
        draw_front_arm=True,
    )
    lunge = Pose(
        lean=0.34,
        arm_front=(DOWN - 1.02, 0.16),
        arm_back=(DOWN + 0.95, 1.55),
        leg_front=(DOWN - 0.46, 0.34),
        leg_back=(DOWN + 0.52, 0.70),
        face="determined",
    )
    pose = blend_pose(stance, lunge, ease_out_cubic(hold(t, 0.16, 0.34)))
    if t > 0.62:
        pose = blend_pose(pose, stance, ease_out_cubic(hold(t, 0.62, 0.80)))
    pose.face = "grin" if t > 0.56 else "determined"
    pose.sash_flow = t * 18.0
    pose.hair_flow = t * 12.0

    # the rubber arm: grows fast, snaps back elastically
    reach = ease_out_cubic(stretch) * (1.0 - ease_out_elastic(recoil) * 1.05)
    reach = max(0.0, min(1.0, reach))
    pose.arm_front_extra = 1.9 * reach
    pose.fist_front = 1.15 + 2.1 * reach
    pose.arm_front_angle_bias = 0.12 * reach
    pose.arm_front_curve = 0.10 * math.sin(t * TAU * 2.0)

    rig = place_rig(
        cel,
        pose,
        height_frac=0.62,
        x_frac=0.40,
        ground_frac=0.96,
        zoom=1.0 + 0.06 * impact,
        shake=shake,
    )
    rig.draw_ground_shadow(cel, rx=0.22, ry=0.036)
    # smear ghosts while the arm is flying out (or snapping back)
    if 0.22 <= t <= 0.44 and reach > 0.05:
        rig.draw_arm_ghost(cel, pose.arm_front_extra * 0.78, pose.fist_front * 0.9, 0.30)
        rig.draw_arm_ghost(cel, pose.arm_front_extra * 1.16, pose.fist_front * 1.05, 0.22)
    if 0.50 <= t <= 0.66 and reach > 0.05:
        rig.draw_arm_ghost(cel, pose.arm_front_extra * 1.25, pose.fist_front, 0.25)
    rig.draw(cel)

    if impact > 0.05:
        fist = rig.j["wrist_front"]
        tip = polar(rig.j["shoulder_front"], rig.j["arm_angle_front"][0] - pose.arm_front_angle_bias, (0.209 + 0.209 * pose.arm_front_extra) * rig.S)
        radius = (0.05 + 0.06 * impact) * cel.h
        bg.impact_star(cel, tip, radius, spikes=14, rotation=0.4 * frame)
        for k in range(3):
            r = radius * (1.1 + 1.5 * k) * impact
            bg.shockwave(cel, tip, r, thickness=max(2.0, 10 - 3 * k), alpha=0.55 - 0.15 * k)
        bg.dust_cloud(cel, (tip[0] - 0.04 * cel.w, cel.h * 0.94), cel.h * 0.10, rng, alpha=0.6)
    if 0.42 <= t <= 0.455:
        cel.flash((255, 255, 255), 0.95)
    elif 0.455 < t <= 0.49:
        cel.flash((255, 236, 220), 0.4)
    cel.vignette(0.30)


# --------------------------------------------------------------------------- #
# 3. Marine chase (run cycle, scrolling deck, splashes)
# --------------------------------------------------------------------------- #
def scene_marine_chase(cel: Cel, t: float, frame: int, rng) -> None:
    look = pulse(hold(t, 0.55, 0.95), 1.6)  # he glances back mid-cycle (0 at both ends)
    speed = 17.0 / 7.0  # = whole plank rows per cycle -> seamless GIF loop
    horizon = cel.h * 0.50
    bg.sky_gradient(cel, (126, 184, 226), (214, 236, 248))
    bg.haze(cel, horizon - cel.h * 0.09, horizon, (236, 246, 252), 0.5)
    bg.ocean(cel, horizon, seed=17)
    bg.deck(cel, horizon + cel.h * 0.14, scroll=t * speed, vp_x=cel.w * 0.40)
    bg.railing(cel, horizon + cel.h * 0.055, scroll=t * 2.0)

    # cannonball splashes racing by
    for start, x_frac in ((0.06, 0.74), (0.40, 0.30), (0.74, 0.86)):
        prog = hold(t, start, start + 0.24)
        if 0.0 < prog < 1.0:
            bg.splash(cel, (cel.w * x_frac, horizon + cel.h * 0.10), prog, color=(214, 236, 250))
            bg.dust_cloud(cel, (cel.w * x_frac, horizon + cel.h * 0.10), cel.h * 0.06 * prog, rng, color=(232, 244, 252), alpha=0.35 * (1 - prog))

    bg.streaks(cel, count=14, alpha=0.30, seed=8, width=2.4)

    theta = t * TAU
    swing_f = math.sin(theta)
    swing_b = math.sin(theta + math.pi)
    pose = Pose(
        lean=0.36,
        arm_front=(DOWN + 0.62 * swing_f, 1.05 + 0.35 * max(0.0, swing_f)),
        arm_back=(DOWN + 0.62 * swing_b, 1.05 + 0.35 * max(0.0, swing_b)),
        leg_front=(DOWN - 0.78 * swing_f, 0.30 + 1.15 * max(0.0, -swing_f)),
        leg_back=(DOWN - 0.78 * swing_b, 0.30 + 1.15 * max(0.0, -swing_b)),
        face="grin" if look < 0.5 else "shock",
        head_turn=0.35 * look,
        bob=-0.020 * abs(math.cos(theta)),
        sash_flow=t * TAU * 2.0,
        hair_flow=t * TAU * 1.5,
    )
    shake = (rng.uniform(-0.004, 0.004), rng.uniform(-0.004, 0.004))
    rig = place_rig(cel, pose, height_frac=0.62, x_frac=0.44, ground_frac=0.97, zoom=1.02, shake=shake)
    rig.draw_ground_shadow(cel, rx=0.18, ry=0.030, alpha=0.24)

    # dust puffs kicked up on each footfall
    for phase, x_off in ((0.0, -0.10), (0.5, 0.06)):
        contact = pulse((t + phase) % 1.0, 2.5)
        if contact > 0.05:
            base = (rig.j["pelvis"][0] + x_off * rig.S, rig.j["pelvis"][1] + 0.29 * rig.S)
            bg.dust_cloud(cel, base, (0.05 + 0.05 * contact) * cel.h, rng, alpha=0.55 * contact)

    rig.draw(cel)
    bg.speed_lines(cel, (cel.w * 0.62, cel.h * 0.46), count=26, r0=cel.w * 0.30, r1=cel.w * 0.95, alpha=0.22, seed=11)
    cel.vignette(0.30)


# --------------------------------------------------------------------------- #
# 4. Sunny figurehead (calm establishing shot)
# --------------------------------------------------------------------------- #
def scene_sunny_figurehead(cel: Cel, t: float, frame: int, rng) -> None:
    horizon = cel.h * 0.56
    bg.sky_gradient(cel, (96, 168, 224), (216, 240, 250))
    bg.haze(cel, horizon - cel.h * 0.16, horizon, (236, 248, 253), 0.55)
    bg.sun_disc(cel, (cel.w * 0.78, cel.h * 0.20), cel.h * 0.075)
    bg.sun_rays(cel, (cel.w * 0.78, cel.h * 0.20), count=11, length=cel.w * 0.9, half_width=0.035, tilt=t * TAU / 11.0, tone=30)
    for i, (cx, cy, s) in enumerate(((0.20, 0.16, 0.15), (0.55, 0.10, 0.10), (0.88, 0.30, 0.12))):
        drift = math.sin(t * TAU + i * 2.0) * 0.05
        bg.cloud(cel, (cel.w * (cx + drift), cel.h * cy), cel.h * s, rng, alpha=0.95)
    bg.ocean(cel, horizon, seed=23)
    bg.sun_path(cel, cel.w * 0.78, horizon, cel.w * 0.05, cel.w * 0.20, alpha=0.35)

    bob = 0.006 * math.sin(t * TAU)
    pose = Pose(
        lean=0.03,
        arm_front=(DOWN - 0.32, 0.40),
        arm_back=(DOWN + 0.20, 0.34),
        leg_front=(DOWN - 0.13, 0.07),
        leg_back=(DOWN + 0.15, 0.16),
        face="smile",
        bob=bob,
        head_turn=0.05 * math.sin(t * TAU * 0.5 + 0.4),
        sash_flow=t * TAU * 2.0,
        hair_flow=t * TAU * 3.0,
    )
    zoom = 1.0 + 0.06 * t
    rig = place_rig(cel, pose, height_frac=0.58, x_frac=0.44, ground_frac=0.98, zoom=zoom)
    # the ship's figurehead he is standing on
    fig = cel.mask()
    fig.polygon(
        [
            (rig.j["pelvis"][0] - 0.34 * rig.S, rig.j["pelvis"][1] + 0.30 * rig.S),
            (rig.j["pelvis"][0] + 0.34 * rig.S, rig.j["pelvis"][1] + 0.30 * rig.S),
            (rig.j["pelvis"][0] + 0.30 * rig.S, rig.j["pelvis"][1] + 0.40 * rig.S),
            (rig.j["pelvis"][0] - 0.30 * rig.S, rig.j["pelvis"][1] + 0.40 * rig.S),
        ]
    )
    cel.region(fig.bake(), (196, 148, 88), shadow=(160, 118, 66), shadow_offset=(4, 5), outline=(96, 66, 36), outline_width=3)
    rig.draw_ground_shadow(cel, rx=0.15, ry=0.022, alpha=0.22)
    rig.draw(cel)
    bg.birds(cel, [(add((cel.w * (0.16 + 0.10 * math.sin(t * TAU + i)), cel.h * (0.14 + 0.05 * i)), (0, 0)), 1.0 + 0.2 * i) for i in range(3)])
    if t > 0.35:
        bg.sparkles(
            cel,
            [
                (rig.j["chest"][0] + math.sin(t * TAU * 2 + i * 2.1) * 0.22 * rig.S, rig.j["chest"][1] + math.cos(t * TAU + i * 1.3) * 0.26 * rig.S)
                for i in range(4)
            ],
            size=0.018 * rig.S,
            alpha=0.75 * pulse(hold(t, 0.25, 0.75), 1.1),
        )
    cel.vignette(0.22)


# --------------------------------------------------------------------------- #
# 5. Sunset silhouette (ending-shot look, rim light on a dark character)
# --------------------------------------------------------------------------- #
def scene_sunset_silhouette(cel: Cel, t: float, frame: int, rng) -> None:
    horizon = cel.h * 0.62
    bg.sky_gradient(cel, (78, 66, 132), (255, 186, 118))
    bg.haze(cel, horizon - cel.h * 0.30, horizon - cel.h * 0.16, (255, 214, 160), 0.35)
    bg.haze(cel, horizon - cel.h * 0.14, horizon, (255, 226, 178), 0.45)
    bg.sun_disc(cel, (cel.w * 0.63, horizon - cel.h * 0.045), cel.h * 0.13, color=(255, 236, 176), glow=(255, 168, 96), alpha=0.95)
    for i in range(4):  # dark cloud bars across the sun
        y = horizon - cel.h * (0.20 - 0.045 * i)
        w = cel.w * (0.30 + 0.16 * i)
        cx = cel.w * (0.30 + 0.10 * i + 0.02 * math.sin(t * TAU + i))
        m = cel.mask()
        m.polygon([(cx - w / 2, y), (cx + w / 2, y - 6), (cx + w / 2 + 30, y + 12), (cx - w / 2 + 20, y + 16)])
        cel.fill_blend(m.bake(), (96, 74, 132), 0.55)
    bg.ocean(cel, horizon, deep=(46, 40, 92), mid=(72, 58, 118), near=(104, 78, 128), glints=False, seed=31)
    bg.sun_path(cel, cel.w * 0.63, horizon, cel.w * 0.06, cel.w * 0.30, color=(255, 214, 150), alpha=0.5)

    pose = Pose(
        lean=0.02,
        arm_front=(DOWN - 0.24, 0.30),
        arm_back=(DOWN + 0.24, 0.26),
        leg_front=(DOWN - 0.16, 0.06),
        leg_back=(DOWN + 0.18, 0.14),
        face="smile",
        bob=0.004 * math.sin(t * TAU),
        head_turn=-0.06 * math.sin(t * TAU),
        sash_flow=t * TAU,
        hair_flow=t * TAU * 2.0,
    )
    zoom = 1.0 + 0.07 * t
    rig = place_rig(cel, pose, height_frac=0.52, x_frac=0.40, ground_frac=0.99, zoom=zoom)
    rig.draw_ground_shadow(cel, rx=0.16, ry=0.020, alpha=0.35)
    rig.draw(cel, silhouette=(52, 34, 62), rim=(255, 198, 132))
    bg.birds(cel, [(add((cel.w * (0.72 + 0.06 * math.sin(t * TAU + i * 1.7)), cel.h * (0.22 + 0.06 * i)), (0, 0)), 0.9 + 0.25 * i) for i in range(3)], color=(70, 52, 96))
    if t > 0.40:
        bg.sparkles(
            cel,
            [(cel.w * 0.66, horizon - cel.h * 0.02), (cel.w * 0.72, horizon + cel.h * 0.05), (cel.w * 0.60, horizon + cel.h * 0.09)],
            size=cel.h * 0.018,
            color=(255, 244, 214),
            alpha=0.85 * pulse(hold(t, 0.30, 0.85), 1.0),
        )
    cel.vignette(0.40)


def _render_episode(cel: Cel, t: float, frame: int, rng) -> None:
    """Cut-together short: 6 shots with camera work (see episode.py)."""
    from .episode import render_episode

    render_episode(cel, t, frame, rng)


SCENES: Dict[str, Scene] = {
    "gear_second": Scene("gear_second", "Gear Second burst", 4.0, False, scene_gear_second),
    "gum_gum_pistol": Scene("gum_gum_pistol", "Gum-Gum Pistol", 4.5, False, scene_gum_gum_pistol),
    "marine_chase": Scene("marine_chase", "Marine chase run", 4.0, True, scene_marine_chase),
    "sunny_figurehead": Scene("sunny_figurehead", "On the figurehead", 5.0, True, scene_sunny_figurehead),
    "sunset_silhouette": Scene("sunset_silhouette", "Sunset silhouette", 5.0, True, scene_sunset_silhouette),
    "episode": Scene("episode", "Episode short (6 shots, camera + cuts)", 12.2, False, _render_episode),
}


def scene_names() -> List[str]:
    return list(SCENES)


def get_scene(name: str) -> Scene:
    key = (name or "").strip().lower()
    if key not in SCENES:
        raise KeyError("unknown scene {!r}; available: {}".format(name, ", ".join(scene_names())))
    return SCENES[key]
