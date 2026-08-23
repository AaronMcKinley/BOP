extends Node2D
# R2: a ball node whose color comes from its ball_id.
# R4 will replace this simple draw with the real glow/trail material.

var ball_id: int = 0:
	set(value):
		ball_id = value
		queue_redraw()

var lifelines: int = 3

var lifeline_anchors: Array = []:
	set(value):
		lifeline_anchors = value
		queue_redraw()

# Colors match the config/stats.json roster order (red, blue, green, yellow, purple, orange).
# Typed as Array[Color] so indexing yields a Color (needed for type inference below).
const COLORS: Array[Color] = [
	Color(1.0, 0.25, 0.25),  # 0 red
	Color(0.25, 0.5, 1.0),   # 1 blue
	Color(0.25, 1.0, 0.4),   # 2 green
	Color(1.0, 0.9, 0.2),    # 3 yellow
	Color(0.8, 0.3, 1.0),    # 4 purple
	Color(1.0, 0.55, 0.15),  # 5 orange
]

func _draw() -> void:
	var c := COLORS[clampi(ball_id, 0, COLORS.size() - 1)]
	# Lifeline strings: lines from the ball out to each rim anchor.
	for a in lifeline_anchors:
		var anchor := Vector2(a[0], a[1])
		draw_line(Vector2.ZERO, anchor - position, Color(c.r, c.g, c.b, 0.55), 3.0)
	# Soft outer halo
	draw_circle(Vector2.ZERO, 52.0, Color(c.r, c.g, c.b, 0.25))
	# Solid body
	draw_circle(Vector2.ZERO, 38.0, c)
	# Hot center highlight
	draw_circle(Vector2.ZERO, 24.0, c.lightened(0.6))
