extends SceneTree

# Code-only regression test. It validates the experimental state machine without
# opening a window or using the Godot editor.
const ExperimentStateScript = preload("res://scripts/experiment_state.gd")
const AuthorityToolsScript = preload("res://scripts/authority_tools.gd")

func _init() -> void:
	var state: ExperimentState = ExperimentStateScript.new()
	state.start_run()
	assert(AuthorityToolsScript.definitions().size() == 8, "Tool surface changed without updating the audit test")
	var allocation := AuthorityToolsScript.execute(state, "H", "allocate_resource", {"resource": "teams", "amount": 1, "destination": "hospital"})
	assert(allocation.ok and state.agent_models.H.resources.teams == 5, "Tool validation did not commit a controlled resource")
	var event_count := 0
	while state.phase != "complete":
		event_count += state.advance().size()
	assert(event_count == 18, "Expected 18 fixture events, got %d" % event_count)
	assert(state.coordinator == "G", "The fixture must create G's temporary role")
	assert(state.constitution, "The fixture must record a public mandate")
	assert(state.public_record.size() == 19, "Public record must include the start event plus 18 round events")
	print("AUTHORITY_LAB_SMOKE_OK events=%d coordinator=%s phase=%s" % [event_count, state.coordinator, state.phase])
	quit(0)
