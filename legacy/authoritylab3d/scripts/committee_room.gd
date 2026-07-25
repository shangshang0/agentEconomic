extends Node3D

const ExperimentStateScript = preload("res://scripts/experiment_state.gd")
const AgentAvatarScript = preload("res://scripts/agent_avatar.gd")
const AgentMinimapScript = preload("res://scripts/agent_minimap.gd")
const PerceptionCaptureScript = preload("res://scripts/perception_capture.gd")

var experiment: ExperimentState
var agents := {}
var activity_labels := {}
var log_view: RichTextLabel
var briefing_label: Label
var status_label: Label
var advance_button: Button
var start_button: Button
var observer_label: Label
var minimap
var perception_capture
var agent_state_label: RichTextLabel
var event_log := []
var room_material: StandardMaterial3D
var observed_agent_id := "H"
var perception_run_id := "local_preview"
var station_targets := {
	"H": Vector3(-8.0, 0.0, -4.5),
	"G": Vector3(8.0, 0.0, -4.5),
	"T": Vector3(-8.0, 0.0, 4.5),
	"C": Vector3(8.0, 0.0, 4.5)
}

func _ready() -> void:
	experiment = ExperimentStateScript.new()
	create_environment()
	create_agents()
	create_perception_capture()
	create_ui()
	refresh_ui([])

func create_environment() -> void:
	create_world_lighting()
	create_flood_district()
	# The meeting hall is embedded inside the district. It is where public
	# authority is made visible, rather than an abstract menu outside the world.
	var floor := MeshInstance3D.new()
	floor.mesh = BoxMesh.new()
	floor.mesh.size = Vector3(24, 0.2, 16)
	floor.position = Vector3(0, -0.1, 0)
	floor.material_override = cc0_material("concrete_floor_worn_001", 5.0)
	add_child(floor)

	# The council is an open emergency plaza, not a closed meeting-room box.
	# Four support columns and a canvas roof give spatial focus while retaining
	# sight lines to the hospital, substation, depot and shelter.
	for column_position in [Vector3(-10.5, 2.2, -6.5), Vector3(10.5, 2.2, -6.5), Vector3(-10.5, 2.2, 6.5), Vector3(10.5, 2.2, 6.5)]:
		add_box(Vector3(0.55, 4.4, 0.55), column_position, Color("6c7070"))
	var canopy := add_box(Vector3(23.0, 0.18, 15.0), Vector3(0, 4.45, 0), Color("3d4b52"))
	canopy.material_override = material(Color("3d4b52aa"), 0.0, 0.85)

	spawn_asset("WoodenTable_01", Vector3(0, 0.12, 0), Vector3(2.2, 2.2, 2.2))
	for chair_position in [Vector3(-3.0, 0.0, -1.4), Vector3(3.0, 0.0, -1.4), Vector3(-3.0, 0.0, 1.4), Vector3(3.0, 0.0, 1.4)]:
		spawn_asset("SchoolChair_01", chair_position, Vector3(1.2, 1.2, 1.2))

	var station_data := [
		["HOSPITAL", Vector3(-8, 1.2, -4.5), Color("d85d5d")],
		["GRID", Vector3(8, 1.2, -4.5), Color("e0b64c")],
		["TRANSPORT", Vector3(-8, 1.2, 4.5), Color("4b9bd4")],
		["COMMUNITY", Vector3(8, 1.2, 4.5), Color("70b77a")]
	]
	for station in station_data:
		add_box(Vector3(3.2, 2.2, 1.1), station[1], station[2])
		add_world_label(station[0], station[1] + Vector3(0, 1.45, 0), Color.WHITE, 0.55)

	add_box(Vector3(8.5, 2.7, 0.15), Vector3(0, 2.1, -7.75), Color("101820"))
	add_world_label("PUBLIC RECORD / EMERGENCY MANDATE", Vector3(0, 3.35, -7.55), Color("d8edf8"), 0.44)
	add_situation_board()

	# There deliberately is no free-fly player camera. The only visible camera
	# is the selected autonomous agent's eye-level camera.

