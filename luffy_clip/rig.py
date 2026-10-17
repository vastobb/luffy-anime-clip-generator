"""Procedural "straw hat pirate boy" character rig, drawn 100% from math.

No AI, no external art: every shape is an analytic polygon (capsules, splines,
ellipses) rasterised into cel masks, shaded with a second tone and inked with
an outline derived from the silhouette - the way a real animation cel is built.

Local coordinate system: ``S`` = rig scale in pixels, origin at the pelvis,
``+x`` = facing direction, ``+y`` = down.  Angles are atan2-style radians where
``pi/2`` points straight down, ``0`` points forward (facing direction).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, fields
from typing import Dict, List, Optional, Sequence, Tuple

from .cel import Cel, Color, Mask, shade
from .vec import (
    Vec,
    add,
    capsule,
    catmull_rom,
    ellipse,
    mix,
    mul,
    normalise,
    perp,
    polar,
    strip,
    sub,
)

# --------------------------------------------------------------------------- #
# palette
# --------------------------------------------------------------------------- #
PALETTE: Dict[str, Color] = {
    "line": (24, 17, 15),
    "skin": (247, 202, 165),
    "skin_shade": (219, 165, 126),
    "skin_deep": (198, 140, 104),
    "skin_gear": (250, 168, 146),
    "hair": (33, 24, 19),
    "hair_hi": (86, 61, 45),
    "vest": (200, 42, 42),
    "vest_shade": (156, 28, 33),
    "sash": (243, 195, 52),
    "sash_shade": (203, 149, 28),
    "shorts": (46, 108, 174),
    "shorts_shade": (32, 78, 130),
    "hat": (233, 201, 124),
    "hat_shade": (196, 163, 88),
    "band": (198, 40, 40),
    "band_shade": (152, 28, 32),
    "sandal": (122, 86, 54),
    "sandal_shade": (96, 66, 40),
    "white": (255, 255, 255),
    "mouth": (94, 41, 35),
    "tongue": (216, 122, 126),
}

DOWN = math.pi / 2


@dataclass
class Pose:
    """All the knobs of the character. Angles in radians (see module docstring)."""

    pelvis: Vec = (0.0, 0.0)
    lean: float = 0.0  # torso tilt, + = leaning forward (+x)
    twist: float = 0.0  # shoulder line rotation
    head_tilt: float = 0.0
    head_turn: float = 0.0

    arm_front: Tuple[float, float] = (DOWN - 0.34, 0.46)  # (shoulder, elbow flex)
    arm_back: Tuple[float, float] = (DOWN + 0.02, 0.30)
    leg_front: Tuple[float, float] = (DOWN - 0.10, 0.10)
    leg_back: Tuple[float, float] = (DOWN + 0.12, 0.22)

    # extras
    arm_front_extra: float = 0.0  # stretch amount for the rubber arm
    fist_front: float = 1.0  # fist scale (foreshortening)
    arm_front_curve: float = 0.0  # bend of the stretched arm
    bob: float = 0.0
    shake: Vec = (0.0, 0.0)
    squash: float = 1.0  # vertical squash/stretch of the whole body
    face: str = "determined"  # determined | smile | grin | shock
    skin_tint: float = 0.0  # 0..1 -> lean towards the Gear Second glow colour
    sash_flow: float = 0.0  # phase of cloth flutter
    hair_flow: float = 0.0
    steam: float = 0.0
    arm_front_angle_bias: float = 0.0
    draw_front_arm: bool = True


# proportions (fractions of S)
P_HEAD = 0.168
HEAD_SCALE = 1.24  # head + hat + hair drawn 16% larger than body units
P_ARM0, P_ARM1 = 0.108, 0.101
P_LEG0, P_LEG1 = 0.132, 0.132
R_NECK = 0.028
R_ARM0, R_ARM1 = 0.030, 0.023
R_WRIST = 0.018
R_LEG0, R_LEG1 = 0.042, 0.034
R_SHIN = 0.021
R_FIST = 0.037


def blend_pose(a: Pose, b: Pose, u: float) -> Pose:
    """Linear blend between two key poses (anime pose-to-pose animation)."""
    u = max(0.0, min(1.0, u))
    values: Dict[str, object] = {}
    for f in fields(Pose):
        va, vb = getattr(a, f.name), getattr(b, f.name)
        if isinstance(va, tuple):
            values[f.name] = tuple(x + (y - x) * u for x, y in zip(va, vb))
        elif isinstance(va, (int, float)) and not isinstance(va, bool):
            values[f.name] = va + (vb - va) * u
        else:
            values[f.name] = vb if u > 0.5 else va
    return Pose(**values)  # type: ignore[arg-type]


class Rig:
    """Forward kinematics + drawing of the character."""

    def __init__(self, pose: Pose, scale: float, origin: Vec, facing: int = 1):
        self.pose = pose
        self.S = scale
        self.origin = origin
        self.facing = facing
        self.j: Dict[str, Vec] = {}
        self._solve()

    # -- helpers ----------------------------------------------------------- #
    def pt(self, local: Vec, anchor: Vec) -> Vec:
        """local (in S units, y down) -> canvas point, honouring facing."""
        x = local[0] * self.facing
        return (anchor[0] + x * self.S, anchor[1] + local[1] * self.S)

    def _solve(self) -> None:
        p = self.pose
        S = self.S
        f = self.facing
        lean = p.lean
        bob = p.bob * S

        def up(angle: float) -> Vec:
            """Unit vector pointing up the spine, tilted forward by *angle*."""
            return (math.sin(angle) * f, -math.cos(angle))

        def side(angle: float) -> Vec:
            """Unit vector pointing to the character's near side."""
            return (math.cos(angle) * f, math.sin(angle) * f)

        pelvis = (self.origin[0] + p.pelvis[0] * S * f, self.origin[1] + p.pelvis[1] * S + bob)
        head_angle = lean + p.head_turn

        self.j["pelvis"] = pelvis
        self.j["waist"] = add(pelvis, mul(up(lean), 0.092 * S))
        self.j["chest"] = add(pelvis, mul(up(lean), 0.166 * S))
        self.j["neck"] = add(pelvis, mul(up(lean), 0.236 * S))
        self.j["head"] = add(pelvis, mul(up(head_angle), 0.292 * S))
        self.j["head_angle"] = (head_angle, 0.0)  # type: ignore[assignment]

        self.j["shoulder_front"] = add(add(pelvis, mul(up(lean), 0.198 * S)), mul(side(lean), 0.084 * S))
        self.j["shoulder_back"] = add(add(pelvis, mul(up(lean), 0.196 * S)), mul(side(lean), -0.074 * S))
        self.j["hip_front"] = add(add(pelvis, mul(up(lean), 0.010 * S)), mul(side(lean), 0.046 * S))
        self.j["hip_back"] = add(add(pelvis, mul(up(lean), 0.008 * S)), mul(side(lean), -0.044 * S))

        def limb_angle(angle: float) -> float:
            return (math.pi - angle) if f < 0 else angle

        # limbs (two-bone forward kinematics)
        for name, origin_key, angles, l0, l1 in (
            ("elbow_front", "shoulder_front", p.arm_front, P_ARM0, P_ARM1),
            ("elbow_back", "shoulder_back", p.arm_back, P_ARM0, P_ARM1),
        ):
            start = self.j[origin_key]
            shoulder_a = limb_angle(angles[0])
            elbow_flex = angles[1]
            upper = polar(start, shoulder_a, l0 * S)
            fore_a = shoulder_a - elbow_flex * f
            wrist = polar(upper, fore_a, l1 * S)
            self.j[name] = upper
            self.j[name.replace("elbow", "wrist")] = wrist
            self.j[name.replace("elbow", "arm_angle")] = (fore_a, 0.0)  # type: ignore[assignment]

        for name, origin_key, angles, l0, l1 in (
            ("knee_front", "hip_front", p.leg_front, P_LEG0, P_LEG1),
            ("knee_back", "hip_back", p.leg_back, P_LEG0, P_LEG1),
        ):
            start = self.j[origin_key]
            hip_a = limb_angle(angles[0])
            knee_flex = angles[1]
            knee = polar(start, hip_a, l0 * S)
            shin_a = hip_a + knee_flex * f
            ankle = polar(knee, shin_a, l1 * S)
            self.j[name] = knee
            self.j[name.replace("knee", "ankle")] = ankle
            self.j[name.replace("knee", "leg_angle")] = (shin_a, 0.0)  # type: ignore[assignment]

    # -- silhouette pieces -------------------------------------------------- #
    def torso_spine(self) -> List[Vec]:
        return [self.j["pelvis"], self.j["waist"], self.j["chest"], self.j["neck"]]

    def torso_mask(self, grow: float = 0.0, mask: Optional[Mask] = None) -> Mask:
        spine = self.torso_spine()
        S = self.S
        widths = [
            (0.163 + grow) * S,
            (0.138 + grow) * S,
            (0.158 + grow) * S,
            (0.112 + grow) * S,
        ]
        m = mask or self.cel.mask()
        m.polygon(strip(spine, widths))
        return m

    def _fist_polygon(self, center: Vec, radius: float, angle: float) -> List[Vec]:
        pts = list(ellipse(center, radius * 1.02, radius * 0.96, angle))
        for k in range(4):  # knuckle bumps on the leading edge
            t = -0.42 + 0.28 * k
            knuckle = add(center, polar((0, 0), angle + t, radius * 1.0))
            pts += ellipse(knuckle, radius * 0.30, radius * 0.30)
        thumb = add(center, polar((0, 0), angle + math.pi * 0.72, radius * 0.95))
        pts += ellipse(thumb, radius * 0.36, radius * 0.30, angle)
        return pts

    def _limb_mask(self, mask: Mask, a: Vec, b: Vec, c: Vec, r0: float, r1: float, r2: float) -> Mask:
        S = self.S
        mask.polygon(capsule(a, b, r0 * S, r1 * S))
        mask.polygon(capsule(b, c, r1 * S, r2 * S))
        return mask

    # -- main entry ---------------------------------------------------------#
    def draw(self, cel: Cel, *, silhouette: Optional[Color] = None, rim: Optional[Color] = None, gear: float = 0.0) -> None:
        self.cel = cel
        S = self.S
        pal = PALETTE
        pose = self.pose

        skin_fill = pal["skin"]
        if gear > 0:
            skin_fill = mix_color(pal["skin"], pal["skin_gear"], gear)
        skin_shade = shade(skin_fill, 0.85)
        skin_deep = shade(skin_fill, 0.72)
        skin_back = shade(skin_fill, 0.88)

        olw = max(2, int(round(0.0072 * S)))
        shadow_k = (max(2, int(0.012 * S)), max(3, int(0.016 * S)))

        def paint(mask: Mask, fill: Color, *, shadow: Optional[Color] = None, outline: bool = True, alpha: float = 1.0) -> None:
            img = mask.bake()
            if silhouette is not None:
                cel.region(img, silhouette, outline=rim or shade(silhouette, 1.2) if rim else None, outline_width=olw, alpha=alpha)
                return
            cel.region(
                img,
                fill,
                shadow=shadow,
                shadow_offset=shadow_k,
                outline=pal["line"],
                outline_width=olw if outline else 0,
                alpha=alpha,
            )

        mask = cel.mask

        # ---- back limbs --------------------------------------------------- #
        back_leg = mask()
        self._limb_mask(
            back_leg,
            self.j["hip_back"],
            self.j["knee_back"],
            self.j["ankle_back"],
            R_LEG0 * 0.94,
            R_LEG1 * 0.94,
            R_SHIN * 0.94,
        )
        paint(back_leg, skin_back, shadow=None)
        self._draw_sandal(cel, paint, self.j["ankle_back"], self.j["leg_angle_back"][0], back=True)

        back_arm = mask()
        self._limb_mask(
            back_arm,
            self.j["shoulder_back"],
            self.j["elbow_back"],
            self.j["wrist_back"],
            R_ARM0 * 0.94,
            R_ARM1 * 0.94,
            R_WRIST * 0.94,
        )
        paint(back_arm, skin_back, shadow=None)
        self._draw_fist(cel, paint, self.j["wrist_back"], self.j["arm_angle_back"][0], 1.0, back=True)

        # ---- torso + clothes ---------------------------------------------- #
        torso = self.torso_mask()
        paint(torso, skin_fill, shadow=skin_shade)

        vest = self.torso_mask(grow=0.008)
        # open V neckline
        spine = self.torso_spine()
        neck_pt = spine[3]
        chest_pt = mix(spine[2], spine[3], 0.18)
        axis = normalise(sub(spine[3], spine[1]))
        v_half = mul(perp(axis), 0.052 * S)
        tip = add(chest_pt, mul(axis, 0.02 * S))
        vest.subtract([add(neck_pt, v_half), add(neck_pt, mul(v_half, -1)), tip])
        paint(vest, pal["vest"], shadow=pal["vest_shade"])

        shorts = mask()
        for hip_key, knee_key in (("hip_front", "knee_front"), ("hip_back", "knee_back")):
            hip, knee = self.j[hip_key], self.j[knee_key]
            hem = mix(hip, knee, 0.46 if hip_key == "hip_front" else 0.40)
            shorts.polygon(capsule(hip, hem, R_LEG0 * 1.10 * S, R_LEG1 * 1.10 * S))
        shorts.ellipse(self.j["pelvis"], 0.085 * S, 0.062 * S)
        paint(shorts, pal["shorts"] and pal["shorts"], shadow=pal["shorts_shade"])

        sash = mask()
        waist = self.j["waist"]
        axis = normalise(sub(self.j["chest"], self.j["pelvis"]))
        side = mul(perp(axis), 0.082 * S)
        band_curve = [
            sub(waist, mul(side, 1.0)),
            waist,
            add(waist, side),
        ]
        sash.polygon(strip(band_curve, [0.052 * S] * 3))
        # knot + fluttering tail
        knot = sub(waist, mul(side, 1.02))
        sash.ellipse(knot, 0.020 * S, 0.024 * S, self.pose.lean)
        flow = self.pose.sash_flow
        tail = [
            knot,
            add(knot, (-0.030 * S, 0.030 * S + math.sin(flow) * 0.012 * S)),
            add(knot, (-0.020 * S, 0.070 * S + math.sin(flow + 0.7) * 0.020 * S)),
        ]
        sash.polygon(strip(catmull_rom(tail, samples=8), [0.020 * S, 0.018 * S, 0.011 * S]))
        paint(sash, pal["sash"], shadow=pal["sash_shade"])

        # ---- front limbs ---------------------------------------------------#
        front_leg = mask()
        self._limb_mask(
            front_leg,
            self.j["hip_front"],
            self.j["knee_front"],
            self.j["ankle_front"],
            R_LEG0,
            R_LEG1,
            R_SHIN,
        )
        paint(front_leg, skin_fill, shadow=skin_shade)
        self._draw_sandal(cel, paint, self.j["ankle_front"], self.j["leg_angle_front"][0], back=False)

        if pose.draw_front_arm:
            self._draw_front_arm(cel, paint, skin_fill, skin_shade, gear)

        # ---- head ----------------------------------------------------------#
        self._draw_head(cel, paint, skin_fill, skin_shade, skin_deep, pal, silhouette=silhouette, rim=rim)

        # ---- steam ----------------------------------------------------------#
        if pose.steam > 0 and silhouette is None:
            self._draw_steam(cel, pose.steam)

    # -- pieces -------------------------------------------------------------#
    def _draw_fist(self, cel: Cel, paint, wrist: Vec, angle: float, scale: float, back: bool = False) -> None:
        m = cel.mask()
        m.polygon(self._fist_polygon(wrist, R_FIST * self.S * scale, angle))
        paint(m, shade(PALETTE["skin"], 0.88 if back else 1.0), shadow=None if back else shade(PALETTE["skin"], 0.85))

    def _draw_sandal(self, cel: Cel, paint, ankle: Vec, shin_angle: float, back: bool = False) -> None:
        S = self.S
        foot_angle = shin_angle + math.pi / 2 * 0.92  # foot roughly horizontal-ish
        toe = polar(ankle, foot_angle, 0.058 * S)
        m = cel.mask()
        m.polygon(capsule(ankle, toe, 0.020 * S, 0.014 * S))
        paint(m, PALETTE["sandal"], shadow=None if back else PALETTE["sandal_shade"])
        sole = cel.mask()
        sole.polygon(capsule(add(ankle, (0, 0.012 * S)), add(toe, (0, 0.012 * S)), 0.012 * S, 0.010 * S))
        paint(sole, shade(PALETTE["sandal"], 0.8), shadow=None, outline=True)

    def _front_arm_shapes(self, mask: Mask, extra: float, fist_scale: float) -> Vec:
        """Rubber arm: soft bezier that thins in the middle, fat fist at the tip."""
        S = self.S
        pose = self.pose
        shoulder = self.j["shoulder_front"]
        arm_angle = self.j["arm_angle_front"][0]
        base_len = (P_ARM0 + P_ARM1) * S
        reach = base_len * (1.0 + extra)
        curve = pose.arm_front_curve * S
        tip = polar(shoulder, arm_angle - pose.arm_front_angle_bias, reach)
        ctrl = [
            shoulder,
            add(mix(shoulder, tip, 0.33), (0, -curve * 0.5)),
            add(mix(shoulder, tip, 0.66), (0, curve * 0.35)),
            tip,
        ]
        rope = catmull_rom(ctrl, samples=14)
        widths = []
        n = len(rope)
        for i in range(n):
            t = i / (n - 1)
            widths.append((0.030 + 0.052 * (t ** 1.6)) * S)
        mask.polygon(strip(rope, widths))
        mask.polygon(self._fist_polygon(tip, R_FIST * S * fist_scale, arm_angle - pose.arm_front_angle_bias))
        return tip

    def _draw_front_arm(self, cel: Cel, paint, skin_fill: Color, skin_shade: Color, gear: float) -> None:
        pose = self.pose
        if pose.arm_front_extra <= 0.01:
            arm = cel.mask()
            self._limb_mask(arm, self.j["shoulder_front"], self.j["elbow_front"], self.j["wrist_front"], R_ARM0, R_ARM1, R_WRIST)
            paint(arm, skin_fill, shadow=skin_shade)
            self._draw_fist(cel, paint, self.j["wrist_front"], self.j["arm_angle_front"][0], pose.fist_front)
            return
        arm = cel.mask()
        self._front_arm_shapes(arm, pose.arm_front_extra, pose.fist_front)
        paint(arm, skin_fill, shadow=skin_shade)

    def draw_arm_ghost(self, cel: Cel, extra: float, fist_scale: float, alpha: float) -> None:
        """Ghost copies of the stretched arm - classic anime motion smear."""
        if alpha <= 0.02:
            return
        m = cel.mask()
        self._front_arm_shapes(m, extra, fist_scale)
        cel.region(
            m.bake(),
            PALETTE["skin"],
            outline=PALETTE["line"],
            outline_width=max(2, int(0.0072 * self.S)),
            alpha=alpha,
        )

    def _head_transform(self, local: Vec, lean_extra: float = 0.0) -> Vec:
        """head-local (S units, y down) -> canvas."""
        head = self.j["head"]
        angle = self.pose.lean + self.pose.head_turn + self.pose.head_tilt + lean_extra
        HS = self.S * HEAD_SCALE
        scaled = (local[0] * HS * self.facing, local[1] * HS)
        return add(head, rotate_pt(scaled, angle * self.facing))

    def _draw_head(self, cel: Cel, paint, skin_fill: Color, skin_shade: Color, skin_deep: Color, pal, *, silhouette=None, rim=None) -> None:
        HS = self.S * HEAD_SCALE
        pose = self.pose
        p = self._head_transform
        ink = (24, 17, 15)

        # ---- neck ---------------------------------------------------------#
        neck_mask = cel.mask()
        neck_mask.polygon(
            capsule(self.j["neck"], add(self.j["neck"], (0, -0.085 * HS)), R_NECK * 1.05 * HS, R_NECK * HS)
        )
        paint(neck_mask, skin_fill, shadow=None)

        head_pts = [
            (0.052, -0.078),
            (0.018, -0.090),
            (-0.028, -0.088),
            (-0.064, -0.068),
            (-0.082, -0.034),
            (-0.080, 0.004),
            (-0.062, 0.040),
            (-0.034, 0.062),
            (0.004, 0.074),
            (0.036, 0.072),
            (0.064, 0.048),
            (0.080, 0.012),
            (0.078, -0.032),
        ]
        head_outline = catmull_rom([p(pt) for pt in head_pts], samples=10, closed=True)
        head_mask = cel.mask()
        head_mask.polygon(head_outline)
        ear_c = p((-0.076, 0.014))
        head_mask.polygon(ellipse(ear_c, 0.014 * HS, 0.018 * HS, 0.2 * self.facing))
        paint(head_mask, skin_fill, shadow=skin_shade)

        # ---- hair ---------------------------------------------------------#
        hair_pts = [
            (0.074, -0.058),
            (0.064, -0.024),
            (0.048, -0.050),
            (0.030, -0.022),
            (0.012, -0.048),
            (-0.008, -0.020),
            (-0.026, -0.046),
            (-0.048, -0.024),
            (-0.072, -0.046),
            (-0.092, -0.014),
            (-0.098, 0.024),
            (-0.084, 0.052),
            (-0.072, 0.026),
            (-0.058, 0.054),
            (-0.050, 0.020),
            (-0.040, -0.028),
            (0.006, -0.064),
            (0.050, -0.080),
        ]
        hair_mask = cel.mask()
        hair_mask.polygon(catmull_rom([p(pt) for pt in hair_pts], samples=8, closed=True))
        if silhouette is not None:
            paint(hair_mask, silhouette, outline=False)
        else:
            paint(hair_mask, pal["hair"], shadow=None)
            sheen = cel.mask()
            sheen.polygon(
                catmull_rom(
                    [p(pt) for pt in [(-0.020, -0.070), (0.020, -0.078), (0.050, -0.062), (0.036, -0.052), (0.004, -0.062)]],
                    samples=8,
                    closed=True,
                )
            )
            cel.fill_blend(sheen.bake(), pal["hair_hi"], 0.55)

        # ---- straw hat ----------------------------------------------------#
        brim = cel.mask()
        brim.polygon(ellipse(p((0.0, -0.078)), 0.176 * HS, 0.035 * HS, (-0.10 + pose.head_tilt) * self.facing))
        dome_c = p((0.0, -0.100))
        dome = cel.mask()
        dome.polygon(ellipse(dome_c, 0.086 * HS, 0.056 * HS))
        dome.subtract(
            [
                (-2 * HS, dome_c[1] + 0.022 * HS),
                (2 * HS, dome_c[1] + 0.022 * HS),
                (2 * HS, dome_c[1] + 2 * HS),
                (-2 * HS, dome_c[1] + 2 * HS),
            ]
        )
        band = cel.mask()
        band.polygon(ellipse(dome_c, 0.088 * HS, 0.058 * HS))
        band.intersect_polygon(
            [
                (dome_c[0] - 0.4 * HS, dome_c[1] - 0.038 * HS),
                (dome_c[0] + 0.4 * HS, dome_c[1] - 0.038 * HS),
                (dome_c[0] + 0.4 * HS, dome_c[1] - 0.019 * HS),
                (dome_c[0] - 0.4 * HS, dome_c[1] - 0.019 * HS),
            ]
        )
        if silhouette is not None:
            paint(brim, silhouette, outline=False)
            paint(dome, silhouette, outline=False)
            paint(band, silhouette, outline=False)
        else:
            brim_img = brim.bake()
            cel.region(
                brim_img,
                pal["hat"],
                shadow=pal["hat_shade"],
                shadow_offset=(3, 4),
                outline=pal["line"],
                outline_width=max(2, int(0.0074 * HS)),
            )
            paint(dome, pal["hat"], shadow=pal["hat_shade"])
            paint(band, pal["band"], shadow=None, outline=False)

            # the classic shadow the brim throws across the forehead
            face = cel.mask()
            face.polygon(head_outline)
            top_face = cel.mask()
            top_face.polygon([(-4 * HS, -4 * HS), (4 * HS, -4 * HS), (4 * HS, self.j["neck"][1]), (-4 * HS, self.j["neck"][1])])
            eye_line = p((-0.12, -0.018))[1]
            top_face.subtract([(-4 * HS, eye_line), (4 * HS, eye_line), (4 * HS, 4 * HS), (-4 * HS, 4 * HS)])
            brim_shadow = Cel._shift(brim_img, 4, max(2, int(0.020 * HS)))
            brim_shadow = Cel.intersect(brim_shadow, Cel.intersect(face.bake(), top_face.bake()))
            cel.fill_blend(brim_shadow, skin_deep, 0.55)

            # hat cord flapping at the nape
            cel.stroke(
                [p((-0.070, -0.008)), p((-0.086, 0.024)), add(self.j["neck"], (-0.008 * HS, -0.016 * HS))],
                (24, 17, 15, 200),
                0.006 * HS,
                smooth=6,
            )

        if silhouette is not None:
            return

        # ---- face ---------------------------------------------------------#
        eye_y = 0.006
        if pose.face in ("determined", "shock"):
            brow_in, brow_out = (0.010, -0.026), (0.058, -0.038)
        else:
            brow_in, brow_out = (0.010, -0.032), (0.058, -0.032)
        cel.stroke([p(brow_in), p(brow_out)], ink + (255,), 0.012 * HS, smooth=6)
        cel.stroke([p((-0.014, -0.030)), p((-0.054, -0.027))], ink + (255,), 0.011 * HS, smooth=6)

        for cx, rx, ry in ((0.032, 0.030, 0.033), (-0.028, 0.023, 0.027)):
            c = p((cx, eye_y))
            sclera = cel.mask()
            sclera.polygon(ellipse(c, rx * HS, ry * HS))
            cel.fill(sclera.bake(), pal["white"])
            iris_r = ry * HS * 0.66
            iris_c = add(c, (-0.004 * HS, 0.002 * HS))
            iris = cel.mask()
            iris.polygon(ellipse(iris_c, iris_r * 0.92, iris_r))
            cel.fill(iris.bake(), (32, 23, 21))
            pupil = cel.mask()
            pupil.polygon(ellipse(add(iris_c, (-0.001 * HS, 0)), iris_r * 0.46, iris_r * 0.56))
            cel.fill(pupil.bake(), (12, 9, 9))
            for hy, hr in ((-0.35, 0.30), (0.35, 0.16)):
                hi = cel.mask()
                hi.polygon(ellipse(add(iris_c, (-iris_r * 0.42, iris_r * hy)), iris_r * hr, iris_r * hr * 0.85))
                cel.fill(hi.bake(), (255, 255, 255))
            cel.stroke(
                [p((cx - rx, eye_y - 0.004)), p((cx, eye_y - ry * 0.98)), p((cx + rx * 1.05, eye_y - 0.004))],
                ink + (255,),
                0.011 * HS,
                smooth=10,
            )
            cel.stroke(
                [p((cx - rx * 0.9, eye_y + ry * 0.72)), p((cx + rx * 0.9, eye_y + ry * 0.66))],
                ink + (190,),
                0.005 * HS,
                smooth=6,
            )

        # nose tick + cheek/jaw shading
        cel.stroke([p((0.064, 0.012)), p((0.072, 0.024))], (150, 104, 76, 220), 0.008 * HS, smooth=4)
        cel.stroke([p((-0.070, 0.004)), p((-0.062, 0.034))], (196, 140, 104, 150), 0.007 * HS, smooth=4)

        # scar under the near eye
        scar_c = p((0.036, 0.036))
        cel.stroke([add(scar_c, (-0.010 * HS, -0.006 * HS)), add(scar_c, (0.010 * HS, 0.006 * HS))], (186, 128, 96, 230), 0.005 * HS)
        cel.stroke([add(scar_c, (-0.008 * HS, 0.008 * HS)), add(scar_c, (0.008 * HS, -0.002 * HS))], (186, 128, 96, 230), 0.005 * HS)

        # mouth
        if pose.face in ("grin", "smile"):
            mouth_c = p((0.034, 0.038))
            w = (0.058 if pose.face == "grin" else 0.032) * HS
            h = (0.027 if pose.face == "grin" else 0.014) * HS
            mouth = cel.mask()
            mouth.polygon(
                catmull_rom(
                    [
                        (mouth_c[0] - w / 2, mouth_c[1]),
                        (mouth_c[0], mouth_c[1] + h),
                        (mouth_c[0] + w / 2, mouth_c[1] - h * 0.15),
                        (mouth_c[0], mouth_c[1] - h * 0.30),
                    ],
                    samples=8,
                    closed=True,
                )
            )
            cel.fill(mouth.bake(), pal["mouth"])
            if pose.face == "grin":
                teeth = cel.mask()
                teeth.polygon(
                    catmull_rom(
                        [
                            (mouth_c[0] - w * 0.45, mouth_c[1] - h * 0.06),
                            (mouth_c[0], mouth_c[1] + h * 0.10),
                            (mouth_c[0] + w * 0.46, mouth_c[1] - h * 0.20),
                            (mouth_c[0], mouth_c[1] - h * 0.26),
                        ],
                        samples=8,
                        closed=True,
                    )
                )
                cel.fill(teeth.bake(), (250, 248, 244))
        elif pose.face == "shock":
            mouth_c = p((0.038, 0.040))
            mouth = cel.mask()
            mouth.polygon(ellipse(mouth_c, 0.024 * HS, 0.030 * HS))
            cel.fill(mouth.bake(), pal["mouth"])
        else:
            cel.stroke([p((0.012, 0.046)), p((0.034, 0.052)), p((0.058, 0.042))], (70, 40, 32, 255), 0.010 * HS, smooth=8)

        # gear second aura bleeding off the head
        if pose.skin_tint > 0:
            glow = cel.mask()
            glow.polygon(head_outline)
            cel.glow(glow.bake(), (255, 96, 72), radius=14, alpha=0.32 * pose.skin_tint)

    # -- ground contact shadow ----------------------------------------------#
    def draw_ground_shadow(self, cel: Cel, *, offset: Vec = (0.0, 0.0), rx: float = 0.165, ry: float = 0.030, alpha: float = 0.30) -> None:
        """Soft contact shadow on the ground plane (keeps the character planted)."""
        S = self.S
        pelvis = self.j["pelvis"]
        center = (pelvis[0] + offset[0] * S, pelvis[1] + (0.298 + offset[1]) * S)
        m = cel.mask()
        m.ellipse(center, rx * S, ry * S)
        cel.fill_blend(m.bake(), (32, 58, 84), alpha)

    # -- steam ---------------------------------------------------------------#
    def _draw_steam(self, cel: Cel, amount: float) -> None:
        S = self.S
        pelvis = self.j["pelvis"]
        for index in range(6):
            t = (index / 6.0) % 1.0
            x = (-0.08 + 0.05 * index) * S
            rise = (0.10 + 0.22 * ((t + 0.3 * index) % 1.0)) * S
            center = (pelvis[0] + x, pelvis[1] + 0.10 * S - rise)
            radius = (0.020 + 0.026 * ((t * 1.7) % 1.0)) * S * (0.6 + amount)
            m = cel.mask()
            m.blob(center, radius, wobble=0.30, phase=index * 1.7, freq=3)
            cel.fill_blend(m.bake(), (255, 255, 255), 0.32 * amount)


def rotate_pt(p: Vec, angle: float) -> Vec:
    c, s = math.cos(angle), math.sin(angle)
    return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)


def mix_color(a: Color, b: Color, t: float) -> Color:
    return tuple(int(round(x + (y - x) * t)) for x, y in zip(a, b))  # type: ignore[return-value]
