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

const DROP_IMPACT_S := 0.4      # camera punch duration after a musical drop
const DROP_ZOOM := 0.10         # peak zoom-in on a drop (1.0 -> 1.10)
const DROP_SHAKE := 26.0        # peak camera jitter (px) on a drop

var _frames: Array = []
var _events_data: Dictionary = {}
var _balls := {}          # ball id -> Ball node
var _frame_index := 0
var _current_t := 0.0
var _arena: ArenaScript
var _winner_screen: WinnerScreen
var _collision_idx := 0
var _bounce_idx := 0
var _elim_idx := 0
var _bursts: Array = []   # [{node: CPUParticles2D, expires: float}]
var _cam: Camera2D
var _drops: Array = []    # drop events from the timeline that punch the camera
var _drop_idx := 0
var _impact_t := 0.0      # > 0 while a drop impact is shaking/zooming
var _impact_zoom := 0.0
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
	_cam.make_current()
	add_child(_cam)
	for e in _events_data.get("events", []):
		if e.get("type", "") == "drop":
			_drops.append(e)

func _process(delta: float) -> void:
	if _frame_index >= _frames.size():
		# Battle is over - play the winner reveal + league table, then finish.
		if _winner_screen == null:
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
	# Clear the battle field - just the winner + table from here on.
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
	# A musical drop (a sharp energy surge in the song) punches the camera:
	# an instant jump + zoom-in that settles back, so the drop feels physical.
	while _drop_idx < _drops.size() and float(_drops[_drop_idx]["t"]) <= _current_t:
		_drop_idx += 1
		_impact_t = DROP_IMPACT_S
		_impact_zoom = DROP_ZOOM
		_shake = DROP_SHAKE

func _step_camera(delta: float) -> void:
	# Punchy start, quick settle: zoom up to ~1.10 and a jitter that fades out.
	if _impact_t > 0.0:
		_impact_t = maxf(_impact_t - delta, 0.0)
		var k := _impact_t / DROP_IMPACT_S     # 1 -> 0
		var ease := k * k
		_cam.zoom = Vector2.ONE * (1.0 + _impact_zoom * ease)
		_cam.offset = Vector2(randf_range(-1.0, 1.0), randf_range(-1.0, 1.0)) * _shake * ease
	else:
		_cam.zoom = Vector2.ONE
		_cam.offset = Vector2.ZERO

func _events_path() -> String:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--events":
			return args[i + 1]
	return DEFAULT_EVENTS