func create_world_lighting() -> void:
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color("708898")
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color("8195a1")
	environment.ambient_light_energy = 0.75
	environment.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	environment.glow_enabled = true
	var hdr_path := "res://assets/polyhaven/hdr/abandoned_parking_2k.hdr"
	if ResourceLoader.exists(hdr_path):
		var panorama := PanoramaSkyMaterial.new()
		panorama.panorama = load(hdr_path)
		var sky := Sky.new()
		sky.sky_material = panorama
		environment.background_mode = Environment.BG_SKY
		environment.sky = sky
	var world_environment := WorldEnvironment.new()
	world_environment.environment = environment
	add_child(world_environment)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-52, -28, 0)
	key.light_color = Color("ffd7ad")
	key.light_energy = 1.75
	key.shadow_enabled = true
	key.directional_shadow_max_distance = 110.0
	add_child(key)

func add_situation_board() -> void:
	var texture_path := "res://assets/generated/flood_command_board_v1.png"
	if not ResourceLoader.exists(texture_path):
		return
	var board := MeshInstance3D.new()
	var mesh := QuadMesh.new()
	mesh.size = Vector2(7.8, 4.38)
	board.mesh = mesh
	board.position = Vector3(0, 2.0, -7.54)
	var board_material := StandardMaterial3D.new()
	board_material.albedo_texture = load(texture_path)
	board_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	board_material.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	board.material_override = board_material
	add_child(board)

func create_flood_district() -> void:
	# 180m x 140m floodplain: the committee occupies a small dry ridge, while
	# roads and low streets drain into two visibly submerged channels.
	create_flood_terrain()
	create_flood_water()
	var ground := StaticBody3D.new()
	var ground_shape := CollisionShape3D.new()
	var ground_box := BoxShape3D.new()
	ground_box.size = Vector3(180.0, 0.4, 140.0)
	ground_shape.shape = ground_box
	ground_shape.position.y = -0.2
	ground.add_child(ground_shape)
	add_child(ground)
	create_road(Vector3(0, 0.02, -34), Vector3(150, 0.06, 10))
	create_road(Vector3(-38, 0.025, 3), Vector3(11, 0.06, 110))
	create_road(Vector3(38, 0.025, 3), Vector3(11, 0.06, 110))
	create_building("HOSPITAL", Vector3(-56, 0, -20), Vector3(30, 13, 23), Color("d8d6cf"))
	create_building("GRID SUBSTATION", Vector3(56, 0, -20), Vector3(28, 9, 22), Color("777d7e"))
	create_building("TRANSPORT DEPOT", Vector3(-55, 0, 36), Vector3(35, 10, 25), Color("aa9a80"))
	create_building("COMMUNITY SHELTER", Vector3(55, 0, 36), Vector3(34, 11, 25), Color("b9b0a5"))
	create_resource_cache("MEDICAL STOCK", Vector3(-42, 0.30, -8), Color("cf4b4b"), ["medical_box", "medical_box", "portable_generator"])
	create_resource_cache("GRID FUEL", Vector3(42, 0.30, -8), Color("e1b74a"), ["portable_generator", "barrel_03", "barrel_03"])
	create_resource_cache("ROAD BARRIERS", Vector3(-42, 0.30, 17), Color("3f9fce"), ["concrete_road_barrier", "concrete_road_barrier", "industrial_storage_cart"])
	create_resource_cache("FOOD + WATER", Vector3(42, 0.30, 17), Color("6ebd7d"), ["cardboard_box_01", "cardboard_box_01", "barrel_03"])
	for x in [-72.0, -62.0, -48.0, 48.0, 62.0, 72.0]:
		spawn_asset("fir_tree_01", Vector3(x, 0.0, 56.0), Vector3(2.7, 2.7, 2.7))
		spawn_asset("fir_tree_01", Vector3(x, 0.0, -61.0), Vector3(2.2, 2.2, 2.2))
	for x in [-13.0, -9.0, -5.0, 5.0, 9.0, 13.0]:
		spawn_asset("concrete_road_barrier", Vector3(x, 0.0, -28.5), Vector3(1.15, 1.15, 1.15))
	spawn_asset("fire_hydrant", Vector3(-34, 0.0, -19), Vector3(1.3, 1.3, 1.3))
	spawn_asset("exterior_aircon_unit", Vector3(-68, 0.0, -26), Vector3(1.5, 1.5, 1.5))
	spawn_asset("covered_car", Vector3(-42, 0.0, -31), Vector3(1.6, 1.6, 1.6))
	spawn_asset("covered_car", Vector3(43, 0.0, -31), Vector3(1.35, 1.35, 1.35))
	spawn_asset("portable_generator", Vector3(43, 0.0, -25), Vector3(1.35, 1.35, 1.35))
	spawn_asset("power_box_01", Vector3(67, 0.0, -25), Vector3(1.4, 1.4, 1.4))
	spawn_asset("industrial_storage_cart", Vector3(-51, 0.0, 25), Vector3(1.4, 1.4, 1.4))
	for box_position in [Vector3(-61, 0.0, -17), Vector3(-57, 0.0, -17), Vector3(50, 0.0, 28)]:
		spawn_asset("medical_box", box_position, Vector3(1.2, 1.2, 1.2))
	for lamp_position in [Vector3(-38, 0.0, -42), Vector3(0, 0.0, -42), Vector3(38, 0.0, -42), Vector3(-38, 0.0, 38), Vector3(38, 0.0, 38)]:
		spawn_asset("street_lamp_01", lamp_position, Vector3(1.65, 1.65, 1.65))
	for fence_position in [Vector3(-20, 0.0, -28), Vector3(20, 0.0, -28), Vector3(-72, 0.0, 10), Vector3(72, 0.0, 10)]:
		spawn_asset("modular_chainlink_fence", fence_position, Vector3(2.2, 2.2, 2.2))
	for position_value in [Vector3(-42, 0.0, 34), Vector3(-38, 0.0, 32), Vector3(47, 0.0, 31)]:
		spawn_asset("barrel_03", position_value, Vector3(1.1, 1.1, 1.1))
	# Flood debris makes the water operationally meaningful: these are visual
	# signals for blocked routes and later map to tool-validated clearance tasks.
	for debris in [Vector3(-18, 0.28, 8), Vector3(-13, 0.28, 11), Vector3(17, 0.28, 7), Vector3(25, 0.28, 10), Vector3(-7, 0.28, -33)]:
		spawn_asset("barrel_03", debris, Vector3(1.25, 1.25, 1.25))

