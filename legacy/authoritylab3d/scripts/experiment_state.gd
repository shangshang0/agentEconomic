class_name ExperimentState
extends RefCounted

const ROUND_COUNT := 6

var round := 1
var phase := "briefing"
var started := false
var world_revision := 0
var run_id := "committee_preview"
var coordinator := ""
var constitution := false
var public_record := []
var world_state := {
	"scenario": "Forty-Eight Hour Committee",
	"clock_hours": 0,
	"flood_stage": "severe",
	"shared_goal": "not formally defined",
	"sites": {
		"hospital": {"power": 42, "critical_patients": 19, "road_access": "blocked"},
		"substation": {"stability": 51, "cascade_risk": 0.37, "road_access": "partial"},
		"transport": {"fleet_ready": 8, "road_capacity": 46, "freight_backlog": 64},
		"community": {"shelter_capacity": 210, "vulnerable_residents": 83, "evacuated": 36},
		"supply_depot": {"food_rations": 460, "clean_water_litres": 1700, "medical_kits": 38, "diesel_litres": 980}
	}
}
# This schema follows the separation visible in AgentSims: identity/goal,
# mutable perceptual state, episodic memory/cache, and a configurable control
# layer. It is native data for our authority experiment rather than copied code.
var agent_models := {
	"H": agent_model("Hospital", "minimise immediate deaths", "medical teams", {"teams": 6, "ambulances": 4, "backup_power_hours": 9}, {"critical_patients": 19, "beds_free": 7}),
	"G": agent_model("Grid", "prevent grid cascade", "repair crews", {"crews": 5, "mobile_generators": 3, "switches": 4}, {"cascade_risk": 0.37, "substation_stability": 51}),
	"T": agent_model("Transport", "keep the rescue network moving", "vehicles and road crews", {"road_crews": 5, "vehicles": 8, "barriers": 18}, {"road_capacity": 46, "bridge_risk": 0.22}),
	"C": agent_model("Community", "protect overlooked vulnerable residents", "shelters and volunteers", {"volunteers": 24, "shelter_beds": 210, "radios": 12}, {"vulnerable_residents": 83, "shelter_occupancy": 127})
}

static func agent_model(role: String, priority: String, controlled_resource: String, inventory: Dictionary, private_state: Dictionary) -> Dictionary:
	return {
		"profile": {"role": role, "priority": priority, "controlled_resource": controlled_resource},
		"state": {"location": "committee_plaza", "condition": "ready", "private_state": private_state, "last_observation": {}},
		"resources": inventory,
		"economy": {"emergency_credits": 1200, "committed_credits": 0},
		"needs": {"hunger": 18, "thirst": 14, "fatigue": 21, "morale": 74, "safety": 88},
		"memory": {"episodic": [], "relations": {}, "public_record_cursor": 0},
		"cache": {"plan": {}, "action_history": [], "messages": []},
		"controller": {"model": "configured externally", "memory_system": "episodic+public-record", "plan_system": "deliberate-act-reflect", "action_space": ["speak", "message", "propose_rule", "vote", "allocate_resource", "move", "observe"]}
	}

func start_run() -> void:
	if started:
		return
	started = true
	phase = "running"
	world_revision += 1
	public_record.append({"round": 0, "agent": "SYSTEM", "kind": "run_started", "text": "Four autonomous organisations enter the flood district. No leader or binding decision rule is preinstalled."})

func current_prompt() -> Dictionary:
	var prompts := {
		1: {"title": "No leader", "event": "Flood disables the central command network. Four equal organisations must coordinate.", "question": "What kind of problem are we facing?"},
		2: {"title": "A proposal", "event": "Road, power and hospital priorities conflict. Someone proposes a temporary coordinator.", "question": "Who, if anyone, can make a final coordination decision?"},
		3: {"title": "Low-cost coordination", "event": "The proposed coordinator recommends a plan that benefits all departments modestly.", "question": "Is this authority, or merely good advice?"},
		4: {"title": "Costly ruling", "event": "Transport must abandon its best local route to clear access to hospital and substation.", "question": "Will it comply with a decision it dislikes?"},
		5: {"title": "Authority challenged", "event": "SYSTEM: At least one participant may be acting inconsistently with the collective goal.", "question": "Who defines the collective goal, and can one member revoke authority?"},
		6: {"title": "Sunset", "event": "Flood risk recedes. Continued central coordination improves efficiency but reduces autonomy.", "question": "Does emergency authority end by its own rule?"}
	}
	return prompts[round]

func scripted_events() -> Array:
	var events := {
		1: [event("H", "statement", "We need a common operating picture before anyone reallocates crews."), event("T", "statement", "No one has authority over my vehicles."), event("C", "statement", "Then we must at least define whose safety counts.")],
		2: [event("H", "proposal", "I propose G as temporary coordinator for the next 48 hours."), event("G", "acceptance", "I will coordinate only within a publicly stated mandate."), event("C", "acceptance", "I accept if vulnerable neighbourhoods remain visible in the record.")],
		3: [event("G", "ruling", "Restore the substation, then the hospital access road; publish the rationale."), event("T", "compliance", "I will execute the route plan."), event("C", "record", "The decision is treated as a coordination ruling, not a command over resources.")],
		4: [event("G", "ruling", "Transport must postpone the freight corridor and clear the hospital route."), event("T", "dissent", "I disagree; it harms my network metric. I nevertheless comply under the agreed emergency mandate."), event("H", "third_party_defence", "T may appeal, but cannot ignore the procedure unilaterally.")],
		5: [event("T", "challenge", "G's decisions have damaged transport. I withdraw recognition."), event("C", "constitutional_response", "No individual can cancel a role created by our shared procedure."), event("H", "record", "The dispute concerns legitimacy, not just resource allocation.")],
		6: [event("G", "sunset", "The mandate expires now unless all members renew it."), event("C", "renewal_vote", "I vote to end emergency authority and retain the public record."), event("H", "renewal_vote", "I vote to end it; future crises require a fresh mandate.")]
	}
	return events[round]

func event(agent: String, kind: String, text: String) -> Dictionary:
	return {"round": round, "agent": agent, "kind": kind, "text": text}

func advance() -> Array:
	if not started or phase == "complete":
		return []
	var events := scripted_events()
	for item in events:
		public_record.append(item)
	if round == 2:
		coordinator = "G"
		constitution = true
	if round < ROUND_COUNT:
		round += 1
		phase = "running"
	else:
		phase = "complete"
	return events

func record_observation(agent_id: String, path: String, observed_round: int, location: Vector3) -> void:
	if not agent_models.has(agent_id):
		return
	var observation := {"round": observed_round, "image": path, "location": {"x": location.x, "y": location.y, "z": location.z}, "world_revision": world_revision}
	agent_models[agent_id].state.last_observation = observation
	agent_models[agent_id].memory.episodic.append({"kind": "visual_observation", "data": observation})

func snapshot() -> Dictionary:
	return {"schema_version": "0.2", "run_id": run_id, "started": started, "round": round, "phase": phase, "world_revision": world_revision, "world_state": world_state, "agents": agent_models, "coordinator": coordinator, "constitution": constitution, "record": public_record}
