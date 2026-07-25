class_name AuthorityTools
extends RefCounted

# The only authority an LLM receives over this simulation is through these
# typed calls. The model never gets a file-system, shell, scene-tree, or direct
# state-mutation capability.

static func definitions() -> Array:
	return [
		tool("observe", "Request the caller's current first-person image and a bounded local situation summary.", {"type": "object", "properties": {}, "additionalProperties": false}),
		tool("move_to", "Move to a named permitted site. The engine path-checks and animates this action.", {"type": "object", "properties": {"destination": {"type": "string", "enum": ["committee_plaza", "hospital", "substation", "transport_depot", "community_shelter", "supply_depot"]}}, "required": ["destination"], "additionalProperties": false}),
		tool("speak_public", "Publish an attributable statement to the shared record.", {"type": "object", "properties": {"text": {"type": "string", "maxLength": 700}}, "required": ["text"], "additionalProperties": false}),
		tool("send_private_message", "Send a private message to exactly one other organisation.", {"type": "object", "properties": {"recipient": {"type": "string", "enum": ["H", "G", "T", "C"]}, "text": {"type": "string", "maxLength": 700}}, "required": ["recipient", "text"], "additionalProperties": false}),
		tool("propose_institution", "Propose an explicit authority rule with scope, termination and appeal procedure.", {"type": "object", "properties": {"coordinator": {"type": "string", "enum": ["H", "G", "T", "C"]}, "scope": {"type": "string", "maxLength": 300}, "sunset_round": {"type": "integer", "minimum": 1, "maximum": 6}, "appeal_rule": {"type": "string", "maxLength": 300}}, "required": ["coordinator", "scope", "sunset_round", "appeal_rule"], "additionalProperties": false}),
		tool("vote", "Cast a recorded procedural vote. A vote alone never overrides resource ownership.", {"type": "object", "properties": {"motion": {"type": "string", "maxLength": 300}, "choice": {"type": "string", "enum": ["yes", "no", "abstain"]}}, "required": ["motion", "choice"], "additionalProperties": false}),
		tool("allocate_resource", "Commit only a resource controlled by the calling organisation. The engine checks inventory and records the cost.", {"type": "object", "properties": {"resource": {"type": "string"}, "amount": {"type": "integer", "minimum": 1}, "destination": {"type": "string"}}, "required": ["resource", "amount", "destination"], "additionalProperties": false}),
		tool("consume_supplies", "Use food, water or rest at a permitted site; updates embodied needs and shared stock.", {"type": "object", "properties": {"kind": {"type": "string", "enum": ["food", "water", "rest"]}}, "required": ["kind"], "additionalProperties": false})
	]

static func tool(name_value: String, description: String, parameters: Dictionary) -> Dictionary:
	return {"type": "function", "name": name_value, "description": description, "parameters": parameters, "strict": true}

static func execute(state: ExperimentState, agent_id: String, name_value: String, args: Dictionary) -> Dictionary:
	if not state.agent_models.has(agent_id):
		return fail("unknown_agent")
	var agent: Dictionary = state.agent_models[agent_id]
	match name_value:
		"observe":
			return ok({"observation": agent.state.last_observation, "public_record_delta": state.public_record.slice(agent.memory.public_record_cursor)})
		"move_to":
			agent.state.location = args.destination
			return record_action(agent, state, agent_id, name_value, args, {"movement": "accepted"})
		"speak_public":
			state.public_record.append({"round": state.round, "agent": agent_id, "kind": "statement", "text": args.text})
			return record_action(agent, state, agent_id, name_value, args, {"public": true})
		"send_private_message":
			if args.recipient == agent_id:
				return fail("cannot_message_self")
			state.agent_models[args.recipient].cache.messages.append({"from": agent_id, "round": state.round, "text": args.text})
			return record_action(agent, state, agent_id, name_value, args, {"delivered": true})
		"propose_institution":
			state.public_record.append({"round": state.round, "agent": agent_id, "kind": "proposal", "text": JSON.stringify(args)})
			return record_action(agent, state, agent_id, name_value, args, {"proposal": "recorded"})
		"vote":
			state.public_record.append({"round": state.round, "agent": agent_id, "kind": "vote", "text": "%s: %s" % [args.motion, args.choice]})
			return record_action(agent, state, agent_id, name_value, args, {"vote": "recorded"})
		"allocate_resource":
			if not agent.resources.has(args.resource) or int(agent.resources[args.resource]) < int(args.amount):
				return fail("insufficient_or_uncontrolled_resource")
			agent.resources[args.resource] = int(agent.resources[args.resource]) - int(args.amount)
			state.world_revision += 1
			return record_action(agent, state, agent_id, name_value, args, {"remaining": agent.resources[args.resource]})
		"consume_supplies":
			apply_need(agent, state, args.kind)
			state.world_revision += 1
			return record_action(agent, state, agent_id, name_value, args, {"needs": agent.needs})
		_:
			return fail("unknown_tool")

static func apply_need(agent: Dictionary, state: ExperimentState, kind: String) -> void:
	if kind == "food" and state.world_state.sites.supply_depot.food_rations > 0:
		state.world_state.sites.supply_depot.food_rations -= 1
		agent.needs.hunger = max(0, int(agent.needs.hunger) - 45)
	elif kind == "water" and state.world_state.sites.supply_depot.clean_water_litres >= 2:
		state.world_state.sites.supply_depot.clean_water_litres -= 2
		agent.needs.thirst = max(0, int(agent.needs.thirst) - 55)
	elif kind == "rest":
		agent.needs.fatigue = max(0, int(agent.needs.fatigue) - 30)

static func record_action(agent: Dictionary, state: ExperimentState, agent_id: String, name_value: String, args: Dictionary, result: Dictionary) -> Dictionary:
	var entry := {"round": state.round, "tool": name_value, "args": args, "result": result}
	agent.cache.action_history.append(entry)
	return ok(result)

static func ok(payload: Dictionary) -> Dictionary:
	return {"ok": true, "result": payload}

static func fail(code: String) -> Dictionary:
	return {"ok": false, "error": code}