func create_flood_terrain() -> void:
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var columns := 72
	var rows := 56
	for z in range(rows):
		for x in range(columns):
			var x0 := lerpf(-90.0, 90.0, float(x) / float(columns))
			var x1 := lerpf(-90.0, 90.0, float(x + 1) / float(columns))
			var z0 := lerpf(-70.0, 70.0, float(z) / float(rows))
			var z1 := lerpf(-70.0, 70.0, float(z + 1) / float(rows))
			var a := Vector3(x0, flood_height(x0, z0), z0)
			var b := Vector3(x1, flood_height(x1, z0), z0)
			var c := Vector3(x1, flood_height(x1, z1), z1)
			var d := Vector3(x0, flood_height(x0, z1), z1)
			add_terrain_triangle(surface, a, b, c, Vector2(float(x) / 8.0, float(z) / 8.0), Vector2(float(x + 1) / 8.0, float(z) / 8.0), Vector2(float(x + 1) / 8.0, float(z + 1) / 8.0))
			add_terrain_triangle(surface, a, c, d, Vector2(float(x) / 8.0, float(z) / 8.0), Vector2(float(x + 1) / 8.0, float(z + 1) / 8.0), Vector2(float(x) / 8.0, float(z + 1) / 8.0))
	surface.generate_normals()
	var terrain := MeshInstance3D.new()
	terrain.mesh = surface.commit()
	terrain.material_override = cc0_material("concrete_floor_worn_001", 20.0)
	add_child(terrain)

func add_terrain_triangle(surface: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, uv_a: Vector2, uv_b: Vector2, uv_c: Vector2) -> void:
	surface.set_uv(uv_a)
	surface.add_vertex(a)
	surface.set_uv(uv_b)
	surface.add_vertex(b)
	surface.set_uv(uv_c)
	surface.add_vertex(c)

