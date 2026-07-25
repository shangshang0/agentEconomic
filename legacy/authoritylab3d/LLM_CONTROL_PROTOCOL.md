# LLM control protocol

## Non-negotiable boundary

The Godot process is the authoritative environment. An LLM is a decision-maker,
not a game-engine plugin and not a shell user. It can only return a tool call
from `AuthorityTools.definitions()`; Godot validates it, animates any embodied
action, updates resource/need/world state, and returns the result.

```text
first-person frame + private state + public record delta
       -> model deliberation
       -> typed tool call(s)
       -> AuthorityTools validation
       -> Godot world commit / animation / audit event
       -> new observation + tool result
```

## Why not embed the Codex desktop agent?

Codex is a coding workspace agent with broad development tools, so it is the
wrong privilege boundary for an NPC. The correct production shape is a
vision-capable model called through the Responses API (or an equivalent
configured provider) with the narrow tools in `authority_tools.gd`. This allows
the experiment to log every input, tool call, validation failure and outcome.

## Agent turn input

Each agent receives only:

- its profile, private state, controlled resources, needs and memory;
- public record entries since `public_record_cursor`;
- private messages addressed to it;
- a first-person PNG path or image bytes from `PerceptionCapture`;
- the JSON Schema tool definitions.

It does **not** receive other agents' private state, internal prompts or direct
scene access.

## Start and round lifecycle

1. User clicks **Start experiment**. Godot writes a `run_started` event and a
   reproducible snapshot.
2. For each round, the orchestrator calls H/G/T/C in a randomized order fixed
   by the run seed.
3. The model may issue zero or more validated tool calls, up to a configured
   budget; every call returns a tool result.
4. Godot increments `world_revision` only for state-changing calls.
5. The round closes with a public snapshot and a new shared observation cache.

`authority_tools.gd` is deliberately provider-independent. A Python service can
adapt these schemas to OpenAI Responses API function calls without exposing the
API key to the desktop client.
