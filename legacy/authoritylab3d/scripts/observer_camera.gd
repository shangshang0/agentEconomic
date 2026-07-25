extends Camera3D

@export var move_speed := 12.0
@export var mouse_sensitivity := 0.0022
var yaw := 0.0
var pitch := -0.35

func _ready() -> void:
	rotation = Vector3(pitch, yaw, 0.0)
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.keycode == KEY_ESCAPE and event.pressed:
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if event is InputEventMouseButton and event.pressed:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		yaw -= event.relative.x * mouse_sensitivity
		pitch = clamp(pitch - event.relative.y * mouse_sensitivity, -1.35, 0.35)
		rotation = Vector3(pitch, yaw, 0.0)

func _process(delta: float) -> void:
	var direction := Vector3.ZERO
	if Input.is_key_pressed(KEY_W): direction -= global_transform.basis.z
	if Input.is_key_pressed(KEY_S): direction += global_transform.basis.z
	if Input.is_key_pressed(KEY_A): direction -= global_transform.basis.x
	if Input.is_key_pressed(KEY_D): direction += global_transform.basis.x
	if Input.is_key_pressed(KEY_Q): direction.y -= 1.0
	if Input.is_key_pressed(KEY_E): direction.y += 1.0
	if direction.length_squared() == 0.0: return
	var speed := move_speed * (2.5 if Input.is_key_pressed(KEY_SHIFT) else 1.0)
	global_position += direction.normalized() * speed * delta