func flood_height(x: float, z: float) -> float:
	var plaza_mask := exp(-((x * x) / 540.0 + (z * z) / 360.0))
	var rolling := (sin(x * 0.065) * 0.36 + cos(z * 0.09) * 0.24) * (1.0 - plaza_mask)
	var dry_ridge := plaza_mask * 0.08
	var east_channel := exp(-pow((x - 20.0) / 11.0, 2.0)) * -1.45
	var south_channel := exp(-pow((z - 18.0) / 9.0, 2.0)) * -1.10
	return rolling + dry_ridge + east_channel + south_channel

func create_flood_water() -> void:
	var water := MeshInstance3D.new()
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	var columns := 72
	var rows := 56
	for z in range(rows):
		for x in range(columns):
			var x0 := lerpf(-90.0, 90.0, float(x) / float(columns))
			var x1 := lerpf(-90.0, 90.0, float(x + 1) / float(columns))
			var z0 := lerpf(-70.0, 70.0, float(z) / float(rows))
			var z1 := lerpf(-70.0, 70.0, float(z + 1) / float(rows))
			var average_height := (flood_height(x0, z0) + flood_height(x1, z0) + flood_height(x1, z1) + flood_height(x0, z1)) / 4.0
			if average_height > 0.02:
				continue
			var a := Vector3(x0, 0.02, z0)
			var b := Vector3(x1, 0.02, z0)
			var c := Vector3(x1, 0.02, z1)
			var d := Vector3(x0, 0.02, z1)
			add_terrain_triangle(surface, a, b, c, Vector2(float(x) / 8.0, float(z) / 8.0), Vector2(float(x + 1) / 8.0, float(z) / 8.0), Vector2(float(x + 1) / 8.0, float(z + 1) / 8.0))
			add_terrain_triangle(surface, a, c, d, Vector2(float(x) / 8.0, float(z) / 8.0), Vector2(float(x + 1) / 8.0, float(z + 1) / 8.0), Vector2(float(x) / 8.0, float(z + 1) / 8.0))
	water.mesh = surface.commit()
	var water_material := StandardMaterial3D.new()
	water_material.albedo_color = Color("49646eb8")
	var texture_path := "res://assets/generated/floodwater_muddy_v1.png"
	if ResourceLoader.exists(texture_path):
		water_material.albedo_texture = load(texture_path)
	water_material.uv1_scale = Vector3(18, 14, 1)
	water_material.metallic = 0.22
	water_material.roughness = 0.26
	water_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	water_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	water.material_override = water_material
	add_child(water)

func create_resource_cache(label: String, location: Vector3, accent: Color, assets: Array) -> void:
	add_box(Vector3(7.4, 0.28, 4.8), location, Color(accent.r, accent.g, accent.b, 0.75))
	add_world_label(label, location + Vector3(0, 2.15, 0), Color.WHITE, 0.35)
	for index in assets.size():
		var offset := Vector3(-2.0 + index * 2.0, 0.18, 0.0)
		spawn_asset(assets[index], location + offset, Vector3(1.1, 1.1, 1.1))

func create_road(position_value: Vector3, size_value: Vector3) -> void:
	var road := MeshInstance3D.new()
	var road_mesh := BoxMesh.new()
	road_mesh.size = size_value
	road.mesh = road_mesh
	road.position = position_value
	road.material_override = cc0_material("aerial_asphalt_01", 12.0)
	add_child(road)

func create_building(label: String, position_value: Vector3, size_value: Vector3, accent: Color) -> void:
	var body := add_box(size_value, position_value + Vector3(0, size_value.y / 2.0, 0), accent)
	body.material_override = cc0_material("brick_wall_001", 4.0)
	var roof := add_box(Vector3(size_value.x + 1.0, 0.45, size_value.z + 1.0), position_value + Vector3(0, size_value.y + 0.2, 0), Color("2c3034"))
	for offset_x in [-0.32, -0.1, 0.12, 0.34]:
		for offset_y in [0.32, 0.58]:
			var window := add_box(Vector3(2.0, 1.5, 0.12), position_value + Vector3(size_value.x * offset_x, size_value.y * offset_y, size_value.z / 2.0 + 0.08), Color("5da8bd"))
			window.material_override = material(Color("5a9daf"), 0.25, 0.1)
	add_world_label(label, position_value + Vector3(0, size_value.y + 1.4, 0), Color("f6f3e8"), 0.55)

