"""A short "episode" cut together shot by shot.

This is the difference between a looping test and something that reads like
broadcast anime:

* **shots with hard cuts** (establishing wide -> medium -> eye close-up ->
  action wide -> impact close-up -> sunset ending) instead of one static camera
* **camera work** - pan, push-in, whip-pan, roll and shake, applied by the
  analytic camera in :class:`~luffy_clip.cel.Cel` (no resampling, so close-ups
  stay razor sharp)
* **acting beats** - eye blinks, talking mouth shapes, torso twist, wind-blown
  hair strands and cloth follow-through
* **broadcast compositing** - white impact flashes on the cut, bloom/light
  wrap, anamorphic flare, warm/cool grades, vignette, film grain, fade in/out.
"""

from __future__ import annotations

import math
from typing import Callable, List, Tuple

from . import bg
from .cel import Cel
from .rig import Pose, blend_pose
from .scenes import DOWN, TAU, place_rig
from .vec import add, ease_out_cubic, hold, mix, polar, pulse


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _standing(beats: float = 0.0, mouth: str = "smile", blink: float = 0.0) -> Pose:
    return Pose(
        lean=0.04,
        arm_front=(DOWN - 0.30, 0.38),
        arm_back=(DOWN + 0.22, 0.32),
        leg_front=(DOWN - 0.13, 0.07),
        leg_back=(DOWN + 0.15, 0.15),
        face="smile",
        mouth_shape=mouth,
        blink=blink,
        bob=0.004 * math.sin(beats * TAU),
        head_turn=0.04 * math.sin(beats * TAU * 0.5 + 0.6),
        sash_flow=beats * TAU * 2.0,
        strand_flow=beats * TAU * 4.0,
    )


# --------------------------------------------------------------------------- #
# shot 1 - establishing wide, slow pan right
# --------------------------------------------------------------------------- #
def shot_establish(cel: Cel, u: float, rng) -> None:
    horizon = cel.h * 0.54
    cel.set_camera(zoom=1.05 + 0.06 * u, look_at=(cel.w * (0.42 + 0.16 * u), cel.h * 0.46), roll=-0.004 * u)

    bg.sky_gradient(cel, (92, 152, 214), (218, 238, 248))
    bg.haze(cel, horizon - cel.h * 0.10, horizon, (236, 248, 253), 0.40)
    for i, (cx, cy, s) in enumerate(((0.22, 0.20, 0.13), (0.60, 0.11, 0.09), (0.88, 0.27, 0.11))):
        bg.cloud(cel, (cel.w * (cx + 0.03 * math.sin(u * 2.4 + i * 2)), cel.h * cy), cel.h * s, rng)
    bg.ocean(cel, horizon, seed=3)
    bg.sun_path(cel, cel.w * 0.70, horizon, cel.w * 0.04, cel.w * 0.18, alpha=0.30)
    bg.deck(cel, horizon + cel.h * 0.10, scroll=0.05, vp_x=cel.w * 0.46)
    bg.railing(cel, horizon + cel.h * 0.03, scroll=0.05)
    bg.birds(cel, [((cel.w * (0.30 + 0.035 * i), cel.h * (0.17 + 0.05 * i)), 0.9 + 0.25 * i) for i in range(3)])

    pose = _standing(beats=u, mouth="smile")
    rig = place_rig(cel, pose, height_frac=0.34, x_frac=0.40, ground_frac=0.80)
    rig.draw_ground_shadow(cel, rx=0.13, ry=0.020, alpha=0.22)
    rig.draw(cel)


# --------------------------------------------------------------------------- #
# shot 2 - medium, push in while he talks
# --------------------------------------------------------------------------- #
def shot_approach(cel: Cel, u: float, rng) -> None:
    horizon = cel.h * 0.52
    cel.set_camera(zoom=1.10 + 0.14 * u, look_at=(cel.w * 0.45, cel.h * (0.44 + 0.05 * u)), roll=0.002 * math.sin(u * 3.0))

    bg.sky_gradient(cel, (104, 164, 220), (220, 240, 250))
    bg.haze(cel, horizon - cel.h * 0.12, horizon, (238, 249, 254), 0.4)
    bg.cloud(cel, (cel.w * 0.78, cel.h * 0.16), cel.h * 0.12, rng)
    bg.ocean(cel, horizon, seed=6)
    bg.deck(cel, horizon + cel.h * 0.18, scroll=0.06, vp_x=cel.w * 0.44)
    bg.railing(cel, horizon + cel.h * 0.06, scroll=0.06)

    talking = ("talk" if int(u * 9) % 2 else "smile") if 0.18 < u < 0.62 else "smile"
    blink = 1.0 if (0.42 <= u <= 0.47) or (0.86 <= u <= 0.90) else 0.0
    pose = _standing(beats=u, mouth=talking, blink=blink)
    pose.twist = 0.07 * math.sin(u * TAU)

    rig = place_rig(cel, pose, height_frac=0.64, x_frac=0.45, ground_frac=0.80)
    rig.draw_ground_shadow(cel, rx=0.16, ry=0.024, alpha=0.22)
    rig.draw(cel)


