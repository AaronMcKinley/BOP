extends Node2D
# R5: a ball rendered as a Tron-style disc - dark body, neon rim, rotating
# light-cycle spoke, layered glow. The lifeline strings radiate to the rim.

var ball_id: int = 0:
	set(value):
		ball_id = value
		queue_redraw()

var lifelines: int = 3

var kills: int = 0

func ball_color() -> Color:
	return COLORS[clampi(ball_id, 0, COLORS.size() - 1)]

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

const RADIUS := 38.0
const BODY_DARK := Color(0.03, 0.05, 0.08)

var spoke_speed := 2.5        # rad/s; render.gd sets it to 1 rev per beat (TAU * BPM / 60)

var _spoke_angle := 0.0

func _process(delta: float) -> void:
	# The light-cycle spoke keeps rotating so the discs feel alive. When the
	# renderer knows the song's BPM it completes one full turn per beat.
	_spoke_angle = fmod(_spoke_angle + delta * spoke_speed, TAU)
	queue_redraw()

func _draw() -> void:
	var c := ball_color()
	# Lifeline strings: lines from the ball out to each rim anchor.
	for a in lifeline_anchors:
		var anchor := Vector2(a[0], a[1])
		draw_line(Vector2.ZERO, anchor - position, Color(c.r, c.g, c.b, 0.55), 3.0)
		# Anchor dot on the rim, so the attachment point reads clearly.
		draw_circle(anchor - position, 3.5, Color(c.r, c.g, c.b, 0.9))

	# Layered glow so the disc reads against the dark arena.
	draw_circle(Vector2.ZERO, RADIUS * 2.2, Color(c.r, c.g, c.b, 0.08))
	draw_circle(Vector2.ZERO, RADIUS * 1.55, Color(c.r, c.g, c.b, 0.16))

	# Dark Tron body.
	draw_circle(Vector2.ZERO, RADIUS, BODY_DARK)

	# Bright neon rim (outer) + softer inner glow ring.
	draw_arc(Vector2.ZERO, RADIUS, 0.0, TAU, 48, c, 3.0, true)
	draw_arc(Vector2.ZERO, RADIUS * 0.72, 0.0, TAU, 48, Color(c.r, c.g, c.b, 0.45), 1.5, true)

	# Rotating light-cycle spoke.
	var spoke := Vector2(RADIUS * 0.95, 0.0).rotated(_spoke_angle)
	draw_line(Vector2.ZERO, spoke, Color(c.r, c.g, c.b, 0.85), 2.5)

	# Hot center core.
	draw_circle(Vector2.ZERO, 4.0, c.lightened(0.3))