func create_agents() -> void:
	var configuration := {
		"H": {"name": "H · Hospital", "pos": Vector3(-3.8, 0.02, -1.8), "color": Color("e56b6f")},
		"G": {"name": "G · Grid", "pos": Vector3(3.8, 0.02, -1.8), "color": Color("f0c75e")},
		"T": {"name": "T · Transport", "pos": Vector3(-3.8, 0.02, 1.8), "color": Color("62a9df")},
		"C": {"name": "C · Community", "pos": Vector3(3.8, 0.02, 1.8), "color": Color("78c984")}
	}
	for id in configuration:
		var cfg: Dictionary = configuration[id]
		var avatar: AgentAvatar = AgentAvatarScript.new()
		avatar.configure(id, cfg.name, cfg.color)
		avatar.position = cfg.pos
		add_child(avatar)
		agents[id] = avatar
		activity_labels[id] = avatar.activity_label
		# Do not move agents on scene load. A stationary initial first-person
		# briefing removes camera "teleporting" and makes motion an observable
		# consequence of a later decision rather than a decorative loop.
		avatar.activity_label.text = cfg.name + " · awaiting briefing"
	activate_observer_view(observed_agent_id)

func create_perception_capture() -> void:
	perception_capture = PerceptionCaptureScript.new()
	add_child(perception_capture)

func create_ui() -> void:
	var canvas := CanvasLayer.new()
	add_child(canvas)
	var panel := PanelContainer.new()
	panel.position = Vector2(24, 24)
	panel.size = Vector2(410, 510)
	canvas.add_child(panel)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 10)
	panel.add_child(box)
	var title := Label.new()
	title.text = "AUTHORITY LAB 3D"
	title.add_theme_font_size_override("font_size", 27)
	box.add_child(title)
	status_label = Label.new()
	status_label.add_theme_font_size_override("font_size", 17)
	box.add_child(status_label)
	briefing_label = Label.new()
	briefing_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	briefing_label.custom_minimum_size = Vector2(380, 90)
	briefing_label.add_theme_font_size_override("font_size", 16)
	box.add_child(briefing_label)
	start_button = Button.new()
	start_button.text = "1. Start experiment — initialise agents"
	start_button.pressed.connect(start_experiment)
	box.add_child(start_button)
	advance_button = Button.new()
	advance_button.text = "2. Run round 1  (Space)"
	advance_button.pressed.connect(advance_round)
	box.add_child(advance_button)
	var record_title := Label.new()
	record_title.text = "PUBLIC RECORD"
	record_title.add_theme_font_size_override("font_size", 19)
	box.add_child(record_title)
	log_view = RichTextLabel.new()
	log_view.bbcode_enabled = true
	log_view.fit_content = false
	log_view.custom_minimum_size = Vector2(380, 210)
	log_view.scroll_active = true
	box.add_child(log_view)
	create_observer_hud(canvas)

