"""Tests for the deterministic arena battle engine."""

import math
import random

import pytest

from simulation.physics import (
    LIFELINE_INITIAL,
    Arena,
    Battle,
    bounce_off_wall,
    collide_balls,
    create_balls,
    cut_lifelines,
    grow_lifelines,
    restore_speed,
)

ARENA = Arena(cx=540.0, cy=960.0, radius=380.0)
BALL_RADIUS = 38.0


def run_battle(seed, num_balls=5, max_steps=20000):
    battle = Battle(seed=seed, arena=ARENA, ball_radius=BALL_RADIUS, num_balls=num_balls)
    steps = 0
    while not battle.is_over() and steps < max_steps:
        battle.step()
        steps += 1
    return battle


def test_determinism_same_seed():
    a = run_battle(7)
    b = run_battle(7)
    assert a.winner == b.winner
    assert a.stats() == b.stats()
    assert a.eliminations == b.eliminations


def test_different_seeds_diverge():
    a = run_battle(1)
    b = run_battle(2)
    # Headings differ per seed, so the battle diverges within a few frames.
    a_frames, b_frames = [], []
    for _ in range(10):
        a_frames.append(a.frame_state())
        b_frames.append(b.frame_state())
        a.step()
        b.step()
    assert a_frames != b_frames


def test_initial_lifelines_on_rim_behind_ball():
    balls = create_balls(random.Random(1), ARENA, BALL_RADIUS, 5)
    assert len(balls) == 5
    for b in balls:
        assert len(b.lifelines) == LIFELINE_INITIAL
        radial = (b.x - ARENA.cx, b.y - ARENA.cy)
        for ax, ay in b.lifelines:
            # anchors sit exactly on the arena rim
            d = math.hypot(ax - ARENA.cx, ay - ARENA.cy)
            assert abs(d - ARENA.radius) < 1e-6
            # anchors are behind the ball: same outward half of the arena
            dot = (ax - ARENA.cx) * radial[0] + (ay - ARENA.cy) * radial[1]
            assert dot > 0


def test_wall_bounce_reflects_inward():
    rng = random.Random(0)
    ball = create_balls(rng, ARENA, BALL_RADIUS, 1)[0]
    # 1 px past the wall contact line (dist + radius > arena radius).
    ball.x = ARENA.cx + ARENA.radius - BALL_RADIUS + 1.0
    ball.y = ARENA.cy
    ball.vx = 200.0
    ball.vy = 0.0
    assert bounce_off_wall(rng, ball, ARENA) is True
    assert ball.vx < 0  # reflected inward
    assert math.hypot(ball.x - ARENA.cx, ball.y - ARENA.cy) + BALL_RADIUS <= ARENA.radius + 1e-6


def test_lifeline_growth_on_bounce_min_three():
    # From 3 strings, a bounce adds max(3, ceil(3*0.6)) = 3.
    for seed in range(30):
        rng = random.Random(seed)
        ball = create_balls(rng, ARENA, BALL_RADIUS, 1)[0]
        ball.x = ARENA.cx + ARENA.radius - BALL_RADIUS + 1.0
        ball.y = ARENA.cy
        ball.vx = 200.0
        ball.vy = 0.0
        before = len(ball.lifelines)
        assert bounce_off_wall(rng, ball, ARENA)
        grow_lifelines(rng, ball, ARENA)
        grew = len(ball.lifelines) - before
        assert grew == 3   # the user's rule: min 3, ~60%


def test_collision_does_not_grow_lifelines():
    rng = random.Random(5)
    balls = create_balls(rng, ARENA, BALL_RADIUS, 2)
    a, o = balls
    a.x, a.y = ARENA.cx - 30.0, ARENA.cy
    o.x, o.y = ARENA.cx + 30.0, ARENA.cy
    before_a, before_o = len(a.lifelines), len(o.lifelines)
    collide_balls(a, o)
    assert len(a.lifelines) == before_a
    assert len(o.lifelines) == before_o


def test_speed_recovers_toward_base():
    rng = random.Random(6)
    ball = create_balls(rng, ARENA, BALL_RADIUS, 1)[0]
    ball.vx *= 0.05   # drain nearly all speed (a hard collision)
    ball.vy *= 0.05
    before = math.hypot(ball.vx, ball.vy)
    restore_speed(rng, ball)
    after = math.hypot(ball.vx, ball.vy)
    assert after > before                    # recovering, not draining
    assert after <= ball.base_speed + 1e-6  # never overshoots base speed


def test_ball_cuts_other_string():
    rng = random.Random(3)
    balls = create_balls(rng, ARENA, BALL_RADIUS, 2)
    a, o = balls
    # Park the attacker on the midpoint of o's first string.
    ax, ay = o.lifelines[0]
    a.x = (o.x + ax) / 2.0
    a.y = (o.y + ay) / 2.0
    before = len(o.lifelines)
    cut_lifelines(a, balls)
    assert len(o.lifelines) < before
    assert o.lifelines_cut == before - len(o.lifelines)
    assert a.cuts_dealt == before - len(o.lifelines)   # the attacker scored those cuts


def test_elastic_collision_equal_masses():
    rng = random.Random(4)
    balls = create_balls(rng, ARENA, BALL_RADIUS, 2)
    a, o = balls
    # Head-on collision along the x axis (dist 60 < 2 * radius).
    a.x, a.y = ARENA.cx - 30.0, ARENA.cy
    o.x, o.y = ARENA.cx + 30.0, ARENA.cy
    a.vx, a.vy = 100.0, 0.0
    o.vx, o.vy = -100.0, 0.0
    impact = collide_balls(a, o)
    assert impact > 0
    # Equal masses swap normal velocities.
    assert a.vx == pytest.approx(-100.0)
    assert o.vx == pytest.approx(100.0)


def test_fast_collision_resolves_without_tunneling():
    # At 6000 px/s a ball moves 100 px per frame - more than the 76 px ball
    # diameter, so a single-step integrator would pass right through. The
    # sub-stepped battle must detect the collision and bounce them apart.
    rng = random.Random(11)
    balls = create_balls(rng, ARENA, BALL_RADIUS, 2)
    a, o = balls
    a.x, a.y = ARENA.cx - 40.0, ARENA.cy
    o.x, o.y = ARENA.cx + 40.0, ARENA.cy
    a.vx, a.vy = 6000.0, 0.0
    o.vx, o.vy = -6000.0, 0.0
    battle = Battle(seed=11, arena=ARENA, num_balls=2)
    battle.balls = balls
    min_gap = float("inf")
    for _ in range(2):
        battle.step()
        dist = math.hypot(a.x - o.x, a.y - o.y)
        min_gap = min(min_gap, dist)
    assert min_gap >= 2 * BALL_RADIUS - 1.0   # never tunneled through each other
    assert a.vx < 0 and o.vx > 0               # they collided and bounced apart


def test_battle_runs_to_winner():
    battle = run_battle(42, num_balls=5)
    assert battle.winner is not None
    winner_ball = next(b for b in battle.balls if b.id == battle.winner)
    assert winner_ball.alive
    stats = battle.stats()[battle.winner]
    assert stats["bounces"] > 0
