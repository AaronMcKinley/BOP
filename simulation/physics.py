"""physics.py: the deterministic arena battle engine.

A ball bounces inside a circular arena. Each ball carries lifelines - string
anchors on the arena rim. Rules:

  * balls spawn evenly around the rim, aimed at the centre with a small
    seeded deviation, and each starts with 3 lifelines pointing at the rim
    behind them
  * every wall bounce grows the ball's lifelines by ~60% of its current count,
    rounded up, at least MIN_GAIN_PER_BOUNCE, capped at MAX_GAIN_PER_BOUNCE per
    bounce - e.g. 3 -> +3, 7 -> +5, 10 -> +6, 20 -> +10
    (ball-ball collisions do NOT grow lifelines)
  * a ball that passes close to another ball's string cuts that string
  * zero lifelines = eliminated; last ball standing wins
  * collisions can drain a ball's speed (real physics); balls recover back to
    their own base speed each frame, faster the more lifelines they carry
  * each ball's base speed varies slightly, so the initial rush to the centre
    is staggered and the first clash doesn't wipe everyone at once
  * the whole field's speed follows the song's energy curve when a timeline is
    given (calm intro -> frantic drop -> eased breakdown), otherwise a slow
    inverse-exponential ramp toward MAX_SPEED_MULT; the opening is always calm
    (no grace period, strings can be cut from the first frame)
  * strings cap at MAX_LIFELINES (180), spaced one per degree around the rim -
    a thick web, but kept tidy (no clumping)
  * sudden death at SUDDEN_DEATH_AT (90 s): from then on wall bounces stop
    growing lifelines - the web can only shrink, so every battle must resolve
  * there is no battle time cap: it runs until one ball remains (re-run the
    dev script for a fresh seed if a run ever drags on)

Determinism: every random choice comes from the seeded RNG, so the same seed
always produces the same battle.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# --- tuning knobs ------------------------------------------------------------
SPAWN_FRAC = 0.8               # spawn at this fraction of arena radius from centre
SPEED = 130.0                  # px/s base ball speed (fast motion, ~1min via re-roll)
SPEED_VARIATION = (0.8, 1.2)   # per-ball base-speed multiplier (stagger the rush)
RESTORE_RATE = 2.5             # per second, speed recovers toward base speed (fast catch-up)
START_RAMP_FLOOR = 0.25        # opening speed as a fraction of base (gets going fast)
SPEED_TAU = 50.0               # seconds - inverse-exponential ramp time constant
MAX_SPEED_MULT = 5.5           # endgame speed multiplier (the ramp's asymptote);
                               #   rams the endgame up (~3.9x by 60s) without
                               #   wrecking battle length (tuned by distribution)
TO_CENTER_DEVIATION = math.radians(15)   # initial heading wobble around "aim at centre"
BOUNCE_WOBBLE = math.radians(10)         # wall bounce angle wobble
LIFELINE_INITIAL = 3           # starting strings per ball
LIFELINE_GAIN_FRACTION = 0.6   # wall bounce grows strings by this x current count (ceil)
MIN_GAIN_PER_BOUNCE = 3        # ... but always at least this many per bounce
MAX_GAIN_PER_BOUNCE = 10       # ... and never more than this per bounce
LIFELINE_SPREAD = math.radians(10)       # anchor angle spread per cluster
MAX_LIFELINES = 180            # strings cap: one per degree, max 180 (kept tidy)
CUT_THRESHOLD = 5.0            # a string is cut when a ball comes within
CUT_OFFSET = 15.0              #   threshold + ball radius - offset of it (28px reach)
FPS = 60
SUBSTEPS = 3                   # physics sub-steps per frame - precise collisions at
                               #   endgame speeds (no ghosting/overlap)
SUDDEN_DEATH_AT = 90.0         # at this time no NEW lifelines appear - the web can
                               #   only shrink, so the battle must end by decay (1:30)
PRE_DROP_S = 3.0              # the slow-mo runs over the 3s before the main drop
PRE_DROP_FLOOR = 0.3          # slow-mo depth: the field eases down to 30% speed
POST_DROP_MULT = 2.0          # after the drop the battle runs at 2x the speed it
                              #   recorded just before the slow-mo - the frantic
                              #   finish (never clamped)

Point = Tuple[float, float]


@dataclass
class Arena:
    cx: float
    cy: float
    radius: float


@dataclass
class Ball:
    id: int
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    base_speed: float = SPEED   # speed this ball recovers toward
    alive: bool = True
    lifelines: List[Point] = field(default_factory=list)   # rim anchor points
    # battle stats
    bounces: int = 0
    collisions: int = 0
    lifelines_created: int = 0
    lifelines_cut: int = 0
    kills: int = 0
    last_cutter: Optional["Ball"] = None   # ball that cut the most recent string
    cuts_dealt: int = 0        # successful string cuts this ball has dealt


def create_balls(rng: random.Random, arena: Arena, radius: float, count: int,
                 speed: float = SPEED) -> List[Ball]:
    """Spawn `count` balls evenly around the rim, aimed at the centre +/- 15 deg,
    each with 3 starting lifelines pointing at the rim behind it."""
    balls: List[Ball] = []
    for i in range(count):
        ang = 2.0 * math.pi * i / count
        x = arena.cx + SPAWN_FRAC * arena.radius * math.cos(ang)
        y = arena.cy + SPAWN_FRAC * arena.radius * math.sin(ang)
        target = math.atan2(arena.cy - y, arena.cx - x)
        heading = target + rng.uniform(-TO_CENTER_DEVIATION, TO_CENTER_DEVIATION)
        base_speed = speed * rng.uniform(*SPEED_VARIATION)
        ball = Ball(id=i, x=x, y=y, vx=base_speed * math.cos(heading),
                    vy=base_speed * math.sin(heading), radius=radius,
                    base_speed=base_speed)
        _init_lifelines(ball, arena)
        balls.append(ball)
    return balls


def _init_lifelines(ball: Ball, arena: Arena) -> None:
    """The starting strings, spread evenly across the rim arc directly behind
    the ball (LIFELINE_INITIAL of them)."""
    radial = math.atan2(ball.y - arena.cy, ball.x - arena.cx)
    for i in range(LIFELINE_INITIAL):
        t = i / (LIFELINE_INITIAL - 1) if LIFELINE_INITIAL > 1 else 0.5
        offset = -LIFELINE_SPREAD + 2.0 * LIFELINE_SPREAD * t
        a = radial + offset
        ball.lifelines.append((arena.cx + arena.radius * math.cos(a),
                               arena.cy + arena.radius * math.sin(a)))
        ball.lifelines_created += 1


def _used_degrees(ball: Ball, arena: Arena) -> set:
    """Integer degree slots (0-359) already occupied by this ball's strings."""
    used = set()
    for ax, ay in ball.lifelines:
        deg = int(math.degrees(math.atan2(ay - arena.cy, ax - arena.cx)) % 360)
        used.add(deg)
    return used