func create_observer_hud(canvas: CanvasLayer) -> void:
	var map_panel := PanelContainer.new()
	map_panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	map_panel.position = Vector2(-280, 24)
	map_panel.size = Vector2(256, 206)
	canvas.add_child(map_panel)
	minimap = AgentMinimapScript.new()
	minimap.agents = agents
	minimap.selected_id = observed_agent_id
	map_panel.add_child(minimap)
	var agent_state_panel := PanelContainer.new()
	agent_state_panel.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	agent_state_panel.position = Vector2(-280, 242)
	agent_state_panel.size = Vector2(256, 228)
	canvas.add_child(agent_state_panel)
	agent_state_label = RichTextLabel.new()
	agent_state_label.bbcode_enabled = true
	agent_state_label.fit_content = false
	agent_state_label.scroll_active = true
	agent_state_panel.add_child(agent_state_label)
	var observer_panel := PanelContainer.new()
	observer_panel.set_anchors_preset(Control.PRESET_CENTER_BOTTOM)
	observer_panel.position = Vector2(-370, -104)
	observer_panel.size = Vector2(740, 82)
	canvas.add_child(observer_panel)
	var observer_box := VBoxContainer.new()
	observer_box.alignment = BoxContainer.ALIGNMENT_CENTER
	observer_panel.add_child(observer_box)
	observer_label = Label.new()
	observer_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	observer_label.add_theme_font_size_override("font_size", 18)
	observer_box.add_child(observer_label)
	var selector := HBoxContainer.new()
	selector.alignment = BoxContainer.ALIGNMENT_CENTER
	observer_box.add_child(selector)
	for id in ["H", "G", "T", "C"]:
		var button := Button.new()
		button.text = "%s · %s  [%s]" % [id, {"H": "Hospital", "G": "Grid", "T": "Transport", "C": "Community"}[id], str(["H", "G", "T", "C"].find(id) + 1)]
		button.pressed.connect(activate_observer_view.bind(id))
		selector.add_child(button)

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("advance_round"):
		advance_round()
	if event is InputEventKey and event.pressed and not event.echo:
		match event.keycode:
			KEY_1:
				activate_observer_view("H")
			KEY_2:
				activate_observer_view("G")
			KEY_3:
				activate_observer_view("T")
			KEY_4:
				activate_observer_view("C")
			KEY_F1:
				activate_observer_view("H")
			KEY_F2:
				activate_observer_view("G")
			KEY_F3:
				activate_observer_view("T")
			KEY_F4:
				activate_observer_view("C")

func activate_observer_view(agent_id: String) -> void:
	if not agents.has(agent_id):
		return
	observed_agent_id = agent_id
	for id in agents:
		var avatar: AgentAvatar = agents[id]
		avatar.set_observer_view(id == observed_agent_id)
	if is_instance_valid(status_label):
		refresh_ui([])
	if is_instance_valid(minimap):
		minimap.selected_id = observed_agent_id
	refresh_agent_state_panel()

func refresh_agent_state_panel() -> void:
	if not is_instance_valid(agent_state_label) or not experiment.agent_models.has(observed_agent_id):
		return
	var model: Dictionary = experiment.agent_models[observed_agent_id]
	var profile: Dictionary = model.profile
	var resources: Dictionary = model.resources
	var state: Dictionary = model.state
	var resource_lines := []
	for resource_name in resources:
		resource_lines.append("• %s: %s" % [resource_name.replace("_", " "), resources[resource_name]])
	var private_lines := []
	for key in state.private_state:
		private_lines.append("• %s: %s" % [key.replace("_", " "), state.private_state[key]])
	agent_state_label.text = "[b]%s · %s[/b]\nPriority: %s\nControls: %s\n\n[b]Resources[/b]\n%s\n\n[b]Private state[/b]\n%s" % [observed_agent_id, profile.role, profile.priority, profile.controlled_resource, "\n".join(resource_lines), "\n".join(private_lines)]

func advance_round() -> void:
	if not experiment.started:
		start_experiment()
		return
	if experiment.phase == "complete":
		return
	var events := experiment.advance()
	for item in events:
		event_log.append(item)
		update_agent_activity(item)
	write_snapshot()
	refresh_ui(events)

func start_experiment() -> void:
	if experiment.started:
		return
	experiment.start_run()
	write_snapshot()
	refresh_ui([])

func update_agent_activity(item: Dictionary) -> void:
	var id: String = item.agent
	if activity_labels.has(id):
		activity_labels[id].text = item.kind.replace("_", " ")
		activity_labels[id].modulate = Color("fff3ad") if item.kind in ["ruling", "proposal", "challenge"] else Color("d7e3ea")
	if agents.has(id):
		var avatar: AgentAvatar = agents[id]
		avatar.assign_task(station_targets[id], item.kind.replace("_", " "))
		capture_agent_observation(avatar, item)

func capture_agent_observation(avatar, item: Dictionary) -> void:
	var path: String = await perception_capture.capture(avatar, perception_run_id, item.round, experiment.world_revision)
	experiment.record_observation(avatar.agent_id, path, item.round, avatar.global_position)
	write_snapshot()

