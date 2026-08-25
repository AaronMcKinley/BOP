extends CanvasLayer
# End-of-video sequence: winner reveal on a clean screen, then an animated
# league table with ball badges, points/wins/kills, and green/red movement
# arrows. The music fades out over the end.

const BallBadge := preload("res://scripts/ball_badge.gd")

const BALL_NAMES := ["RED", "BLUE", "GREEN", "YELLOW", "PURPLE", "ORANGE"]
const BALL_COLORS: Array[Color] = [
	Color(1.0, 0.25, 0.25),  # 0 red
	Color(0.25, 0.5, 1.0),   # 1 blue
	Color(0.25, 1.0, 0.4),   # 2 green
	Color(1.0, 0.9, 0.2),    # 3 yellow
	Color(0.8, 0.3, 1.0),    # 4 purple
	Color(1.0, 0.55, 0.15),  # 5 orange
]

const REVEAL_S := 2.5         # winner phase duration
const LOAD_S := 0.8           # whole table fades in together, then a short beat
const MOVE_S := 1.0           # then all rows slide together to their new ranks
const TABLE_S := 6.0          # league table phase duration
const READ_S := TABLE_S - LOAD_S - MOVE_S   # static reading time at the end
const TOTAL_S := REVEAL_S + TABLE_S

const ROW_H := 64.0           # table row height (px, design space)
const TABLE_TOP := 770.0      # y of the first table row

var _root: Control
var _reveal: Control
var _table: Control
var _rows: Array = []         # [{node: Control, from_y: float, to_y: float}]
var _t := 0.0

func setup(ball_id: int, color: Color, stats: Dictionary,
           leaderboard: Array, leaderboard_before: Dictionary) -> void:
	_root = Control.new()
	_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(_root)

	var overlay := ColorRect.new()
	overlay.color = Color(0, 0, 0, 0.78)
	overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(overlay)

	_reveal = _build_reveal(ball_id, color, stats)   # builder adds it under _root

	_table = _build_table(ball_id, leaderboard, leaderboard_before)   # builder adds it under _root
	_table.visible = false

func _process(delta: float) -> void:
	_t += delta
	var in_reveal := _t < REVEAL_S
	_reveal.visible = in_reveal
	_table.visible = not in_reveal
	# Quick fade-in on the reveal so it doesn't pop in.
	_reveal.modulate.a = minf(1.0, _t / 0.35)
	if not in_reveal:
		_animate_table(_t - REVEAL_S)

func is_done() -> bool:
	return _t >= TOTAL_S

func _animate_table(table_t: float) -> void:
	# Two beats so the movement reads clearly:
	#   1. LOAD: the whole table fades in together at the OLD standings.
	#   2. MOVE: all rows slide together to their NEW positions; the arrows
	#      (already on screen) point where each row goes.
	for r in _rows:
		var node: Control = r["node"]
		var fade_t := clampf(table_t / 0.4, 0.0, 1.0)
		fade_t = 1.0 - pow(1.0 - fade_t, 3)   # ease-out cubic
		node.modulate.a = fade_t
		var slide_t := clampf((table_t - LOAD_S) / MOVE_S, 0.0, 1.0)
		slide_t = 1.0 - pow(1.0 - slide_t, 3)
		node.position.y = lerpf(r["from_y"], r["to_y"], slide_t)


func _build_reveal(ball_id: int, color: Color, stats: Dictionary) -> Control:
	var box := VBoxContainer.new()
	box.set_anchors_preset(Control.PRESET_FULL_RECT)
	box.alignment = BoxContainer.ALIGNMENT_CENTER
	box.add_theme_constant_override("separation", 8)
	_root.add_child(box)

	var title := Label.new()
	title.text = "WINNER"
	title.add_theme_font_size_override("font_size", 44)
	title.add_theme_color_override("font_color", Color(0.2, 0.9, 1.0))
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(title)

	var badge := BallBadge.new()
	badge.ball_color = color
	badge.custom_minimum_size = Vector2(0, 120)
	box.add_child(badge)

	var name_label := Label.new()
	name_label.text = BALL_NAMES[clampi(ball_id, 0, BALL_NAMES.size() - 1)]
	name_label.add_theme_font_size_override("font_size", 72)
	name_label.add_theme_color_override("font_color", color)
	name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(name_label)

	var stats_text := ""
	stats_text += "KILLS  %d\n" % int(stats.get("kills", 0))
	stats_text += "BOUNCES  %d\n" % int(stats.get("bounces", 0))
	stats_text += "STRINGS CUT  %d\n" % int(stats.get("cuts_dealt", 0))
	stats_text += "COLLISIONS  %d" % int(stats.get("collisions", 0))
	var stats_label := Label.new()
	stats_label.text = stats_text
	stats_label.add_theme_font_size_override("font_size", 28)
	stats_label.add_theme_color_override("font_color", Color(0.9, 0.95, 1.0, 0.9))
	stats_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	box.add_child(stats_label)
	return box

