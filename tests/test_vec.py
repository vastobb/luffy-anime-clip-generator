"""Math layer tests: curves, capsules, easing, two-bone kinematics."""

from __future__ import annotations

import math

from luffy_clip import vec


def test_catmull_rom_interpolates_endpoints():
    points = [(0.0, 0.0), (10.0, 5.0), (20.0, -5.0), (30.0, 0.0)]
    curve = vec.catmull_rom(points, samples=8)
    assert curve[0] == points[0]
    assert curve[-1] == points[-1]
    assert len(curve) > len(points)


def test_capsule_stays_within_endpoint_radii():
    a, b = (0.0, 0.0), (100.0, 0.0)
    poly = vec.capsule(a, b, 10.0, 4.0)
    for x, y in poly:
        # nothing sticks out above/below the radii, and nothing before/after the caps
        assert -10.5 <= x <= 104.5
        assert -10.5 <= y <= 10.5


def test_strip_resamples_width_profiles():
    curve = [(0.0, 0.0), (10.0, 1.0), (20.0, 0.0), (30.0, -1.0), (40.0, 0.0)]
    ribbon = vec.strip(curve, [4.0, 2.0])  # wrong length on purpose
    assert len(ribbon) == 2 * len(curve)


def test_bezier_hits_control_points():
    ctrl = [(0.0, 0.0), (0.0, 10.0), (10.0, 10.0), (10.0, 0.0)]
    assert vec.bezier(ctrl, 0.0) == ctrl[0]
    assert vec.bezier(ctrl, 1.0) == ctrl[-1]
    mid = vec.bezier(ctrl, 0.5)
    assert 4.0 < mid[0] < 6.0


def test_easing_functions_behave():
    assert vec.ease_out_cubic(0.0) == 0.0
    assert vec.ease_out_cubic(1.0) == 1.0
    assert vec.ease_out_cubic(0.5) > 0.5  # snappy out
    assert 0.0 <= vec.ease_in_out(0.3) <= 1.0
    assert vec.ease_out_back(1.0) == 1.0
    assert abs(vec.ease_out_elastic(1.0) - 1.0) < 1e-9


def test_hold_and_pulse_windows():
    assert vec.hold(0.1, 0.2, 0.4) == 0.0
    assert vec.hold(0.3, 0.2, 0.4) == 0.5
    assert vec.hold(0.9, 0.2, 0.4) == 1.0
    assert vec.pulse(0.0) == 0.0 and vec.pulse(1.0) == 0.0
    assert vec.pulse(0.5) > 0.9


def test_two_bone_lengths_are_exact():
    origin = (0.0, 0.0)
    a, b, c = vec.two_bone(origin, math.pi / 2, 0.5, 30.0, 20.0)
    assert a == origin
    assert abs(vec.length(vec.sub(b, a)) - 30.0) < 1e-9
    assert abs(vec.length(vec.sub(c, b)) - 20.0) < 1e-9


def test_rotate_and_mirror():
    assert vec.rotate((1.0, 0.0), math.pi / 2) == (0.0, 1.0)
    assert vec.mirror_many([(2.0, 1.0)], axis_x=0.0) == [(-2.0, 1.0)]
