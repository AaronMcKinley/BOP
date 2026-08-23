extends Node2D
# R3: the decorative arena ring that pulses with the music.
#
# It reads timeline.json directly (beats, bpm, energy_curve) and draws two
# purely musical effects - the battle happens inside and this ring only reacts
# to the track:
#   * a beat bump: the ring swells on every beat, decaying smoothly after
#   * a rotating surface wave: the ring edge undulates around its circumference,
#     rotating at the beat rate (the smooth, organic "visualizer" feel)
#
# Usage: pass "--timeline path/to/timeline.json" after "--" to override the
# default fixture at res://fixtures/timeline.json

const JsonLoader := preload("res://scripts/json_loader.gd")
const DEFAULT_TIMELINE := "res://fixtures/timeline.json"

const CENTER := Vector2(540.0, 960.0)   # 1080x1920 design space
const BASE_RADIUS := 380.0
const BUMP_AMPLITUDE := 18.0    # px the ring swells on a strong beat
const WAVE_AMPLITUDE := 14.0    # px of circumferential wave at full bump
const BUMP_DECAY := 3.5         # bump decays this fast per second
const WAVE_SPIN := 0.5          # wave rotations per beat (0.5 = one per 2 beats)
const SEGMENTS := 128

var beats: Array = []
var energy_curve: Array = []    # [[t, e], ...] from timeline.json
var bpm := 0.0

var _t := 0.0
var _beat_index := 0
var _bump := 0.0                # 0..1, re-triggered on each beat
var _phase := 0.0               # rotating wave phase (radians)

func _ready() -> void:
	var timeline := JsonLoader.load_events(_timeline_path())
	if timeline.is_empty():
		push_error("arena: no timeline loaded; ring will not pulse")
		return
	beats = timeline["beats"]
	energy_curve = timeline["energy_curve"]
	bpm = float(timeline["bpm"])

func _process(delta: float) -> void:
	_t += delta
	# Trigger a bump on each new beat, scaled by the local energy.
	while _beat_index < beats.size() and _t >= float(beats[_beat_index]):
		_bump = 0.6 + 0.4 * _energy_at(float(beats[_beat_index]))
		_beat_index += 1
	# Decay the bump smoothly between beats.
	_bump = maxf(_bump - delta * BUMP_DECAY, 0.0)
	# Advance the surface wave at the beat rate so it feels locked to the music.
	if bpm > 0.0:
		_phase = fmod(_phase + delta * TAU * (bpm / 60.0) * WAVE_SPIN, TAU)
	queue_redraw()

func _draw() -> void:
	var wave_amp := WAVE_AMPLITUDE * (0.2 + 0.8 * _bump)
	var ring_r := BASE_RADIUS + BUMP_AMPLITUDE * _bump
	var points := PackedVector2Array()
	for i in SEGMENTS:
		var a := TAU * float(i) / SEGMENTS
		var r := ring_r + wave_amp * sin(a * 2.0 + _phase)
		points.append(CENTER + Vector2(r, 0.0).rotated(a))
	points.append(points[0])  # close the loop so the stroke has no seam
	# Layered neon ring: soft outer glow, mid pass, bright core.
	draw_polyline(points, Color(1.0, 1.0, 1.0, 0.08), 20.0, true)
	draw_polyline(points, Color(1.0, 1.0, 1.0, 0.25), 8.0, true)
	draw_polyline(points, Color(1.0, 0.95, 0.85, 0.9), 2.5, true)

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
	return DEFAULT_TIMELINE
