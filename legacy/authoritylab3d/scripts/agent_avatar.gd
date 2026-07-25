class_name AgentAvatar
extends CharacterBody3D

# Autonomous embodied agent. User input never enters this controller.
# The main camera is for a human observer who "possesses" the viewpoint; the
# SubViewport camera produces the same first-person evidence for an LLM agent.

var agent_id := ""
var display_name := ""
var accent := Color.WHITE
var walk_speed := 2.6
var run_speed := 4.8
var task_target := Vector3.ZERO
var has_target := false
var last_heading := Vector3.FORWARD
var jump_cooldown := 0.0
var gait_phase := 0.0

var left_arm: MeshInstance3D
var right_arm: MeshInstance3D
var left_leg: MeshInstance3D
var right_leg: MeshInstance3D

var first_person_camera: Camera3D
var activity_label: Label3D

func configure(id: String, name_value: String, color: Color) -> void:
	agent_id = id
	display_name = name_value
	accent = color

func _ready() -> void:
	name = "Agent_" + agent_id
	create_body()
	create_first_person_camera()

func create_body() -> void:
	var collider := CollisionShape3D.new()
	var capsule_shape := CapsuleShape3D.new()
	capsule_shape.radius = 0.33
	capsule_shape.height = 1.72
	collider.shape = capsule_shape
	collider.position.y = 0.86
	add_child(collider)
	var torso := MeshInstance3D.new()
	var torso_mesh := CapsuleMesh.new()
	torso_mesh.radius = 0.33
	torso_mesh.height = 1.15
	torso.mesh = torso_mesh
	torso.position.y = 0.77
	var torso_material := StandardMaterial3D.new()
	torso_material.albedo_color = accent
	torso_material.roughness = 0.56
	torso.material_override = torso_material
	add_child(torso)
	var head := MeshInstance3D.new()
	var head_mesh := SphereMesh.new()
	head_mesh.radius = 0.29
	head_mesh.height = 0.58
	head.mesh = head_mesh
	head.position.y = 1.48
	head.material_override = skin_material()
	add_child(head)
	left_arm = make_limb(Vector3(-0.43, 1.08, -0.10), 0.62, accent)
	left_arm.rotation_degrees.z = -16.0
	right_arm = make_limb(Vector3(0.43, 1.08, -0.10), 0.62, accent)
	right_arm.rotation_degrees.z = 16.0
	left_leg = make_limb(Vector3(-0.16, 0.34, 0.02), 0.73, Color("26313b"))
	right_leg = make_limb(Vector3(0.16, 0.34, 0.02), 0.73, Color("26313b"))
	add_hand(Vector3(-0.49, 0.78, -0.17))
	add_hand(Vector3(0.49, 0.78, -0.17))
	activity_label = Label3D.new()
	activity_label.text = display_name + " · autonomous"
	activity_label.position = Vector3(0, 2.15, 0)
	activity_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	activity_label.pixel_size = 0.0038
	activity_label.outline_size = 6
	add_child(activity_label)

func make_limb(location: Vector3, length: float, color: Color) -> MeshInstance3D:
	var limb := MeshInstance3D.new()
	var mesh := CapsuleMesh.new()
	mesh.radius = 0.13
	mesh.height = length
	limb.mesh = mesh
	limb.position = location
	var limb_material := StandardMaterial3D.new()
	limb_material.albedo_color = color
	limb_material.roughness = 0.68
	limb.material_override = limb_material
	add_child(limb)
	return limb

func add_hand(location: Vector3) -> void:
	var hand := MeshInstance3D.new()
	var mesh := SphereMesh.new()
	mesh.radius = 0.15
	mesh.height = 0.30
	hand.mesh = mesh
	hand.position = location
	hand.material_override = skin_material()
	add_child(hand)

func skin_material() -> StandardMaterial3D:
	var value := StandardMaterial3D.new()
	value.albedo_color = Color("d6ad91")
	value.roughness = 0.78
	return value

func create_first_person_camera() -> void:
	first_person_camera = Camera3D.new()
	first_person_camera.name = "ObserverFirstPersonCamera"
	first_person_camera.position = Vector3(0, 1.55, 0)
	first_person_camera.rotation.x = deg_to_rad(-5.0)
	first_person_camera.current = false
	add_child(first_person_camera)

func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity += get_gravity() * delta
	jump_cooldown = max(0.0, jump_cooldown - delta)
	if has_target:
		var direction := task_target - global_position
		direction.y = 0.0
		if direction.length() < 0.65:
			has_target = false
			velocity.x = move_toward(velocity.x, 0.0, walk_speed * 8.0 * delta)
			velocity.z = move_toward(velocity.z, 0.0, walk_speed * 8.0 * delta)
			activity_label.text = display_name + " · arrived"
		else:
			var horizontal := direction.normalized()
			last_heading = last_heading.lerp(horizontal, min(1.0, delta * 7.0)).normalized()
			velocity.x = horizontal.x * run_speed
			velocity.z = horizontal.z * run_speed
			# A Godot camera looks along local -Z. Point that axis toward the
			# direction of travel so both the observer and perception camera see
			# what this agent is approaching.
			# Avoid an instantaneous body/camera turn at the start of a task. This
			# is essential when the human observer is attached to the same camera.
			var desired_yaw := atan2(-last_heading.x, -last_heading.z)
			rotation.y = lerp_angle(rotation.y, desired_yaw, min(1.0, delta * 8.0))
			activity_label.text = display_name + " · executing task"
			if jump_cooldown <= 0.0 and is_on_floor() and direction.length() > 4.0 and randf() < 0.006:
				velocity.y = 5.0
				jump_cooldown = 4.0
	move_and_slide()
	update_gait(delta)

func update_gait(delta: float) -> void:
	var pace: float = Vector2(velocity.x, velocity.z).length()
	if pace > 0.15:
		gait_phase += delta * pace * 4.0
	var swing: float = sin(gait_phase) * minf(0.55, pace * 0.13)
	if is_instance_valid(left_arm):
		left_arm.rotation.x = swing
		right_arm.rotation.x = -swing
		left_leg.rotation.x = -swing
		right_leg.rotation.x = swing

func assign_task(destination: Vector3, activity: String) -> void:
	task_target = destination
	has_target = true
	activity_label.text = display_name + " · " + activity

func set_observer_view(active: bool) -> void:
	first_person_camera.current = active
