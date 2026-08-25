# BOP — Beat-Synced Arena Battle Generator

A circular neon arena, colored balls with lifelines, bouncing and colliding until one winner remains — turned into a polished vertical (9:16) short-form video.

**Status:** the core pipeline works end-to-end — create a battle, watch it, save it (video + leaderboard + stats). The music-sync layer (making the battle *perform* the track) is the active roadmap item — see [TODO.md](TODO.md).

## Current pipeline

### Create a battle — `./scripts/create.sh`

Runs everything with no arguments, then opens the result:

1. **`simulate.py`** — deterministic physics battle on a fresh random seed (skips seeds already used, re-rolls until ≥ 45 s). Writes `output/events/current.json`.
2. **Godot** (`render.gd`, Movie Maker mode) — plays `current.json` frame-by-frame → `output/renders/current.avi`. A window flashes during this; Movie Maker needs a real display.
3. **`mux.py`** — upscales to 1080×1920, encodes H.264/AAC, muxes the song, fades the music out over the winner screen, and lays a faint `BOP` watermark below the arena → `output/renders/current.mp4`, then opens it for review.

### Save a battle — `python scripts/save.py`

Zero arguments. Picks up `current.mp4` + `current.json` and:

- moves the video to `output/publish/<song>/battle_NNN.mp4` (auto-incremented, never overwrites; prunes to the newest 10 per song)
- writes `battle_NNN.json` metadata (seed, winner, positions, points, stats, timestamp)
- updates the season leaderboard `config/stats.json` (points 4/3/2/1/0, wins, podiums, kills, …)
- records the seed in `config/used_seeds.json` so the same battle is never created again — and refuses to save a battle whose seed is already recorded

### Leaderboard previews — `python scripts/mock_stats.py`

Seeds a tight demo leaderboard so the end-of-video league-table movement is easy to see without waiting for real battles. `--reset` wipes to a fresh zero season.

## Folder structure

```
BOP/
├── AGENTS.md  README.md  TODO.md
├── config/
│   ├── stats.json            # season leaderboard (source of truth)
│   └── used_seeds.json       # seeds already saved (created on first save)
├── songs/                    # input music (gitignored)
├── analysis/                 # song → timeline.json (standalone, not wired in yet)
│   ├── analyze.py  beat_detect.py  energy.py
├── simulation/
│   ├── physics.py            # deterministic arena battle
│   ├── simulate.py           # battle → events.json (fresh seed, ≥ 45 s)
│   ├── scoring.py            # finishing positions, points, leaderboard math
│   ├── seed_registry.py      # used-seed tracking (shared by simulate + save)
│   └── stats_manager.py      # leaderboard loading helpers
├── render/                   # Godot 4.7 project (run via flatpak)
│   ├── project.godot  scenes/  fixtures/
│   └── scripts/              # render.gd (entry), arena.gd, ball.gd,
│                              #   winner_screen.gd, ball_badge.gd, json_loader.gd
├── postprocess/
│   └── mux.py                # upscale + encode + mux song + fade + watermark
├── scripts/
│   ├── create.sh             # create + watch a battle (zero args)
│   ├── save.py               # save a battle + update stats/seed (zero args)
│   └── mock_stats.py         # seed / reset the leaderboard
├── output/                   # timelines/ events/ renders/ runs/ publish/ (gitignored)
└── tests/                    # 24 tests: physics, scoring, seed registry
```

Requires: Python 3.14 (`.venv`), Godot 4.7 via `flatpak run org.godotengine.Godot`, and ffmpeg/ffprobe.

## Usage

```bash
./scripts/create.sh                  # simulate → render → mux → play
python scripts/save.py               # keep the battle (publish + stats + seed)
python scripts/mock_stats.py         # demo standings for table previews
python scripts/mock_stats.py --reset # fresh zero season
```

Each stage also runs standalone:

```bash
.venv/bin/python simulation/simulate.py --seed 123 --balls 5 --out output/events/x.json
flatpak run org.godotengine.Godot --path render --resolution 540x960 \
  --write-movie out.avi --fixed-fps 60 -- --events output/events/x.json
.venv/bin/python postprocess/mux.py --video out.avi \
  --audio songs/MONODY-BIMONTE-REMIX.wav --out out.mp4
```

## Data contracts

These JSON files are the interface between stages — keep them stable so any
stage can be swapped without touching the rest of the chain.

**`timeline.json`** (analysis → future simulation/render) — what `analysis/analyze.py` produces:

```json
{
  "duration_s": 187.4, "bpm": 128.0,
  "beats": [0.47, 0.94, ...], "downbeats": [0.47, 2.35, ...],
  "energy_curve": [[0.0, 0.02], ...], "bass_hits": [1.41, 2.82, ...],
  "sections": [{"label": "intro", "start": 0.0, "end": 16.0}, ...]
}
```

**`events.json`** (simulation → render):

```json
{
  "seed": 4821, "fps": 60,
  "frames": [{"t": 0.0, "balls": [{"id": 0, "x": 120.4, "y": 300.1,
               "lifelines": 3, "alive": true}, ...]}],
  "collisions": [{"t": 3.21, "ball_a": 2, "ball_b": 5, "impact": 0.8}],
  "wall_bounces": [{"t": 1.41, "ball_id": 0}],
  "eliminations": [{"t": 12.7, "ball_id": 3}],
  "pulse_curve": [[0.0, 1.0], ...], "speed_curve": [[0.0, 0.2], ...],
  "winner": {"ball_id": 1, "t": 47.6}, "stats": {...},
  "positions": {...}, "points": {...},
  "leaderboard_before": {...}, "leaderboard": [...]
}
```

`events.json` is a superset of the base contract — the scoring fields
(`winner`, `stats`, `positions`, `points`, `leaderboard_before`,
`leaderboard`) are what the end-of-video winner/league-table sequence reads.

## Scoring, leaderboard & seasons

Battles score by finishing position (1st 4 / 2nd 3 / 3rd 2 / 4th 1 / 5th 0) and
feed a season leaderboard. `config/stats.json` tracks points, wins, losses,
podiums, kills, eliminations, collisions, and total battles per ball. Seasons
last ~2 months (~60 battles at one a day); Season 1 is the neon/Tron look.
`simulate.py` embeds the standings (before + after) into `events.json`, and the
winner screen shows them.

## Video structure (the ending)

1. The battle runs its course (≥ 45 s) until one ball remains.
2. **Winner reveal** — 2.5 s: WINNER title, badge, battle stats. The music fade starts here.
3. **League table** — 6 s: the whole table fades in at the *old* standings, then all rows slide together to their new positions with ▲/▼ movement arrows.
4. The music fades out over the whole sequence (6 s esin taper) and the video ends.

Ending roadmap: final kill landing on/near a beat, so the winner reveal lands
with the music. (The current reveal → animated table → music-fade sequence is
otherwise locked in.)

## Roadmap

The product goal is a battle that *performs* the track, not just plays over it.
The remaining work is tracked in [TODO.md](TODO.md); the next milestone is the
**music-driven battle**:

- `director.py` — `timeline.json` → per-frame pulse/speed curves and
  section-aware rules (intro calm → build ramp → drop chaos → resolution).
- Seed selection — run many seeds, score each against the timeline, keep the
  best arc.
- Beat-aligned rendering — collision flashes on bass hits, arena pulse on the
  energy curve, ball pulse on downbeats.

Then: Sudden Death rule, 1V1 events, announcer voice, perceived-speed motion
(trails/camera/glow), and platform presets + loudness normalization in `mux.py`.

## Launch checklist

Watermark, visual polish (particles, arena pulse, winner screen), music
metadata/credits, leaderboard data, a first batch of videos — then **stop
building and publish**. Music licensing is tracked per track (source,
permissions, credit requirements, date checked).