# --------------------------------------------------------------------------- #
# shot 3 - eye close-up, blink, speed lines rising, flash on the cut
# --------------------------------------------------------------------------- #
def shot_eyes(cel: Cel, u: float, rng) -> None:
    cel.set_camera(zoom=2.30 + 0.35 * u, look_at=(cel.w * 0.45, cel.h * (0.44 - 0.015 * u)), roll=-0.010 * u)

    bg.sky_gradient(cel, (78, 140, 204), (200, 230, 246))
    bg.haze(cel, cel.h * 0.55, cel.h * 0.72, (226, 242, 252), 0.4)
    bg.speed_lines(cel, (cel.w * 0.45, cel.h * 0.40), count=34, r0=cel.w * 0.04, r1=cel.w * 0.55, color=(255, 255, 255), alpha=0.16 + 0.26 * u, seed=4, width=2.2)

    blink = 1.0 if u < 0.13 else (1.0 if 0.62 <= u <= 0.68 else 0.0)
    pose = _standing(beats=u * 0.5, mouth="line", blink=blink)
    pose.face = "determined"
    pose.mouth_shape = "line"
    pose.head_turn = -0.02

    rig = place_rig(cel, pose, height_frac=0.46, x_frac=0.45, ground_frac=0.64)
    rig.draw(cel)
    # rising speed lines in front too (they sell the "about to move" beat)
    bg.speed_lines(cel, (cel.w * 0.45, cel.h * 0.42), count=18, r0=cel.w * 0.03, r1=cel.w * 0.34, color=(255, 255, 255), alpha=0.18 + 0.30 * u, seed=9, width=1.8)


# --------------------------------------------------------------------------- #
# shot 4 - Gear Second burst, whip-pan follows the sprint
# --------------------------------------------------------------------------- #
def shot_burst(cel: Cel, u: float, rng) -> None:
    burst = ease_out_cubic(hold(u, 0.16, 0.28))
    cel.set_camera(
        zoom=1.08 + 0.20 * hold(u, 0.18, 0.42),
        look_at=(cel.w * (0.38 + 0.16 * u), cel.h * 0.60),
        roll=0.006 * math.sin(u * 9.0),
    )
    horizon = cel.h * 0.52
    bg.sky_gradient(cel, (100, 160, 216), (212, 236, 246))
    bg.haze(cel, horizon - cel.h * 0.14, horizon, (234, 246, 252), 0.5)
    bg.ocean(cel, horizon, seed=12)
    bg.deck(cel, horizon + cel.h * 0.20, scroll=u * 1.8, vp_x=cel.w * 0.44)
    bg.railing(cel, horizon + cel.h * 0.05, scroll=u * 1.8)
    if burst > 0.05:
        aura = cel.mask()
        aura.ellipse((cel.w * 0.46, cel.h * 0.70), cel.w * 0.24, cel.h * 0.34)
        cel.glow(aura.bake(), (255, 84, 66), radius=cel.w * 0.045, alpha=0.55 * burst)
        bg.speed_lines(cel, (cel.w * 0.46, cel.h * 0.58), count=52, r0=cel.w * 0.14, r1=cel.w * 0.9, alpha=0.5 * burst, seed=2)

    crouch = Pose(
        lean=0.36, arm_front=(DOWN - 1.05, 1.45), arm_back=(DOWN + 0.85, 1.60),
        leg_front=(DOWN - 0.42, 0.95), leg_back=(DOWN + 0.30, 1.05), face="determined", bob=0.020,
    )
    sprint = Pose(
        lean=0.46, arm_front=(DOWN + 0.80, 1.15), arm_back=(DOWN - 0.95, 1.05),
        leg_front=(DOWN - 0.62, 0.30), leg_back=(DOWN + 0.66, 1.10), face="grin", bob=-0.014,
    )
    pose = blend_pose(crouch, sprint, ease_out_cubic(hold(u, 0.14, 0.28)))
    pose.skin_tint = burst
    pose.steam = 0.95 * hold(u, 0.20, 0.55)
    pose.sash_flow = u * 16.0
    pose.strand_flow = u * 22.0
    rig = place_rig(cel, pose, height_frac=0.54, x_frac=0.46, ground_frac=0.90, zoom=1.0 + 0.08 * burst)
    rig.draw_ground_shadow(cel, rx=0.19, ry=0.032)
    rig.draw(cel, gear=burst)
    bg.steam(cel, (rig.j["pelvis"][0] + 0.05 * rig.S, rig.j["pelvis"][1] - 0.10 * rig.S), pose.steam, rng, alpha=0.30)