def _free_degree(rng: random.Random, radial_deg: float, used: set) -> Optional[int]:
    """A free integer degree slot, preferring ones near the ball's radial
    direction, then expanding outward. None if all 360 are taken."""
    spread = math.degrees(LIFELINE_SPREAD)
    lo = max(0, int(radial_deg - spread))
    hi = min(359, int(radial_deg + spread))
    candidates = list(range(lo, hi + 1))
    rng.shuffle(candidates)
    for deg in candidates:
        if deg not in used:
            return deg
    for off in range(1, 360):
        for deg in (int(radial_deg + off) % 360, int(radial_deg - off) % 360):
            if deg not in used:
                return deg
    return None


def grow_lifelines(rng: random.Random, ball: Ball, arena: Arena) -> int:
    """Wall-bounce growth: ~40% of current strings, rounded up, at least 1,
    capped at MAX_GAIN_PER_BOUNCE. New strings go to fresh integer degree
    slots (one per degree) up to the MAX_LIFELINES cap, so the web stays
    tidy instead of clumping, and late-game growth can't outpace cutting."""
    count = max(MIN_GAIN_PER_BOUNCE, math.ceil(len(ball.lifelines) * LIFELINE_GAIN_FRACTION))
    count = min(count, MAX_GAIN_PER_BOUNCE)
    used = _used_degrees(ball, arena)
    radial_deg = math.degrees(math.atan2(ball.y - arena.cy, ball.x - arena.cx)) % 360.0
    added = 0
    for _ in range(count):
        if len(ball.lifelines) >= MAX_LIFELINES:
            break
        deg = _free_degree(rng, radial_deg, used)
        if deg is None:
            break
        a = math.radians(deg)
        ball.lifelines.append((arena.cx + arena.radius * math.cos(a),
                               arena.cy + arena.radius * math.sin(a)))
        used.add(deg)
        ball.lifelines_created += 1
        added += 1
    return added


