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
const DEFAULT_EVENTS := "res://fixtures/sample_events.json"

var _frames: Array = []
var _balls := {}          # ball id -> Ball node
var _frame_index := 0

func _ready() -> void:
	var events := JsonLoader.load_events(_events_path())
	if events.is_empty():
		get_tree().quit(1)
		return
	_frames = events["frames"]
	# Spawn one ball node per id, using the first frame to learn the roster.
	for frame: Dictionary in _frames:
		for ball_data: Dictionary in frame["balls"]:
			var id: int = int(ball_data["id"])
			if not _balls.has(id):
				var ball: Ball = BallScene.instantiate() as Ball
				ball.ball_id = id
				add_child(ball)
				_balls[id] = ball

func _process(_delta: float) -> void:
	if _frame_index >= _frames.size():
		get_tree().quit()
		return
	var frame: Dictionary = _frames[_frame_index]
	_frame_index += 1
	for ball_data: Dictionary in frame["balls"]:
		var ball: Ball = _balls[int(ball_data["id"])] as Ball
		ball.visible = ball_data["alive"]
		ball.position = Vector2(ball_data["x"], ball_data["y"])
		ball.lifelines = ball_data["lifelines"]

func _events_path() -> String:
	var args := OS.get_cmdline_user_args()
	for i in range(args.size() - 1):
		if args[i] == "--events":
			return args[i + 1]
	return DEFAULT_EVENTS

func _draw() -> void:
	# Faint arena rim so the bounce boundary is visible while testing.
	# R3 replaces this with the real glowing arena.
	draw_arc(Vector2(540.0, 960.0), 380.0, 0.0, TAU, 128, Color(1.0, 1.0, 1.0, 0.15), 4.0)
