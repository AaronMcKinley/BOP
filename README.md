# Beat-Synced Arena Battle Generator

Automatically generates polished, vertical (9:16) short-form videos from a song file. A circular arena contains colored balls with lifelines; they bounce off the walls and each other, gaining/losing lifelines on impact, until one winner remains. The song drives pacing, arena pulse, and effect timing — the goal is for the animation to feel like it's performing to the track, not just playing over it.

## Pipeline

```
song.mp3
   │
   ▼
analyze.py        (Python / librosa)
   │  → timeline.json
   │    beats, downbeats, tempo, energy envelope, bass-hit events,
   │    section boundaries (intro / build / drop / resolution)
   ▼
simulate.py        (Python / numpy)
   │  → runs the physics headless, hundreds of seeds, no rendering
   │  → scores each run against timeline.json (does the pacing/arc fit the song?)
   │  → keeps the best-scoring seed
   │  → events.json
   │    per-frame ball positions/velocities/lifelines, collision log,
   │    elimination log, arena pulse curve, speed-multiplier curve
   ▼
render.gd           (Godot 4, headless)
   │  reads timeline.json + events.json, drives a pre-built scene
   │  (arena, ball template, trail/glow shaders, particle templates)
   │  native HDR bloom, GPUParticles2D, motion blur
   │  → raw_output.mov / frame sequence (via --write-movie)
   ▼
mux.py               (ffmpeg subprocess)
   │  combine rendered video + original song, loudness-normalize,
   │  encode per-platform (9:16 H.264/AAC), trim to highlight window
   ▼
final.mp4  (TikTok / Shorts / Reels / Facebook ready)
```

Each stage is a standalone script/executable that reads and writes plain JSON or media files on disk. No stage depends on another being in memory — you can re-run any single stage in isolation, inspect intermediate JSON by hand, or swap an implementation later without touching the rest of the chain.

## Why this stack

- **Simulation stays in Python** — fast to iterate, numpy is plenty for circle/arena collision math, easy to batch-run hundreds of headless seeds for selection.
- **Analysis stays in Python** — librosa handles beat tracking, onset detection, and energy curves without needing a heavier ML dependency to start.
- **Rendering moves to Godot, headless** — this is the one part that actually needs a real compositor. Native HDR glow/bloom, particle systems, and motion blur are what separate "looks generated" from "looks edited." `--write-movie` exports deterministically and faster than real-time with no browser, no screenshot loop, no extra automation layer.
- **The Godot *scene* (arena, ball shader, particle templates) is built once, semi-interactively, in the editor** — then frozen as a template. Every actual render run afterward is 100% headless and CLI-driven from JSON; the editor is a one-time asset-building tool, not a pipeline dependency.

## Folder structure

```
arena-generator/
├── README.md
├── .gitignore
├── requirements.txt              # librosa, numpy, scipy, etc.
├── config/
│   ├── director_defaults.json    # tunable ranges: speed curve, pulse amplitude,
│   │                              #   intro step size, drop treatment options
│   └── physics_defaults.json     # restitution, ball count range, mass scaling,
│                                  #   lifeline rules
├── songs/
│   └── (input .mp3 / .wav files go here — gitignored except maybe a sample)
│
├── analysis/
│   ├── analyze.py                # song.mp3 -> timeline.json
│   ├── beat_detect.py            # beat/downbeat/tempo extraction
│   ├── energy.py                 # RMS + band-passed bass envelope
│   └── sections.py               # structural segmentation (intro/build/drop/etc.)
│
├── simulation/
│   ├── simulate.py               # runs one headless physics pass -> run_<seed>.json
│   ├── physics.py                # ball state, collision resolution, wall bounce
│   ├── director.py               # timeline.json -> per-frame parameter curves
│   │                              #   (speed multiplier, pulse amplitude, triggers)
│   ├── select.py                 # runs N seeds, scores each against timeline.json,
│   │                              #   picks/returns the best -> events.json
│   └── scoring.py                # the fit function used by select.py
│
├── render/
│   ├── project.godot             # Godot project file
│   ├── scenes/
│   │   ├── arena.tscn            # arena ring + WorldEnvironment glow settings
│   │   ├── ball.tscn             # ball template: gradient/rim-light shader, trail
│   │   ├── particles_impact.tscn # collision impact burst template
│   │   └── particles_eliminate.tscn
│   ├── shaders/
│   │   ├── ball_shading.gdshader
│   │   ├── trail.gdshader
│   │   └── arena_pulse.gdshader
│   └── scripts/
│       ├── render.gd             # headless entry point: reads events.json,
│       │                          #   steps frames, drives nodes, triggers particles
│       └── json_loader.gd
│
├── postprocess/
│   ├── mux.py                    # ffmpeg subprocess: mux audio, normalize loudness,
│   │                              #   encode, trim to highlight window
│   └── platform_presets.json     # per-platform export settings (9:16, bitrate, etc.)
│
├── output/
│   ├── timelines/                # analyze.py outputs, one per song
│   ├── runs/                     # simulate.py candidate runs (gitignored, disposable)
│   ├── events/                   # select.py winning events.json per song
│   ├── renders/                  # raw Godot video output before muxing
│   └── final/                    # finished mp4s, ready to post
│
├── scripts/
│   └── run.py                    # top-level orchestrator:
│                                  #   python scripts/run.py songs/track.mp3
│                                  #   → runs the whole pipeline end to end
│
└── tests/
    ├── test_physics.py           # determinism checks, collision correctness
    └── test_scoring.py
```