# --------------------------------------------------------------------------- #
# shot 5 - impact close-up: rubber fist into the lens
# --------------------------------------------------------------------------- #
def shot_impact(cel: Cel, u: float, rng) -> None:
    impact = hold(u, 0.40, 0.50)
    pose = Pose(
        lean=0.30,
        arm_front=(DOWN - 1.00, 0.20),
        arm_back=(DOWN + 0.90, 1.55),
        leg_front=(DOWN - 0.46, 0.34),
        leg_back=(DOWN + 0.52, 0.70),
        face="grin",
        sash_flow=u * 20.0,
        strand_flow=u * 26.0,
        arm_front_extra=1.9 * ease_out_cubic(hold(u, 0.0, 0.40)),
        fist_front=1.2 + 2.0 * ease_out_cubic(hold(u, 0.0, 0.40)),
        arm_front_angle_bias=0.10,
    )
    rig = place_rig(cel, pose, height_frac=0.62, x_frac=0.28, ground_frac=1.06)
    tip = polar(
        rig.j["shoulder_front"],
        rig.j["arm_angle_front"][0] - pose.arm_front_angle_bias,
        (0.209 * (1.0 + pose.arm_front_extra)) * rig.S,
    )
    # the camera rides the incoming fist so the impact always lands on screen
    cel.set_camera(
        zoom=1.22 + 0.26 * u,
        look_at=mix(tip, (cel.w * 0.56, cel.h * 0.46), 0.10 + 0.30 * hold(u, 0.0, 0.55)),
        roll=0.014 * math.sin(u * 11.0),
    )

    bg.sky_gradient(cel, (86, 148, 208), (204, 232, 246))
    bg.haze(cel, cel.h * 0.50, cel.h * 0.68, (228, 244, 252), 0.4)
    bg.streaks(cel, count=16, alpha=0.30, seed=12, width=2.6)
    bg.speed_lines(cel, (cel.w * 0.60, cel.h * 0.50), count=44, r0=cel.w * 0.12, r1=cel.w * 0.95, alpha=0.25 + 0.35 * hold(u, 0.2, 0.6), seed=13)

    if 0.06 < u < 0.42:
        rig.draw_arm_ghost(cel, pose.arm_front_extra * 0.82, pose.fist_front * 0.92, 0.28)
        rig.draw_arm_ghost(cel, pose.arm_front_extra * 1.14, pose.fist_front * 1.04, 0.20)
    rig.draw(cel)

    if impact > 0.05:
        radius = (0.06 + 0.07 * impact) * cel.h
        bg.impact_star(cel, tip, radius, spikes=14, rotation=0.5)
        for k in range(3):
            bg.shockwave(cel, tip, radius * (1.1 + 1.4 * k) * impact, thickness=max(2.0, 11 - 3 * k), alpha=0.55 - 0.15 * k)
        bg.dust_cloud(cel, (tip[0], cel.h * 0.96), cel.h * 0.10, rng, alpha=0.55)