def bounce_off_wall(rng: random.Random, ball: Ball, arena: Arena) -> bool:
    """Reflect the ball off the arena wall with a small wobble. Returns True if bounced."""
    dx = ball.x - arena.cx
    dy = ball.y - arena.cy
    dist = math.hypot(dx, dy)
    if dist + ball.radius > arena.radius:
        nx, ny = dx / dist, dy / dist
        ball.x = arena.cx + (arena.radius - ball.radius) * nx
        ball.y = arena.cy + (arena.radius - ball.radius) * ny
        dot = ball.vx * nx + ball.vy * ny
        vx = ball.vx - 2 * dot * nx
        vy = ball.vy - 2 * dot * ny
        wobble = rng.uniform(-BOUNCE_WOBBLE, BOUNCE_WOBBLE)
        c, s = math.cos(wobble), math.sin(wobble)
        ball.vx = vx * c - vy * s
        ball.vy = vx * s + vy * c
        ball.bounces += 1
        return True
    return False


def collide_balls(a: Ball, o: Ball) -> float:
    """Elastic collision (equal masses) with positional separation.
    Returns the impact magnitude (0.0 if no collision)."""
    dx = o.x - a.x
    dy = o.y - a.y
    dist = math.hypot(dx, dy)
    if dist == 0 or dist >= a.radius + o.radius:
        return 0.0
    nx, ny = dx / dist, dy / dist
    rel = (a.vx - o.vx) * nx + (a.vy - o.vy) * ny
    a.vx -= rel * nx
    a.vy -= rel * ny
    o.vx += rel * nx
    o.vy += rel * ny
    overlap = (a.radius + o.radius - dist) * 0.5
    a.x -= overlap * nx
    a.y -= overlap * ny
    o.x += overlap * nx
    o.y += overlap * ny
    a.collisions += 1
    o.collisions += 1
    return abs(rel)


def point_segment_dist(px: float, py: float, x1: float, y1: float,
                       x2: float, y2: float) -> float:
    """Distance from point (px, py) to the line segment (x1,y1)-(x2,y2)."""
    vx, vy = x2 - x1, y2 - y1
    norm = vx * vx + vy * vy
    if norm == 0:
        return math.hypot(px - x1, py - y1)
    u = ((px - x1) * vx + (py - y1) * vy) / norm
    u = max(0.0, min(1.0, u))
    cx, cy = x1 + u * vx, y1 + u * vy
    return math.hypot(px - cx, py - cy)


def ramp_speed_multiplier(t: float) -> float:
    """Field-wide speed factor on an inverse-exponential curve:
    mult(t) = FLOOR + (MAX - FLOOR) * (1 - e^(-t / SPEED_TAU)).

    Very slow start, fast acceleration, levelling off toward MAX_SPEED_MULT -
    a tense opening that rockets into a frantic endgame. This is the fallback
    for battles that have no energy curve (no timeline given)."""
    frac = 1.0 - math.exp(-t / SPEED_TAU)
    return START_RAMP_FLOOR + (MAX_SPEED_MULT - START_RAMP_FLOOR) * frac


def _energy_at(t: float, energy_curve: List[List[float]]) -> float:
    """Linear interpolation on the energy curve (assumed sorted by time)."""
    if not energy_curve:
        return 0.0
    if t <= energy_curve[0][0]:
        return energy_curve[0][1]
    for i in range(len(energy_curve) - 1):
        t0, e0 = energy_curve[i]
        t1, e1 = energy_curve[i + 1]
        if t0 <= t <= t1:
            if t1 == t0:
                return e0
            return e0 + (e1 - e0) * (t - t0) / (t1 - t0)
    return energy_curve[-1][1]


def energy_speed_multiplier(t: float, energy_curve: List[List[float]]) -> float:
    """Speed target follows the song's energy (0..1) from the calm floor up to
    the frantic max - the intro drifts, the drop slams, the breakdown eases.

    The energy is gated by the same slow-opening progress as the time ramp, so
    the opening is always calm and the battle builds, while the song's shape
    decides when it slams and when it eases."""
    e = _energy_at(t, energy_curve)
    e = max(0.0, min(1.0, e))
    progress = 1.0 - math.exp(-t / SPEED_TAU)
    return START_RAMP_FLOOR + (MAX_SPEED_MULT - START_RAMP_FLOOR) * progress * e