func _build_table(ball_id: int, leaderboard: Array, before: Dictionary) -> Control:
	var panel := Control.new()
	panel.set_anchors_preset(Control.PRESET_FULL_RECT)
	_root.add_child(panel)

	var title := Label.new()
	title.text = "LEAGUE TABLE"
	title.add_theme_font_size_override("font_size", 40)
	title.add_theme_color_override("font_color", Color(0.2, 0.9, 1.0))
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.anchor_left = 0.0
	title.anchor_right = 1.0
	title.offset_top = 620.0
	title.offset_bottom = 690.0
	panel.add_child(title)

	for i: int in range(leaderboard.size()):
		var row: Dictionary = leaderboard[i]
		var id: int = row["id"]
		var after_pos: int = row["position"]
		# leaderboard_before keys are strings after the JSON round-trip.
		var before_pos: int = int(before.get(str(id), after_pos))
		var row_node := _build_table_row(ball_id, row, before_pos, after_pos)
		var from_y := TABLE_TOP + (before_pos - 1) * ROW_H
		var to_y := TABLE_TOP + (after_pos - 1) * ROW_H
		row_node.position = Vector2(0, from_y)
		row_node.size = Vector2(1080, ROW_H)
		row_node.modulate.a = 0.0
		panel.add_child(row_node)
		_rows.append({"node": row_node, "from_y": from_y, "to_y": to_y})
	return panel

func _build_table_row(winner_id: int, row: Dictionary, before_pos: int, after_pos: int) -> Control:
	var r := Control.new()
	var id: int = row["id"]
	var c := BALL_COLORS[clampi(id, 0, BALL_COLORS.size() - 1)]
	var is_winner := id == winner_id

	# Winner highlight bar behind the row - only as wide as the arena circle.
	var highlight := ColorRect.new()
	highlight.color = Color(c.r, c.g, c.b, 0.12 if is_winner else 0.0)
	highlight.position = Vector2(160, 0)
	highlight.size = Vector2(760, ROW_H)
	r.add_child(highlight)

	# Ball badge (the ball itself).
	var badge := BallBadge.new()
	badge.ball_color = c
	badge.position = Vector2(330, 10)
	badge.size = Vector2(44, 44)
	r.add_child(badge)

	# Name in the ball's colour.
	var name := Label.new()
	name.text = str(row["name"]).to_upper()
	name.add_theme_color_override("font_color", c)
	name.add_theme_font_size_override("font_size", 32 if is_winner else 28)
	name.position = Vector2(392, 14)
	r.add_child(name)

	# Points with this battle's gain.
	var pts := Label.new()
	pts.text = "%d  +%d" % [row["points"], row["delta"]]
	pts.add_theme_color_override("font_color", Color(1, 1, 1, 0.95))
	pts.add_theme_font_size_override("font_size", 28)
	pts.position = Vector2(580, 14)
	r.add_child(pts)

	# Wins and kills.
	var wk := Label.new()
	wk.text = "W %d   K %d" % [row["wins"], row["kills"]]
	wk.add_theme_color_override("font_color", Color(0.8, 0.85, 1.0, 0.8))
	wk.add_theme_font_size_override("font_size", 24)
	wk.position = Vector2(720, 18)
	r.add_child(wk)

	# Movement arrow: green up, red down.
	var arrow := Label.new()
	arrow.add_theme_font_size_override("font_size", 26)
	arrow.position = Vector2(860, 14)
	if after_pos < before_pos:
		arrow.text = "\u25B2"
		arrow.add_theme_color_override("font_color", Color(0.25, 1.0, 0.4))
	elif after_pos > before_pos:
		arrow.text = "\u25BC"
		arrow.add_theme_color_override("font_color", Color(1.0, 0.3, 0.3))
	r.add_child(arrow)

	return r

