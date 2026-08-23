#!/usr/bin/env python3
"""Generate render/fixtures/sample_events.json — a synthetic events.json matching
the README data contract, for testing the Godot renderer.

Motion model (matches the intended arena battle, carried over from the v1 sketches):
  * balls spawn equidistant around the arena rim (0.8 x arena radius)
  * each ball's initial velocity aims at the arena centre, deviated by a
    seeded random +/-15 degrees, so collisions are unpredictable
  * wall bounces reflect the velocity and add a small +/-10 degree wobble
  * ball-ball collisions are elastic (equal masses) with positional correction
Ball 4 is eliminated at t=4.0s.
Run:  python3 render/fixtures/generate_sample_events.py
"""

import json
import math
import random
from pathlib import Path

SEED = 4821
FPS = 60
DURATION_S = 6.0
N_BALLS = 5
CENTER = (540.0, 960.0)      # 1080x1920 design space
ARENA_R = 380.0
BALL_R = 38.0
SPAWN_FRAC = 0.8
SPEED = 220.0                # px/s
TO_CENTER_DEVIATION = math.radians(15)
BOUNCE_WOBBLE = math.radians(10)

ELIMINATED_ID = 4
ELIMINATED_T = 4.0

rng = random.Random(SEED)


def main() -> None:
    # Spawn equidistant around the rim, velocity aimed at centre +/-15 degrees.
    balls = []
    for i in range(N_BALLS):
        ang = 2.0 * math.pi * i / N_BALLS
        x = CENTER[0] + SPAWN_FRAC * ARENA_R * math.cos(ang)
        y = CENTER[1] + SPAWN_FRAC * ARENA_R * math.sin(ang)
        target = math.atan2(CENTER[1] - y, CENTER[0] - x)
        heading = target + rng.uniform(-TO_CENTER_DEVIATION, TO_CENTER_DEVIATION)
        balls.append({
            "id": i,
            "x": x,
            "y": y,
            "vx": SPEED * math.cos(heading),
            "vy": SPEED * math.sin(heading),
            "alive": True,
        })

    wall_bounces = []
    collisions = []
    eliminations = [{"t": ELIMINATED_T, "ball_id": ELIMINATED_ID}]

    frames = []
    dt = 1.0 / FPS
    for f in range(int(DURATION_S * FPS)):
        t = round(f * dt, 6)

        # Integrate positions (eliminated balls stop being simulated).
        for b in balls:
            if not b["alive"]:
                continue
            b["x"] += b["vx"] * dt
            b["y"] += b["vy"] * dt

        # Wall bounces.
        for b in balls:
            if not b["alive"]:
                continue
            dx = b["x"] - CENTER[0]
            dy = b["y"] - CENTER[1]
            dist = math.hypot(dx, dy)
            if dist + BALL_R > ARENA_R:
                nx, ny = dx / dist, dy / dist
                b["x"] = CENTER[0] + (ARENA_R - BALL_R) * nx
                b["y"] = CENTER[1] + (ARENA_R - BALL_R) * ny
                dot = b["vx"] * nx + b["vy"] * ny
                vx = b["vx"] - 2 * dot * nx
                vy = b["vy"] - 2 * dot * ny
                wobble = rng.uniform(-BOUNCE_WOBBLE, BOUNCE_WOBBLE)
                cos_t, sin_t = math.cos(wobble), math.sin(wobble)
                b["vx"] = vx * cos_t - vy * sin_t
                b["vy"] = vx * sin_t + vy * cos_t
                wall_bounces.append({"t": t, "ball_id": b["id"]})

        # Ball-ball collisions (elastic, equal masses) with separation.
        for i in range(N_BALLS):
            for j in range(i + 1, N_BALLS):
                a, o = balls[i], balls[j]
                if not a["alive"] or not o["alive"]:
                    continue
                dx = o["x"] - a["x"]
                dy = o["y"] - a["y"]
                dist = math.hypot(dx, dy)
                if dist == 0:
                    continue
                if dist < 2 * BALL_R:
                    nx, ny = dx / dist, dy / dist
                    rel = (a["vx"] - o["vx"]) * nx + (a["vy"] - o["vy"]) * ny
                    a["vx"] -= rel * nx
                    a["vy"] -= rel * ny
                    o["vx"] += rel * nx
                    o["vy"] += rel * ny
                    overlap = (2 * BALL_R - dist) * 0.5
                    a["x"] -= overlap * nx
                    a["y"] -= overlap * ny
                    o["x"] += overlap * nx
                    o["y"] += overlap * ny
                    impact = min(1.0, abs(rel) / SPEED)
                    collisions.append({
                        "t": t, "ball_a": a["id"], "ball_b": o["id"], "impact": round(impact, 2),
                    })

        # Eliminations take effect from their timestamp onward.
        for b in balls:
            if b["id"] == ELIMINATED_ID and t >= ELIMINATED_T:
                b["alive"] = False

        # Emit frame.
        frame_balls = []
        for b in balls:
            frame_balls.append({
                "id": b["id"],
                "x": round(b["x"], 2),
                "y": round(b["y"], 2),
                "lifelines": 3,
                "alive": b["alive"],
            })
        frames.append({"t": t, "balls": frame_balls})

    pulse_curve = [[round(t, 2), 1.0] for t in (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0)]
    speed_curve = [[0.0, 1.0], [6.0, 1.0]]

    events = {
        "seed": SEED,
        "fps": FPS,
        "duration_s": DURATION_S,
        "frames": frames,
        "collisions": collisions,
        "wall_bounces": wall_bounces,
        "eliminations": eliminations,
        "pulse_curve": pulse_curve,
        "speed_curve": speed_curve,
    }

    out = Path(__file__).parent / "sample_events.json"
    out.write_text(json.dumps(events, indent=1), encoding="utf-8")
    print(f"wrote {out} ({len(frames)} frames, {N_BALLS} balls, "
          f"{len(collisions)} collisions, {len(wall_bounces)} wall bounces, 1 elimination)")


if __name__ == "__main__":
    main()

