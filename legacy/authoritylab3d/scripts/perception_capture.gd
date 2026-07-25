class_name PerceptionCapture
extends Node3D

# Shared, demand-driven visual sensor. There is deliberately one camera and one
# render target for the whole simulation—not one continuously rendering camera
# per agent. World meshes and textures remain resident; only a requested
# first-person view is rasterized once and then cached as experiment evidence.
var sensor_viewport: SubViewport
var sensor_camera: Camera3D
var cached_frames := {}

func _ready() -> void:
	sensor_viewport = SubViewport.new()
	sensor_viewport.name = "SharedPerceptionSensor"
	sensor_viewport.size = Vector2i(640, 360)
	sensor_viewport.render_target_update_mode = SubViewport.UPDATE_DISABLED
	sensor_viewport.world_3d = get_world_3d()
	add_child(sensor_viewport)
	sensor_camera = Camera3D.new()
	sensor_camera.fov = 78.0
	sensor_camera.current = true
	sensor_viewport.add_child(sensor_camera)

func capture(agent, run_id: String, round_number: int, world_revision: int) -> String:
	var cache_key := "%s/%d/%d/%s" % [run_id, round_number, world_revision, agent.agent_id]
	if cached_frames.has(cache_key):
		return cached_frames[cache_key]
	# This is a camera-transform change inside an already loaded World3D. It
	# allocates no duplicate district, terrain, texture or agent scene.
	sensor_camera.global_transform = agent.first_person_camera.global_transform
	sensor_viewport.render_target_update_mode = SubViewport.UPDATE_ONCE
	await RenderingServer.frame_post_draw
	var image := sensor_viewport.get_texture().get_image()
	var directory := "user://perception/" + run_id
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(directory))
	var output := directory + "/round_%02d_%s_rev_%03d.png" % [round_number, agent.agent_id, world_revision]
	image.save_png(ProjectSettings.globalize_path(output))
	cached_frames[cache_key] = output
	print("PERCEPTION_CAPTURE_SHARED agent=%s path=%s" % [agent.agent_id, output])
	return output