## Usage (target end state)

```bash
python scripts/run.py songs/track.mp3
```

This runs the full chain — analyze → simulate/select → render → mux — and writes `output/final/track.mp4`. Each stage can also be run individually while developing:

```bash
python analysis/analyze.py songs/track.mp3 --out output/timelines/track.json
python simulation/select.py --timeline output/timelines/track.json --seeds 500 --out output/events/track.json
godot --headless --script render/scripts/render.gd -- --events output/events/track.json --out output/renders/track.mov
python postprocess/mux.py --video output/renders/track.mov --audio songs/track.mp3 --out output/final/track.mp4
```

## Data contracts

**`timeline.json`** (analysis → simulation & render)
```json
{
  "duration_s": 187.4,
  "bpm": 128.0,
  "beats": [0.47, 0.94, 1.41, ...],
  "downbeats": [0.47, 2.35, 4.23, ...],
  "energy_curve": [[0.0, 0.02], [0.1, 0.03], ...],
  "bass_hits": [1.41, 2.82, ...],
  "sections": [
    {"label": "intro", "start": 0.0, "end": 16.0},
    {"label": "build", "start": 16.0, "end": 32.0},
    {"label": "drop", "start": 32.0, "end": 64.0}
  ]
}
```

**`events.json`** (simulation → render)
```json
{
  "seed": 4821,
  "fps": 60,
  "frames": [
    {"t": 0.0, "balls": [{"id": 0, "x": 120.4, "y": 300.1, "lifelines": 3, "alive": true}, ...]},
    ...
  ],
  "collisions": [{"t": 3.21, "ball_a": 2, "ball_b": 5, "impact": 0.8}],
  "wall_bounces": [{"t": 1.41, "ball_id": 0}],
  "eliminations": [{"t": 12.7, "ball_id": 3}],
  "pulse_curve": [[0.0, 1.0], [0.47, 1.08], ...],
  "speed_curve": [[0.0, 0.2], [2.0, 0.35], ...]
}
```

These two files are the entire interface between stages — keep them stable and everything downstream (or a future alternative renderer) can be swapped without touching the rest of the pipeline.

## Music ↔ animation design

The battle should feel like it's performing the track, not just playing over it.
The music drives the animation at three levels:

**1. Micro — beat-level motion.** Balls pulse on downbeats, the arena pulses with
the energy curve, and collisions flash on bass hits. This puts the *feel* of the
motion on the beat grid (`pulse_curve` + beat-aligned effects).

**2. Meso — section-level rules (the crescendo maker).** The battle rules change
with the song's structure. The lifeline economy is the throttle: when balls can
grow strings, nobody dies; when strings get cut faster than they grow,
eliminations happen.

- **Intro** — calm: slow balls; balls gain lifelines on bounces (no deaths).
- **Build** — speed ramps with the energy curve; lifeline gains slow, cuts start,
  and the first eliminations trickle in.
- **Drop** — full speed, lifeline gains at minimum, cuts at maximum, the arena
  tightens → mass eliminations, chaos, the climax.
- **Resolution** — the final duel → winner.

(No breakdown/outro for now — the arc stays tight so the video stays short.)

