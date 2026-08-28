extends Node2D
# R4: the decorative arena, Tron-style.
#
# It reads timeline.json directly (beats, bpm, energy_curve) and draws:
#   * a neon cyan rim (layered glow) that swells on every beat
#   * concentric inner circles that brighten with the beat
#   * a shockwave ripple expanding outward from the rim on each beat
#   * a faint full-screen grid background
#
# The battle balls move inside; this only reacts to the music.
#
# Usage: pass "--timeline path/to/timeline.json" after "--" (create.sh always
# does). Required - if it is missing the renderer refuses to run: the arena
# must pulse on the actual song's beats, never a fixture's.

const JsonLoader := preload("res://scripts/json_loader.gd")

const CENTER := Vector2(540.0, 960.0)   # 1080x1920 design space
const BASE_RADIUS := 380.0
const BUMP_AMPLITUDE := 16.0    # px the rim swells on a strong beat
const BUMP_DECAY := 3.5         # bump decays this fast per second
const RIPPLE_SPEED := 240.0     # px/s the shockwave expands outward
const RIPPLE_LIFE := 2.0        # seconds a ripple lives before fading
const FLASH_DECAY := 2.5        # per second, a kill-flash fades back to cyan
const GRID_SPACING := 120.0     # px between grid lines
const SEGMENTS := 128

const CYAN := Color(0.2, 0.9, 1.0)

var beats: Array = []
var energy_curve: Array = []    # [[t, e], ...] from timeline.json
var bpm := 0.0

var _t := 0.0
var _beat_index := 0
var _bump := 0.0                # 0..1, re-triggered on each beat
var _ripples: Array = []        # [{age: float}, ...]
var _flash := 0.0               # 0..1 kill-flash intensity
var _flash_color := Color(1, 1, 1)

func _ready() -> void:
	var timeline := JsonLoader.load_events(_timeline_path())
	if timeline.is_empty():
		push_error("arena: no timeline given (pass --timeline after \"--\"). "
			+ "The arena pulses on the song's beats - refusing to fall back to "
			+ "a fixture.")
		get_tree().quit(1)
		return
	beats = timeline["beats"]
	energy_curve = timeline["energy_curve"]
	bpm = float(timeline["bpm"])

func _process(delta: float) -> void:
	_t += delta
	# Trigger a bump + ripple on each new beat, scaled by the local energy.
	while _beat_index < beats.size() and _t >= float(beats[_beat_index]):
		_bump = 0.6 + 0.4 * _energy_at(float(beats[_beat_index]))
		_ripples.append({"age": 0.0})
		_beat_index += 1
	_bump = maxf(_bump - delta * BUMP_DECAY, 0.0)
	_flash = maxf(_flash - delta * FLASH_DECAY, 0.0)
	for r in _ripples:
		r["age"] += delta
	_ripples = _ripples.filter(func(r: Dictionary) -> bool: return r["age"] < RIPPLE_LIFE)
	queue_redraw()

func trigger_flash(color: Color) -> void:
	# A ball scored a kill - the arena flashes in that ball's color.
	_flash_color = color
	_flash = 1.0

func _draw() -> void:
	_draw_grid()
	var bump_r := BASE_RADIUS + BUMP_AMPLITUDE * _bump
	var ring_col := CYAN.lerp(_flash_color, _flash)
	_draw_ring(bump_r, ring_col)
	_draw_inner_circles(bump_r, ring_col)
	_draw_ripples()

func _draw_grid() -> void:
	# Faint Tron-floor grid across the whole frame.
	var col := Color(CYAN.r, CYAN.g, CYAN.b, 0.04)
	var x := 0.0
	while x <= 1080.0:
		draw_line(Vector2(x, 0.0), Vector2(x, 1920.0), col, 1.0)
		x += GRID_SPACING
	var y := 0.0
	while y <= 1920.0:
		draw_line(Vector2(0.0, y), Vector2(1080.0, y), col, 1.0)
		y += GRID_SPACING

func _draw_ring(r: float, col: Color) -> void:
	# Layered neon cyan rim: soft outer glow down to a bright core.
	var pts := _circle_points(r)
	pts.append(pts[0])
	draw_polyline(pts, Color(col.r, col.g, col.b, 0.05), 22.0, true)
	draw_polyline(pts, Color(col.r, col.g, col.b, 0.12), 10.0, true)
	draw_polyline(pts, Color(col.r, col.g, col.b, 0.35), 3.5, true)
	draw_polyline(pts, col, 1.5, true)

func _draw_inner_circles(r: float, col: Color) -> void:
	# Concentric rings inside the arena; they brighten with the beat.
	var alpha := 0.05 + 0.15 * _bump
	for frac in [0.9, 0.78]:
		var pts := _circle_points(r * frac)
		draw_polyline(pts, Color(col.r, col.g, col.b, alpha), 1.5, true)

func _draw_ripples() -> void:
	# Shockwaves expanding outward from the rim, fading as they go.
	for r in _ripples:
		var age: float = r["age"]
		var radius := BASE_RADIUS + RIPPLE_SPEED * age
		var alpha := maxf(0.0, 0.35 * (1.0 - age / RIPPLE_LIFE))
		var pts := _circle_points(radius)
		draw_polyline(pts, Color(CYAN.r, CYAN.g, CYAN.b, alpha), 2.0, true)

func _circle_points(r: float) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in SEGMENTS:
		var a := TAU * float(i) / SEGMENTS
		pts.append(CENTER + Vector2(r, 0.0).rotated(a))
	return pts

func _energy_at(t: float) -> float:
	# Linear interpolation on the energy curve (assumed sorted by time).
	if energy_curve.is_empty():
		return 0.0
	if t <= float(energy_curve[0][0]):
		return float(energy_curve[0][1])
	for i in range(energy_curve.size() - 1):
		var t0 := float(energy_curve[i][0])
		var t1 := float(energy_curve[i + 1][0])
		if t0 <= t and t <= t1:
			var e0 := float(energy_curve[i][1])
			var e1 := float(energy_curve[i + 1][1])
			if t1 - t0 == 0.0:
				return e0
			return e0 + (e1 - e0) * (t - t0) / (t1 - t0)
	return float(energy_curve[-1][1])

func _timeline_path() -> String:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--timeline":
			return args[i + 1]
	return ""

