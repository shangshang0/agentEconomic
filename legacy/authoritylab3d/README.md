# Authority Lab 3D

A desktop 3D experimental environment for studying whether LLM agents can create,
recognise, defend, challenge, and end authority without a hard-coded leader.

The initial scene is **The Forty-Eight Hour Committee**: four autonomous
organisations coordinate a flood emergency. The six rounds instantiate the
research conditions: no leader, proposal, low-cost coordination, costly ruling,
challenge, and sunset.

## Design choices

- **Godot 4.7 desktop project**: current, open source, scriptable and reproducible.
- **No proprietary or unlicensed art dependency in the baseline**: the room and
  avatars are procedural primitives, so the experiment always builds. Licensed
  realistic assets can be layered in later without changing experimental logic.
- **Experiment core separated from rendering**: `ExperimentState` owns rounds,
  institution state and event logs; `CommitteeRoom` only visualises it.
- **Human-readable event trace**: each state transition is appended to
  `user://authority_events.jsonl` for audit and later analysis.
- **Original generated art is tracked separately**: the flood command board is
  `assets/generated/flood_command_board_v1.png`; it is used as an in-world
  situation-map texture, not as evidence or experimental data.

## Current controls

- Click **Run round** or press Space.
- Click an on-screen role button or press **1–4** (F1–F4 also work when macOS
  does not reserve them) to attach the observer to H, G, T or C. This switches
  only the displayed first-person camera; it never hands movement control to a
  person. The HUD identifies the attached role and includes a live minimap.
- Each AgentAvatar walks/runs/jumps autonomously toward its assigned task. They
  remain still during the initial briefing; movement begins only after an
  experimental action. When an agent acts, its separate 640×360 eye-level
  perception camera renders one frame and saves a PNG
  under `user://perception/local_preview/`. Those frames are the input boundary
  intended for a later vision-capable decision model.
- The six scripted rounds are a visual and logging validation fixture. The next
  implementation replaces `scripted_events()` with messages from four LLM agents
  while preserving the same event schema.

## Code-only operation

No scene assembly is required from a person. The room, furniture, avatars,
lighting, UI and event log are created by `committee_room.gd`. Run the regression
fixture without opening the editor:

```bash
./run_checks.sh
```

The test runs all six rounds, verifies the institutional trace and exits.

## Reference projects (studied, not copied)

- AI2-THOR: object affordances, rich post-action metadata and multi-agent camera
  conventions (Apache-2.0).
- VirtualHome: executable action programs plus an evolving environment graph
  (MIT).
- TDW: controller / build separation, multi-agent simulations and navigation
  interfaces (BSD-2-Clause).
