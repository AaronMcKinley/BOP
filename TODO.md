# TODO

The core pipeline works end-to-end (create → save → leaderboard). Priorities
from the brainstorm: the endgame must feel frantic, battles must never drag,
every seed should make a good video, and the presentation gets beat-sync +
voice overs.

## 1 · Speed & feel — final settings (locked in)

- [x] `SPEED_TAU 35 → 50` — calmer build, same frantic endgame
- [x] `MAX_SPEED_MULT 4.0 → 5.5` — endgame ~3.9× by 60 s; data showed 6.5×+
      wrecked battle length, so 5.5 is the sweet spot
- [x] Lifeline growth stays `0.6` / `+10` — the doubling was tested, no benefit
- [x] Battle structure accepted: quick 3-ball cascade (~16 s) then a 1v1 duel.
      Radius, spawn position, opening floor and heading spread were all probed;
      none delay the 1v1 without hurting length
- [x] 6 balls rejected — kills the 60–90 s battles (max ~52 s vs ~71 s)
- [ ] Re-render to judge the current feel: endgame speed + scoreboard `+4 = 16`

## 2 · Sudden death & the events channel

- [x] `SUDDEN_DEATH_AT` 90 s: wall bounces stop growing lifelines from then on —
      existing lifelines stay untouched (no forced 1-lifeline); the battle
      resolves by decay, so it always ends soon after the cap
- [x] `events.json` now carries an `events` array (one-per-battle log);
      `{"type": "sudden_death", "t": 90.0}` is the first entry — immunity /
      walls / speed boosts / the musical drop slot into the same channel later
- [x] Event library (`simulation/events.py`): `sudden_death` / `immunity` /
      `speed_boost` functions plus a `roll()` dispatcher. Off by default —
      enable per battle with `./scripts/create.sh 0.5` (or `--event-chance`)
- [ ] Renderer reaction: "SUDDEN DEATH" banner + rim flash when the event fires
- [ ] Seed-fixing: decide how short seeds get handled — immunity / speed boost
      already exist to call; walls + the musical drop to design

## 3 · Events & pacing — every seed makes a good video

- [x] Energy-driven speed ramp: the field speed now follows the song's energy
      curve (gated by the slow-opening progress) via `simulate.py --timeline` —
      intro drifts, the drop slams, the breakdown eases. Bonus: 8/15 seeds
      now ≥45 s (was 5/30)
- [ ] Replace the crude "re-roll if < 45 s" with structured events so short
      seeds become long, interesting battles:
      - Opening buffer: no eliminations before ~15–20 s
      - Timed events keyed to sections: speed surges, string blooms, chaos
        windows, double-cut moments
- [ ] Beat-aligned rendering: collision flashes on bass hits, arena pulse
      (the arena already reads beats — extend to the balls).
- [ ] Optional seed scoring vs the timeline (arc fit, close finish) only if
      the events aren't enough on their own.

## 4 · Presentation beats

- [x] Spoke beat-sync: each ball's light-cycle spoke does 1 full revolution
      per beat (`TAU × BPM / 60`, set from the arena's timeline in render.gd);
      try 1 rev / 2 beats if the render looks too frantic
- [ ] Lifeline cut legibility: rim anchor dots kept (render-side clarity), but
      the outer-band cut rule was ROLLED BACK to the committed physics — it made
      cuts feel inconsistent, and stricter versions made battles 2–6 min. The
      centre is where the action naturally happens; forcing outer-circle cuts
      fights the game. Revisit only via the speed ramp / rim-dense strings,
      never a hard cut zone.
- [ ] Sound effects: procedural bounce tick, collision thump (scaled by
      impact), elimination whoosh, win sting — played at event times, ducked
      under the song.
- [ ] Announcer voice overs (Mortal-Kombat-style): "FIGHT!" at the start,
      "FINISH HIM!" at sudden death, "FLAWLESS VICTORY!" at the win reveal,
      occasional flavor lines on kills — pre-generated clips, music ducked
      during VO.

## 5 · Ending & presentation polish (mostly done — small touches only)

- [ ] Final kill lands on/near a beat (hold the last cut ≤ 0.5 s so the
      winner reveal lands on the beat)
- [x] Break-based ending: mux.py finds a lull in the song's energy curve near
      the winner screen and fades the music into it (`--timeline`)
- [x] Drop impact: the renderer detects musical drops (sharp energy surges in
      the timeline) and punches the camera — a jump + zoom-in that settles
      over 0.4 s. The winner screen stays crisp (CanvasLayer)
- [x] Ball glow rework: multi-layer emission halo (smaller, tighter falloff)
      + motion streaks at full speed (endgame "burns")
- [ ] Camera movement/zoom (sells the endgame speed further)
- [x] Watermark on the final video (mux.py, faint BOP below the arena)
- [ ] Music credits/metadata in the final video

## 6 · Postprocess & platform

- [ ] Loudness normalization in `postprocess/mux.py`
- [ ] Platform presets (per-platform 9:16 H.264/AAC bitrates)
- [ ] `requirements.txt` with pinned deps (analysis/simulation)

## 7 · Housekeeping

- [ ] Clean up stale outputs (`output/timelines`, `output/events/MONODY-*.json`)
- [x] Test the `scripts/save.py` flow end-to-end (verified against temp dirs)
- [x] `render/shaders/` was empty — removed
- [x] `.gitignore` audit — output/, songs/, caches covered

