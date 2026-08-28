extends Node2D
# R2: the data-driven renderer. Steps one events.json frame per rendered frame,
# moving ball nodes and hiding eliminated balls. A real simulation's events.json
# will drive this exactly the same way the synthetic fixture does.
#
# Usage:  godot --path render --resolution 540x960 --write-movie out.avi
# Optional:  pass "--events path/to/events.json" after "--" to override the default.

const Ball := preload("res://scripts/ball.gd")
const BallScene := preload("res://scenes/ball.tscn")
const JsonLoader := preload("res://scripts/json_loader.gd")
const ArenaScript := preload("res://scripts/arena.gd")
const WinnerScreen := preload("res://scripts/winner_screen.gd")
const DEFAULT_EVENTS := "res://fixtures/sample_events.json"
const BURST_LIFE := 0.6         # seconds a particle burst lives
const WINNER_HOLD_FRAMES := 60  # freeze the winner on the game screen ~1s before the reveal

const DROP_IMPACT_S := 0.5      # shake duration when the main drop lands
const DROP_SHAKE := 40.0        # peak camera jitter (px) on the drop
const DROP_ZOOM := 0.30         # zoom to 1.30 on the drop - tighter on the action;
                                #   1.40 would clip the arena edges (6px margin)
const ZOOM_IN_S := 0.8          # how fast the camera pushes in (then holds)

var _frames: Array = []
var _events_data: Dictionary = {}
var _balls := {}          # ball id -> Ball node
var _frame_index := 0
var _winner_hold_frames := 0
var _current_t := 0.0
var _arena: ArenaScript
var _winner_screen: WinnerScreen
var _collision_idx := 0
var _bounce_idx := 0
var _elim_idx := 0
var _bursts: Array = []   # [{node: CPUParticles2D, expires: float}]
var _cam: Camera2D
var _drops: Array = []    # the main drop event (one per battle) from the timeline
var _drop_idx := 0
var _drop_time := -1.0    # battle time of the main drop (-1 = not fired yet)
var _zoom_in := 0.0       # 0..1 push-in progress toward the finale
var _impact_t := 0.0      # > 0 while the drop shake is active
var _shake := 0.0

func _ready() -> void:
	var events := JsonLoader.load_events(_events_path())
	if events.is_empty():
		get_tree().quit(1)
		return
	_frames = events["frames"]
	_events_data = events
	# Spawn one ball node per id, using the first frame to learn the roster.
	for frame: Dictionary in _frames:
		for ball_data: Dictionary in frame["balls"]:
			var id: int = int(ball_data["id"])
			if not _balls.has(id):
				var ball: Ball = BallScene.instantiate() as Ball
				ball.ball_id = id
				add_child(ball)
				_balls[id] = ball
	_arena = $Arena as ArenaScript

	# Light-cycle spokes rotate one full turn per beat when the arena knows the
	# song's BPM (it loads the timeline); otherwise balls keep their default spin.
	var bpm: float = _arena.bpm
	if bpm > 0.0:
		for ball: Ball in _balls.values():
			ball.spoke_speed = TAU * bpm / 60.0

	# Camera for musical-drop impacts: it jumps + zooms when the song drops.
	# The winner screen is a CanvasLayer, so it stays crisp - only the battle
	# field is affected.
	_cam = Camera2D.new()
	_cam.position = Vector2(540.0, 960.0)
	add_child(_cam)
	_cam.make_current()
	for e in _events_data.get("events", []):
		if e.get("type", "") == "drop":
			_drops.append(e)

func _process(delta: float) -> void:
	if _frame_index >= _frames.size():
		# Battle is over. Hold the frozen winner on the game screen for a beat
		# (so it's clear who won) while the camera settles, then play the
		# winner reveal + league table, then finish.
		if _winner_hold_frames < WINNER_HOLD_FRAMES:
			_winner_hold_frames += 1
			_step_camera(1.0 / 60.0)
		elif _winner_screen == null:
			_show_winner_screen()
		elif _winner_screen.is_done():
			get_tree().quit()
		return
	var frame: Dictionary = _frames[_frame_index]
	_frame_index += 1
	_current_t = frame["t"]
	for ball_data: Dictionary in frame["balls"]:
		var ball: Ball = _balls[int(ball_data["id"])] as Ball
		ball.visible = ball_data["alive"]
		ball.position = Vector2(ball_data["x"], ball_data["y"])
		ball.lifelines = ball_data["lifelines"]
		if ball_data.has("lifeline_anchors"):
			ball.lifeline_anchors = ball_data["lifeline_anchors"]
		ball.kills = int(ball_data.get("kills", 0))
	_trigger_events(frame)
	_purge_bursts()
	_check_drops()
	_step_camera(delta)