**3. Macro — scoring + seed selection (optional, deferred).** Run many seeds and
keep the one whose arc best fits the song. Postponed until we know the emergent
sim needs it.

**Video length.** Never force a fixed duration. The battle runs its course, the
scoreboard resolves, and the music continues to a natural lull/break before the
video ends - a video can be 45 s or 68 s depending on the track and battle. The
music is never cut abruptly to hit an arbitrary length.

## Scoring, leaderboard & seasons

Every battle scores by finishing position (4/3/2/1/0: 1st 4, 2nd 3, 3rd 2, 4th 1,
5th 0) and feeds a season leaderboard (`config/stats.json` already tracks wins,
kills, etc. per ball). Seasons last ~2 months (~60 battles at one a day), each
with its own visual theme - Season 1 is the neon/Tron-inspired look. Leaderboard
data exists from day one even before any public website.

## Video structure (the ending)

1. Final kill lands on (or near) a beat
2. 🏆 WINNER reveal - ~2.5 s
3. Scoreboard - ~2.5-5 s: points awarded (39 → +4 → 43), position changes
   animated, 👑 NEW LEADER when someone takes #1
4. No more information
5. The music continues to a natural lull/break
6. Video ends there

## Sudden Death

The natural maximum for a long battle: at 1:30 all remaining balls drop to
exactly 1 lifeline and can no longer grow strings. Movement and collisions
continue normally, lifelines can still be cut, and the last ball standing wins.
Triggered with a significant visual/musical transition (arena pulse, brief
freeze/slowdown, title card, 1-lifeline indicators).

## Procedural events

Events are context-aware, not purely random: they only fire when the battle
state AND the musical moment suit them (conditions, probability, musical
suitability, cooldown, priority). Roughly 1-2 major events per video maximum.
Events can branch - music section → battle state → eligibility → decision →
event → new state → new opportunities - so different videos emerge organically
without scripting. Examples: **1V1** (two balls remain + a musical break →
freeze, camera push-in, "1V1", resume on the beat) and Sudden Death.

## Announcer

A pre-generated deep arcade/esports-style voice ("FINAL TWO", "SUDDEN DEATH",
"ELIMINATED", "NEW LEADER", ...) placed at musically suitable beats - never
generated per video. The AI makes the sound; BOP makes the timing. The music
stays dominant (light ducking while the voice speaks).

## Perceived speed

Fast battles are short battles, so BOP makes motion *feel* fast instead of
making it fast: motion trails, velocity glow, impact particles, camera
movement/zoom, arena pulse, and progressive intensity. The battle has dynamic
range - calm → build → drop → final duel - rather than maximum intensity the
whole time.

## Battle data

Every battle saves its metadata for reproducibility and leaderboards: battle
number, seed, season, track, BPM, events triggered, winner, points, duration.

## Short battle handling

Battles under 45 s are re-rolled for now (the dev pipeline already does this).
Short-but-interesting seeds are kept for a future quality system that judges
battles on more than duration: music sync, close finish, interaction density,
event potential, visual interest.

## Launch checklist

Watermark, visual polish (particles, arena pulse, winner screen, scoreboard),
automatic stats, music metadata/credits, leaderboard data, first batch of
videos. Then **stop building and publish** - don't over-invest before there's an
audience. Music licensing is tracked per track (source, permissions, credit
requirements, date checked).

## Status

- [x] `analyze.py` — beat/energy/section extraction → `timeline.json`
- [x] `physics.py` + `simulate.py` — deterministic battle sim → `events.json` (re-rolls for ≥45 s)
- [ ] `director.py` — timeline → section-driven parameter curves + dynamic intensity
- [x] Godot scene — neon arena, pulsing rings, grid, particles, KILLS scoreboard
- [x] `render.gd` — data-driven playback of events.json
- [x] `mux.py` — minimal ffmpeg mux/upscale/encode
- [ ] Winner screen + scoreboard (points, positions, leaderboard)
- [ ] Sudden Death rule + 1V1 event presentation
- [ ] Announcer voice placement
- [ ] Motion trails + camera movement (perceived speed)
- [ ] Natural musical ending (breaks-based)
- [ ] Battle metadata / leaderboard data saving
- [ ] `run.py` — end-to-end orchestrator
- [ ] Platform presets + loudness normalization in `mux.py`