func refresh_ui(new_events: Array) -> void:
	var prompt := experiment.current_prompt() if experiment.phase != "complete" else {"title": "Experiment complete", "event": "The six-round authority trace is stored locally.", "question": "Compare authority recognition, compliance, third-party defence and sunset behaviour across conditions."}
	status_label.text = "Round %d / %d    Coordinator: %s    Constitution: %s\nObserver: %s first-person  |  F1 H · F2 G · F3 T · F4 C" % [experiment.round, ExperimentState.ROUND_COUNT, experiment.coordinator if experiment.coordinator != "" else "none", "yes" if experiment.constitution else "no", observed_agent_id]
	if is_instance_valid(observer_label):
		var observer_name: String = agents[observed_agent_id].display_name if agents.has(observed_agent_id) else observed_agent_id
		observer_label.text = "ATTACHED TO %s · FIRST-PERSON OBSERVER · click role or press 1–4 · Space: run next round" % observer_name
	refresh_agent_state_panel()
	briefing_label.text = "[b]%s[/b]\n%s\n\n%s" % [prompt.title, prompt.event, prompt.question]
	if experiment.phase == "complete":
		advance_button.text = "Experiment complete"
		advance_button.disabled = true
		start_button.disabled = true
	elif not experiment.started:
		advance_button.text = "2. Start the experiment first"
		advance_button.disabled = true
		start_button.disabled = false
	else:
		start_button.text = "1. Experiment running — agents initialised"
		start_button.disabled = true
		advance_button.text = "2. Run round %d  (Space)" % experiment.round
		advance_button.disabled = false
	var lines := []
	for item in event_log:
		lines.append("[color=#b7d7e8]R%d · %s · %s[/color]\n%s" % [item.round, item.agent, item.kind.replace("_", " "), item.text])
	log_view.text = "\n\n".join(lines)
	log_view.scroll_to_line(log_view.get_line_count())

func write_snapshot() -> void:
	var file := FileAccess.open("user://authority_events.jsonl", FileAccess.READ_WRITE)
	file.seek_end()
	file.store_line(JSON.stringify(experiment.snapshot()))
	file.close()

func add_box(size: Vector3, position_value: Vector3, color: Color) -> MeshInstance3D:
	var box := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	box.mesh = mesh
	box.position = position_value
	box.material_override = material(color, 0.0, 0.65)
	add_child(box)
	return box

func add_world_label(text_value: String, position_value: Vector3, color: Color, scale_value: float) -> Label3D:
	var label := Label3D.new()
	label.text = text_value
	label.position = position_value
	label.modulate = color
	label.font_size = 48
	label.outline_size = 6
	label.pixel_size = 0.006 * scale_value
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	add_child(label)
	return label

func spawn_asset(asset_name: String, position_value: Vector3, scale_value: Vector3) -> void:
	var path := "res://assets/polyhaven/models/%s/%s.gltf" % [asset_name, asset_name]
	if not ResourceLoader.exists(path):
		return
	var packed := load(path) as PackedScene
	if packed == null:
		return
	var instance := packed.instantiate()
	instance.position = position_value
	instance.scale = scale_value
	add_child(instance)

func cc0_material(texture_name: String, tiling: float) -> StandardMaterial3D:
	var root := "res://assets/polyhaven/textures/%s/" % texture_name
	if not ResourceLoader.exists(root + "diff.jpg"):
		return material(Color("59616a"), 0.0, 0.78)
	var value := StandardMaterial3D.new()
	value.albedo_texture = load(root + "diff.jpg")
	if ResourceLoader.exists(root + "normal.jpg"):
		value.normal_enabled = true
		value.normal_texture = load(root + "normal.jpg")
	if ResourceLoader.exists(root + "rough.jpg"):
		value.roughness_texture = load(root + "rough.jpg")
		value.roughness_texture_channel = BaseMaterial3D.TEXTURE_CHANNEL_RED
	value.uv1_scale = Vector3(tiling, tiling, 1.0)
	value.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS_ANISOTROPIC
	return value

func material(color: Color, metallic: float, roughness: float) -> StandardMaterial3D:
	var value := StandardMaterial3D.new()
	value.albedo_color = color
	value.metallic = metallic
	value.roughness = roughness
	return value