def drop_speed_multiplier(t: float, drop_t: float, base_level: float = 1.0) -> float:
    """Time ramp -> slow-mo -> 2x recorded speed at the main drop.

    The battle builds on the normal ramp (scaled by the song's overall level -
    loud songs race, calm ones cruise). Just before the main drop the ramp's
    speed is RECORDED, the field eases into slow-mo for a few seconds, then AT
    the drop the camera zooms and the battle jumps to double the recorded speed
    - the frantic finish. The song is NOT followed pulse-by-pulse here: the
    main drop is the one moment the music gets to shape the battle dynamics.
    """
    base = ramp_speed_multiplier(t) * base_level
    # The cruising speed just before the slow-mo begins: the finish runs at 2x this.
    recorded = ramp_speed_multiplier(drop_t - PRE_DROP_S) * base_level
    if t >= drop_t:
        return recorded * POST_DROP_MULT
    lead = drop_t - t
    if lead >= PRE_DROP_S:
        return base
    k = lead / PRE_DROP_S                   # 1 at slow-mo start, 0 at the drop
    ease = k * k * (3.0 - 2.0 * k)          # smoothstep 1 -> 0
    return base * (PRE_DROP_FLOOR + (1.0 - PRE_DROP_FLOOR) * ease)


def restore_speed(rng: random.Random, ball: Ball, speed_mult: float = 1.0) -> None:
    """Nudge a ball's speed back toward base_speed * speed_mult each frame.

    Real collisions can leave two balls nearly stationary, which makes a
    final duel drag. Recovery is faster for balls with more lifelines, so
    stringy balls get back up to speed (and into the fight) first.
    """
    target = ball.base_speed * speed_mult
    current = math.hypot(ball.vx, ball.vy)
    rate = RESTORE_RATE * (1.0 + len(ball.lifelines) / 10.0) / FPS
    if current < 1e-6:
        # Completely stopped: give it a fresh seeded direction at target speed.
        a = rng.uniform(0.0, TAU)
        ball.vx = target * math.cos(a)
        ball.vy = target * math.sin(a)
        return
    new = current + (target - current) * min(1.0, rate)
    scale = new / current
    ball.vx *= scale
    ball.vy *= scale


def cut_lifelines(attacker: Ball, others: List[Ball]) -> None:
    """The attacker cuts any string of another ball it passes close to."""
    cut_radius = attacker.radius - CUT_OFFSET
    for other in others:
        if other is attacker or not other.alive:
            continue
        remaining: List[Point] = []
        for (ax, ay) in other.lifelines:
            d = point_segment_dist(attacker.x, attacker.y, other.x, other.y, ax, ay)
            if d <= CUT_THRESHOLD + cut_radius:
                other.lifelines_cut += 1
                other.last_cutter = attacker
                attacker.cuts_dealt += 1
            else:
                remaining.append((ax, ay))
        other.lifelines = remaining


