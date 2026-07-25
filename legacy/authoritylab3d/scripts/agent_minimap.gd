class_name AgentMinimap
extends Control

# A deliberately schematic spatial aid: it is an observer instrument, not an
# omniscient game mechanic. It shows where the embodied agents actually are.
var agents: Dictionary = {}
var selected_id := "H"

func _ready() -> void:
	custom_minimum_size = Vector2(250, 200)
	mouse_filter = Control.MOUSE_FILTER_IGNORE

func _process(_delta: float) -> void:
	queue_redraw()

func _draw() -> void:
	var area := Rect2(Vector2.ZERO, size)
	draw_rect(area, Color("08131bdd"), true)
	draw_rect(area, Color("b8d8e9aa"), false, 2.0)
	draw_string(ThemeDB.fallback_font, Vector2(12, 22), "DISTRICT / LIVE POSITIONS", HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color("d8edf8"))
	var map_area := Rect2(12, 34, max(1.0, size.x - 24.0), max(1.0, size.y - 48.0))
	draw_rect(map_area, Color("243d49"), true)
	# Simplified flood district: roads, central committee plaza, and four sites.
	draw_rect(Rect2(map_area.position + Vector2(0, map_area.size.y * 0.42), Vector2(map_area.size.x, map_area.size.y * 0.09)), Color("657179"), true)
	draw_rect(Rect2(map_area.position + Vector2(map_area.size.x * 0.43, 0), Vector2(map_area.size.x * 0.08, map_area.size.y)), Color("657179"), true)
	draw_circle(map_position(Vector3.ZERO, map_area), 11.0, Color("ecf4e9"))
	for id in agents:
		var avatar = agents[id]
		if not is_instance_valid(avatar):
			continue
		var marker_color: Color = avatar.accent
		var marker_position := map_position(avatar.global_position, map_area)
		draw_circle(marker_position, 6.5 if id == selected_id else 4.5, marker_color)
		if id == selected_id:
			draw_arc(marker_position, 9.5, 0.0, TAU, 20, Color.WHITE, 1.5)
		draw_string(ThemeDB.fallback_font, marker_position + Vector2(8, -7), id, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color.WHITE)

func map_position(world_position: Vector3, map_area: Rect2) -> Vector2:
	# District dimensions match CommitteeRoom.create_flood_district().
	var nx: float = clampf((world_position.x + 90.0) / 180.0, 0.0, 1.0)
	var nz: float = clampf((world_position.z + 70.0) / 140.0, 0.0, 1.0)
	return map_area.position + Vector2(nx * map_area.size.x, nz * map_area.size.y)