func _show_winner_screen() -> void:
	# Clear the battle field - just the winner + table from here on. Settle the
	# camera back to a clean, unzoomed frame.
	_cam.zoom = Vector2.ONE
	_cam.offset = Vector2.ZERO
	for ball in _balls.values():
		ball.visible = false
	var winner_data: Dictionary = _events_data.get("winner", {})
	if winner_data.is_empty():
		get_tree().quit()
		return
	var wid: int = int(winner_data["ball_id"])
	if not _balls.has(wid):
		get_tree().quit()
		return
	var ball: Ball = _balls[wid]
	var stats: Dictionary = _events_data.get("stats", {}).get(str(wid), {})
	var leaderboard: Array = _events_data.get("leaderboard", [])
	var leaderboard_before: Dictionary = _events_data.get("leaderboard_before", {})
	var screen := WinnerScreen.new()
	screen.setup(wid, ball.ball_color(), stats, leaderboard, leaderboard_before)
	add_child(screen)
	_winner_screen = screen

func _trigger_events(frame: Dictionary) -> void:
	# Fire particle bursts when battle events land on the current frame.
	var t: float = frame["t"]
	var colls: Array = _events_data.get("collisions", [])
	while _collision_idx < colls.size() and float(colls[_collision_idx]["t"]) <= t:
		var e: Dictionary = colls[_collision_idx]
		_collision_idx += 1
		var a: Ball = _balls[int(e["ball_a"])]
		var b: Ball = _balls[int(e["ball_b"])]
		var mid := (a.position + b.position) * 0.5
		var impact: float = float(e.get("impact", 0.5))
		# Clash sparks blend the two balls' colors (red + blue = purple).
		var mix := (a.ball_color() + b.ball_color()) * 0.5
		_spawn_burst(mid, mix, int(8 + 12 * impact), 120.0 + 140.0 * impact)
	var bounces: Array = _events_data.get("wall_bounces", [])
	while _bounce_idx < bounces.size() and float(bounces[_bounce_idx]["t"]) <= t:
		var e: Dictionary = bounces[_bounce_idx]
		_bounce_idx += 1
		var ball: Ball = _balls[int(e["ball_id"])]
		_spawn_burst(ball.position, ball.ball_color(), 6, 90.0)
	var elims: Array = _events_data.get("eliminations", [])
	while _elim_idx < elims.size() and float(elims[_elim_idx]["t"]) <= t:
		var e: Dictionary = elims[_elim_idx]
		_elim_idx += 1
		var ball: Ball = _balls[int(e["ball_id"])]
		_spawn_burst(ball.position, ball.ball_color(), 40, 260.0)
		# The arena rim + inner circles flash in the killer's color.
		var killer_id := int(e.get("killer", -1))
		if _balls.has(killer_id):
			_arena.trigger_flash((_balls[killer_id] as Ball).ball_color())

func _spawn_burst(pos: Vector2, color: Color, count: int, speed: float) -> void:
	var p := CPUParticles2D.new()
	p.position = pos
	p.amount = count
	p.lifetime = BURST_LIFE
	p.one_shot = true
	p.explosiveness = 1.0
	p.direction = Vector2.RIGHT
	p.spread = 180.0
	p.initial_velocity_min = speed * 0.25
	p.initial_velocity_max = speed
	p.gravity = Vector2.ZERO
	p.scale_amount_min = 2.0
	p.scale_amount_max = 5.0
	p.color = color
	p.emitting = true
	add_child(p)
	_bursts.append({"node": p, "expires": _current_t + BURST_LIFE + 0.05})

func _purge_bursts() -> void:
	for i in range(_bursts.size() - 1, -1, -1):
		if _current_t >= float(_bursts[i]["expires"]):
			(_bursts[i]["node"] as Node).queue_free()
			_bursts.remove_at(i)

func _check_drops() -> void:
	# The single main drop (the strongest energy surge in the song) slams the
	# camera: a dramatic shake plus a fast zoom-in that holds, so we end up
	# closer to the action for the finale.
	while _drop_idx < _drops.size() and float(_drops[_drop_idx]["t"]) <= _current_t:
		_drop_time = float(_drops[_drop_idx]["t"])
		_drop_idx += 1
		_impact_t = DROP_IMPACT_S
		_shake = DROP_SHAKE
		_zoom_in = 0.0

func _step_camera(delta: float) -> void:
	# The camera is created in _ready; when events failed to load the scene
	# quits before that, so guard against a null camera.
	if _cam == null:
		return
	if _drop_time >= 0.0:
		# Fast ease-out push-in (1.0 -> ~1.20) that settles and holds; the shake
		# is strongest at the drop and decays.
		_zoom_in = minf(_zoom_in + delta / ZOOM_IN_S, 1.0)
		var ease := 1.0 - pow(1.0 - _zoom_in, 3)
		if _impact_t > 0.0:
			_impact_t = maxf(_impact_t - delta, 0.0)
			var k := _impact_t / DROP_IMPACT_S
			_cam.offset = Vector2(randf_range(-1.0, 1.0), randf_range(-1.0, 1.0)) * _shake * k
		else:
			_cam.offset = Vector2.ZERO
		_cam.zoom = Vector2.ONE * (1.0 + DROP_ZOOM * ease)
	else:
		_cam.zoom = Vector2.ONE
		_cam.offset = Vector2.ZERO

func _events_path() -> String:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--events":
			return args[i + 1]
	return DEFAULT_EVENTS
