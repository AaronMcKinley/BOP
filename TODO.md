# TODO

The pipeline is solid end-to-end (create → save → leaderboard, beat-synced
visuals, energy-driven pacing, the main-drop camera impact, watermark). The
outro is final: winner reveal → league table → music fade to the very end.
Remaining work by priority.

## 1 · Launch (before publishing much)

- [x] Music licensing: TheFatRat free-use — YouTube OK incl. monetization with a
      proper description credit (full title + artist + link to the original);
      never copyright-claim. Recorded in `config/credits.json`
- [ ] Fill the real `music_link` in `config/credits.json` (for a remix the
      original may be on The Arcadium channel, not TheFatRat's)
- [ ] First batch of 3–5 videos — captions auto-generate next to each saved
      battle (`battle_NNN_caption.txt`) with the credit baked in
- [ ] Optional: music credits/metadata in the final video

## 2 · Next features (build order)

- [ ] Sound effects: procedural bounce tick / collision thump (scaled by
      impact) / elimination whoosh / win sting — played at event times, under
      the song. (Sound clips the user is sourcing drop into a folder)
- [ ] Announcer voice audio (Mortal-Kombat-style): "FIGHT!" at the start,
      "FINISH HIM!" at sudden death, "FLAWLESS VICTORY!" at the reveal,
      occasional flavor lines on kills
- [ ] Sudden death must READ as a moment — the first live watch was unclear:
      the rules changed and nothing said so. Full "SUDDEN DEATH" banner +
      rim flash + the "FINISH HIM!" voice line landing together, so it's
      obvious the battle just flipped (the renderer already reacts to `drop`
      events the same way)
- [ ] Acceleration kicks: balls gain an acceleration boost (×x) on musical
      beats and on collisions, so the action punches with the song. Exact
      factor/mechanism TBD — fine as is for now
- [ ] Optional polish: final kill lands on/near a beat so the winner reveal
      lands on the beat; camera keeps creeping in after the drop

## 3 · Events & pacing (later — the full system)

- [ ] Replace the ≥45 s re-roll with structured pacing for short seeds
      (immunity / speed boost / walls already exist to call; design the rest)
- [ ] Beat-aligned rendering: collision flashes on bass hits, energy-scaled
      arena pulse
- [ ] Seed scoring vs the timeline (director: keep the battle whose arc fits
      the song)

## 4 · Postprocess & platform

- [ ] Loudness normalization in `postprocess/mux.py`
- [ ] Platform presets (per-platform 9:16 H.264/AAC bitrates)
- [ ] `requirements.txt` with pinned deps

## 5 · Housekeeping

- [ ] Clean stale outputs (`output/timelines`, `output/events/MONODY-*.json`)
- [ ] Add tests for `mux.py` (watermark + fade timing)

## Decisions recorded (done / explicitly not doing)

- Outro is final — no more outro work
- Speed settings locked: `SPEED_TAU 50`, `MAX_SPEED_MULT 5.5`, growth `0.6/+10`
- 6 balls rejected (kills the 60–90 s battles); battle structure accepted
- No grace period, no damage throttling, no duration caps
- Outer-circle cut rule rolled back — the centre is where the action is
- Lull-based "break ending" rolled back — fixed fade from the winner screen
- Motion streaks on balls dumped — the layered emission halo is the look

