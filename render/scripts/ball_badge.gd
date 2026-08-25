extends Control
# A small ball disc badge (dark body + neon rim + inner ring) used in UI rows.
# Mirrors the in-arena ball look so the table rows read as the balls themselves.

var ball_color := Color.WHITE:
	set(value):
		ball_color = value
		queue_redraw()

func _draw() -> void:
	var c := ball_color
	var r := minf(size.x, size.y) * 0.5
	var center := size * 0.5
	draw_circle(center, r, Color(0.03, 0.05, 0.08))
	draw_arc(center, r, 0.0, TAU, 24, c, 2.5, true)
	draw_arc(center, r * 0.62, 0.0, TAU, 24, Color(c.r, c.g, c.b, 0.5), 1.0, true)
	draw_circle(center, r * 0.15, c)