class Battle:
    """Steps the arena battle forward frame by frame. Deterministic per seed."""

    def __init__(self, seed: int, arena: Arena, ball_radius: float = 38.0,
                 num_balls: int = 5, speed: float = SPEED) -> None:
        self.rng = random.Random(seed)
        self.arena = arena
        self.balls = create_balls(self.rng, arena, ball_radius, num_balls, speed=speed)
        self.speed = speed
        self.time = 0.0
        self.collisions: List[Dict] = []
        self.wall_bounces: List[Dict] = []
        self.eliminations: List[Dict] = []
        # One-per-battle event log (written to events.json): sudden death is the
        # first entry; immunity, walls, speed boosts and the musical drop slot
        # into the same channel later.
        self.events: List[Dict] = []
        self.sudden_death_at: Optional[float] = SUDDEN_DEATH_AT   # None disables
        self._sudden_death_active = False
        # Event mechanics (set by simulation/events.py): a no-elimination
        # window and a temporary field-speed surge.
        self.immunity_until: float = 0.0     # no eliminations while time < this
        self.speed_boost_until: float = 0.0  # field speed surge while time < this
        self.speed_boost_mult: float = 1.5
        # Music-driven pacing: when a timeline is supplied, the ONE main drop
        # (the song's big surge, usually 40-70s) drives the battle - the field
        # runs the normal ramp, dips into slow-mo just before it, then doubles
        # the recorded speed AT it (drop_speed_multiplier). -1 = no drop.
        self.main_drop_at: float = -1.0
        # Overall pace scale: the song's "how intense is it" level (a constant,
        # not a curve) so loud songs race and calm ones cruise without pulsing.
        self.speed_level: float = 1.0
        self.energy_curve: List[List[float]] = []
        self._speed_mult_smoothed: float = START_RAMP_FLOOR
        self._winner: Optional[int] = None

    def _check_events(self) -> None:
        """Emit one-time battle events as the fight progresses.

        Sudden death (default 90 s): from this point wall bounces no longer
        grow lifelines - the web can only shrink, so the battle must resolve by
        decay. Called every step; each event fires exactly once.
        """
        if (not self._sudden_death_active and self.sudden_death_at is not None
                and self.time >= self.sudden_death_at):
            self._sudden_death_active = True
            self.events.append({"type": "sudden_death", "t": self.sudden_death_at})

    def step(self, dt: float = 1.0 / FPS) -> None:
        self._check_events()
        # Sub-step the motion + collisions so endgame speeds stay precise.
        sub_dt = dt / SUBSTEPS
        for _ in range(SUBSTEPS):
            # Integrate positions.
            for b in self.balls:
                if not b.alive:
                    continue
                b.x += b.vx * sub_dt
                b.y += b.vy * sub_dt
            # Wall bounces grow lifelines (unless sudden death stopped growth).
            for b in self.balls:
                if not b.alive:
                    continue
                if bounce_off_wall(self.rng, b, self.arena):
                    if not self._sudden_death_active:
                        grow_lifelines(self.rng, b, self.arena)
                    self.wall_bounces.append({"t": round(self.time, 3), "ball_id": b.id})
            # Ball-ball collisions (no lifeline growth from these).
            for i in range(len(self.balls)):
                for j in range(i + 1, len(self.balls)):
                    a, o = self.balls[i], self.balls[j]
                    if not a.alive or not o.alive:
                        continue
                    impact = collide_balls(a, o)
                    if impact:
                        self.collisions.append({
                            "t": round(self.time, 3),
                            "ball_a": a.id,
                            "ball_b": o.id,
                            "impact": round(min(1.0, impact / self.speed), 2),
                        })
        # Balls recover speed toward their (ramped) base speed. The ramp makes
        # the whole field ease from a slow opening up to full battle speed. A
        # main drop overrides the ramp with the slow-then-bam choreography;
        # the energy-curve follower remains for timelines that set it directly.
        if self.main_drop_at >= 0.0:
            target_mult = drop_speed_multiplier(self.time, self.main_drop_at,
                                                self.speed_level)
        elif self.energy_curve:
            target_mult = energy_speed_multiplier(self.time, self.energy_curve)
        else:
            target_mult = ramp_speed_multiplier(self.time)
        # Smooth the target: the raw energy curve is noisy (10Hz samples) and
        # the physics should pulse with the music, not jitter frame to frame.
        self._speed_mult_smoothed += (target_mult - self._speed_mult_smoothed) * min(1.0, dt * 4.0)
        speed_mult = self._speed_mult_smoothed
        if self.time < self.speed_boost_until:
            speed_mult *= self.speed_boost_mult
        for b in self.balls:
            if b.alive:
                restore_speed(self.rng, b, speed_mult)
        # Strings get cut by passing balls (from the very first frame - the
        # slow opening is what keeps things calm, not an immunity period).
        for b in self.balls:
            if b.alive:
                cut_lifelines(b, self.balls)
        # Zero strings = eliminated (immunity can delay this).
        for b in self.balls:
            if b.alive and not b.lifelines and self.time >= self.immunity_until:
                b.alive = False
                killer_id: Optional[int] = None
                if b.last_cutter is not None:
                    b.last_cutter.kills += 1
                    killer_id = b.last_cutter.id
                self.eliminations.append({
                    "t": round(self.time, 3),
                    "ball_id": b.id,
                    "killer": killer_id,
                })
        self.time += dt

    def is_over(self) -> bool:
        if self._winner is not None:
            return True
        alive = [b for b in self.balls if b.alive]
        if len(alive) == 1:
            self._winner = alive[0].id
            return True
        return False

    @property
    def winner(self) -> Optional[int]:
        return self._winner

    def frame_state(self) -> List[Dict]:
        """Per-ball state for one events.json frame."""
        return [{
            "id": b.id,
            "x": round(b.x, 2),
            "y": round(b.y, 2),
            "lifelines": len(b.lifelines),
            "lifeline_anchors": [[round(p[0], 2), round(p[1], 2)] for p in b.lifelines],
            "kills": b.kills,
            "alive": b.alive,
        } for b in self.balls]

    def stats(self) -> Dict[int, Dict]:
        return {b.id: {
            "kills": b.kills,
            "bounces": b.bounces,
            "collisions": b.collisions,
            "lifelines_created": b.lifelines_created,
            "lifelines_cut": b.lifelines_cut,
            "cuts_dealt": b.cuts_dealt,
        } for b in self.balls}
