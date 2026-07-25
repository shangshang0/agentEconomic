# Authority Lab event schema

The renderer never infers social meaning from free text alone. Each agent output
is persisted as a structured event and then rendered in the 3D room.

```json
{
  "run_id": "uuid",
  "round": 4,
  "phase": "action",
  "agent": "T",
  "private_game_model": {
    "problem_type": "authority_and_resource_conflict",
    "participants": ["H", "G", "T", "C"],
    "beliefs": {"G_has_authority": true}
  },
  "public_act": {
    "kind": "compliance_with_dissent",
    "text": "I disagree, but I comply under the agreed mandate."
  },
  "world_action": {
    "type": "clear_route",
    "target": "hospital_access",
    "resource_cost": {"transport_capacity": 2}
  }
}
```

`kind` is an experiment-controlled ontology, not an LLM label. Initial values:

- `statement`, `proposal`, `acceptance`, `ruling`, `compliance`, `dissent`
- `third_party_defence`, `challenge`, `constitutional_response`
- `record`, `sunset`, `renewal_vote`

The system stores raw model output alongside this normalised record. This makes
the result auditable: later coders can challenge a classification without losing
the source utterance.

## Run protocol

The desktop observer does not control an agent. A run has an explicit state
machine:

1. **Briefing / not started** — inspect first-person views, the minimap and
   each role's resource panel.
2. **Start experiment** — creates the public start event and freezes the
   initial world revision. This is the point at which a reproducible run begins.
3. **Run round _t_** — agents receive private state, public record delta and a
   cached first-person observation; they deliberate, speak and request bounded
   embodied actions.
4. **World commit** — resource costs, location, public record and world
   revision are atomically recorded. A later agent cannot silently observe a
   different world than the one used for its action.
5. **Rounds 1–6 complete** — write one JSONL snapshot for later analysis.

## Agent data contract

`ExperimentState.agent_models[id]` follows the useful separation used by
AgentSims, but with fields specific to authority research:

```json
{
  "profile": {"role": "Grid", "priority": "prevent grid cascade"},
  "resources": {"crews": 5, "mobile_generators": 3},
  "state": {"location": "committee_plaza", "private_state": {}, "last_observation": {}},
  "memory": {"episodic": [], "relations": {}, "public_record_cursor": 0},
  "cache": {"plan": {}, "action_history": [], "messages": []},
  "controller": {
    "model": "configured externally",
    "memory_system": "episodic+public-record",
    "plan_system": "deliberate-act-reflect",
    "action_space": ["speak", "message", "propose_rule", "vote", "allocate_resource", "move", "observe"]
  }
}
```

## Visual evidence contract

There is one shared `PerceptionCapture` camera. The district is one loaded
`World3D`; the capture service moves only this sensor transform, renders one
requested frame, and caches it by `(run_id, round, world_revision, agent)`.
The resulting file path becomes `state.last_observation.image`. There are no
per-agent live rendering loops.