# --------------------------------------------------------------------------- #
# shot 6 - sunset ending, hat tip, slow tilt up
# --------------------------------------------------------------------------- #
def shot_ending(cel: Cel, u: float, rng) -> None:
    horizon = cel.h * 0.64
    cel.set_camera(zoom=1.05 + 0.09 * u, look_at=(cel.w * 0.44, cel.h * (0.62 - 0.10 * u)))

    bg.sky_gradient(cel, (76, 64, 130), (255, 188, 120))
    bg.haze(cel, horizon - cel.h * 0.32, horizon - cel.h * 0.18, (255, 214, 160), 0.35)
    bg.haze(cel, horizon - cel.h * 0.15, horizon, (255, 228, 180), 0.45)
    bg.sun_disc(cel, (cel.w * 0.63, horizon - cel.h * 0.05), cel.h * 0.14, color=(255, 236, 176), glow=(255, 168, 96), alpha=0.95)
    for i in range(3):
        y = horizon - cel.h * (0.20 - 0.05 * i)
        w = cel.w * (0.26 + 0.17 * i)
        cx = cel.w * (0.30 + 0.10 * i + 0.02 * math.sin(u * TAU + i))
        m = cel.mask()
        m.polygon([(cx - w / 2, y), (cx + w / 2, y - 6), (cx + w / 2 + 30, y + 12), (cx - w / 2 + 20, y + 16)])
        cel.fill_blend(m.bake(), (122, 92, 152), 0.38)
    bg.ocean(cel, horizon, deep=(46, 40, 92), mid=(72, 58, 118), near=(104, 78, 128), glints=False, seed=31)
    bg.sun_path(cel, cel.w * 0.63, horizon, cel.w * 0.06, cel.w * 0.30, color=(255, 214, 150), alpha=0.5)

    raise_amount = ease_out_cubic(hold(u, 0.12, 0.45))
    pose = Pose(
        lean=0.02,
        arm_front=(DOWN - 0.28 - 1.25 * raise_amount, 0.30 + 1.55 * raise_amount),
        arm_back=(DOWN + 0.24, 0.26),
        leg_front=(DOWN - 0.16, 0.06),
        leg_back=(DOWN + 0.18, 0.14),
        face="smile",
        mouth_shape="smile",
        blink=1.0 if 0.30 <= u <= 0.35 else 0.0,
        bob=0.004 * math.sin(u * TAU),
        head_turn=-0.05 * math.sin(u * TAU),
        head_tilt=0.02 * raise_amount,
        sash_flow=u * TAU,
        strand_flow=u * TAU * 2.0,
    )
    rig = place_rig(cel, pose, height_frac=0.54, x_frac=0.40, ground_frac=1.00)
    rig.draw_ground_shadow(cel, rx=0.16, ry=0.020, alpha=0.35)
    rig.draw(cel, silhouette=(52, 34, 62), rim=(255, 198, 132))
    bg.birds(cel, [(add((cel.w * (0.74 + 0.05 * math.sin(u * TAU + i * 1.7)), cel.h * (0.20 + 0.06 * i)), (0, 0)), 0.9 + 0.25 * i) for i in range(3)], color=(70, 52, 96))
    bg.sparkles(
        cel,
        [(cel.w * 0.66, horizon - cel.h * 0.02), (cel.w * 0.72, horizon + cel.h * 0.05), (cel.w * 0.58, horizon + cel.h * 0.09)],
        size=cel.h * 0.018,
        color=(255, 244, 214),
        alpha=0.85 * pulse(hold(u, 0.25, 0.85), 1.0),
    )


SHOTS: List[Tuple[float, Callable[[Cel, float, "object"], None]]] = [
    (2.6, shot_establish),
    (2.2, shot_approach),
    (0.9, shot_eyes),
    (2.4, shot_burst),
    (1.5, shot_impact),
    (2.6, shot_ending),
]
EPISODE_SECONDS = sum(duration for duration, _ in SHOTS)


def _shot_at(time_s: float) -> Tuple[int, Callable[[Cel, float, "object"], None], float]:
    acc = 0.0
    for index, (duration, render) in enumerate(SHOTS):
        if time_s < acc + duration:
            return index, render, (time_s - acc) / duration
        acc += duration
    duration, render = SHOTS[-1]
    return len(SHOTS) - 1, render, 1.0


def render_episode(cel: Cel, t: float, frame: int, rng) -> None:
    """Render the whole cut sequence at timeline position *t* in [0, 1]."""
    index, render, local = _shot_at(max(0.0, min(0.9999, t)) * EPISODE_SECONDS)
    render(cel, local, rng)

    # ---- editorial + finishing (broadcast compositing) -------------------- #
    if index in (3, 4) and local < 0.05:  # white flash right after a hard cut
        cel.flash((255, 255, 255), 0.9 * (1.0 - local / 0.05))
    if index == 4 and local > 0.40:  # impact frames
        cel.flash((255, 255, 255), 0.75 * (1.0 - hold(local, 0.40, 0.46)))
    if index == 0 and local < 0.10:  # fade up from black
        cel.flash((0, 0, 0), 1.0 - local / 0.10)
    if index == len(SHOTS) - 1 and local > 0.86:  # fade to black
        cel.flash((0, 0, 0), hold(local, 0.86, 1.0))

    if index in (0, 1, 5):
        cel.bloom(threshold=206, radius=18.0, alpha=0.30)
    if index in (0, 5):
        cel.lens_flare((cel.w * 0.72, cel.h * 0.20), length=cel.w * 0.44, alpha=0.35)
    if index == 3:
        cel.grade((192, 214, 255), 0.16)
    if index == 5:
        cel.grade((255, 214, 172), 0.20)
    cel.bloom(threshold=212, radius=12.0, alpha=0.16)
    cel.vignette(0.38 if index == 4 else 0.28)
    cel.grain(2.4, seed=11 + index)
