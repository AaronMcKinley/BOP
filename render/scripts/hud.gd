extends CanvasLayer
# HUD: a scoreboard strip at the bottom of the screen. One horizontal row:
# for each ball, a color swatch plus the number of strings it has cut
# (its live aggression score).

var _rows := {}   # ball id -> Label

func setup(balls: Array) -> void:
	# CanvasLayer is not a Control, so it needs a full-rect Control child to
	# anchor the scoreboard against.
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(root)

	var panel := PanelContainer.new()
	panel.name = "Scoreboard"
	panel.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	panel.offset_top = -64.0
	panel.offset_bottom = -10.0
	# Subtle dark background so the strip reads against the arena.
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0, 0, 0, 0.4)
	bg.corner_radius_top_left = 10
	bg.corner_radius_top_right = 10
	panel.add_theme_stylebox_override("panel", bg)
	root.add_child(panel)

	var bar := HBoxContainer.new()
	bar.alignment = BoxContainer.ALIGNMENT_CENTER
	bar.add_theme_constant_override("separation", 28)
	panel.add_child(bar)

	var header := Label.new()
	header.text = "KILLS"
	header.add_theme_font_size_override("font_size", 18)
	header.modulate = Color(1, 1, 1, 0.6)
	bar.add_child(header)

	for ball in balls:
		var id: int = ball.ball_id
		var group := HBoxContainer.new()
		group.add_theme_constant_override("separation", 8)
		bar.add_child(group)

		var swatch := ColorRect.new()
		swatch.custom_minimum_size = Vector2(22, 22)
		swatch.color = ball.ball_color()
		group.add_child(swatch)

		var cuts := Label.new()
		cuts.text = "0"
		cuts.add_theme_font_size_override("font_size", 26)
		cuts.add_theme_color_override("font_color", ball.ball_color())
		group.add_child(cuts)

		_rows[id] = cuts

func refresh(balls: Array) -> void:
	for ball in balls:
		var id: int = ball.ball_id
		var label: Label = _rows.get(id)
		if label == null:
			continue
		label.text = str(ball.kills)

