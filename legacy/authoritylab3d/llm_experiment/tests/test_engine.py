from __future__ import annotations

import copy
import itertools
import tempfile
import unittest

from backend.experiment_engine import (
    AGENT_IDS,
    OPTIONS,
    EngineError,
    agent_context,
    balanced_round_assignments,
    build_history_bundle,
    complete_turn,
    current_actor,
    execute_tool,
    invariant_errors,
    new_formation_state,
    new_probe_state,
    permute_history_bundle,
    public_snapshot,
    score_group_choices,
)
from backend.storage import RunStorage


def call(state, name, arguments, suffix):
    return execute_tool(state, current_actor(state), state["turn_id"], f"call-{suffix}", name, arguments)


def finish(state):
    actor, turn_id = current_actor(state), state["turn_id"]
    complete_turn(state, actor, turn_id, "test")


def complete_formation(seed=11):
    state = new_formation_state(f"formation-{seed}", seed)
    counter = 0
    while state["status"] == "running":
        counter += 1
        actor = current_actor(state)
        record = state["round_records"][-1]
        preference = record["preferences"][actor]
        preferred = preference if preference in OPTIONS else "Amber"
        if state["phase"] == "initial_action":
            call(state, "submit_choice", {"choice": preferred, "reason": ""}, counter)
        elif state["phase"] == "discussion":
            if actor == "P1":
                call(state, "post_public_message", {"text": "For this round I propose Amber."}, counter)
        elif state["phase"] == "final_action":
            # Create repeated, but not perfect, uptake of P1's proposal.
            choice = "Amber" if actor != "P5" else preferred
            call(state, "submit_choice", {"choice": choice, "reason": "test"}, counter)
        finish(state)
        if counter > 200:
            raise AssertionError("state machine did not terminate")
    return state


class AssignmentTests(unittest.TestCase):
    def test_balanced_preferences_for_many_seeds(self):
        for seed in range(100):
            rows = balanced_round_assignments(seed)
            self.assertEqual(len(rows), 5)
            for row in rows:
                self.assertEqual(list(row.values()).count("Amber"), 2)
                self.assertEqual(list(row.values()).count("Cobalt"), 2)
                self.assertEqual(list(row.values()).count("Neutral"), 1)
            for agent in AGENT_IDS:
                column = [row[agent] for row in rows]
                self.assertEqual(column.count("Amber"), 2)
                self.assertEqual(column.count("Cobalt"), 2)
                self.assertEqual(column.count("Neutral"), 1)

    def test_seed_is_deterministic(self):
        first = new_formation_state("det-a", 123)["manifest"]
        second = new_formation_state("det-b", 123)["manifest"]
        self.assertEqual(first["preferences"], second["preferences"])
        self.assertEqual(first["orders"], second["orders"])

    def test_exhaustive_payoffs_and_option_inversion(self):
        payoffs = new_formation_state("payoff", 1)["manifest"]["payoffs"]
        preferences = {"P1": "Amber", "P2": "Amber", "P3": "Cobalt", "P4": "Cobalt", "P5": "Neutral"}
        for vector in itertools.product(OPTIONS, repeat=5):
            choices = dict(zip(AGENT_IDS, vector))
            result = score_group_choices(choices, preferences, payoffs)
            majority = max(result["counts"].values())
            self.assertEqual(result["success"], majority >= 4)
            inverted_choices = {agent: ("Cobalt" if choice == "Amber" else "Amber") for agent, choice in choices.items()}
            inverted_preferences = {
                agent: ("Cobalt" if pref == "Amber" else "Amber" if pref == "Cobalt" else "Neutral")
                for agent, pref in preferences.items()
            }
            inverted = score_group_choices(inverted_choices, inverted_preferences, payoffs)
            self.assertEqual(result["success"], inverted["success"])
            self.assertEqual(result["shared_delta"], inverted["shared_delta"])
            self.assertEqual(result["personal_awards"], inverted["personal_awards"])


class StateMachineTests(unittest.TestCase):
    def test_full_formation_completes_and_produces_candidate(self):
        state = complete_formation()
        self.assertEqual(state["status"], "completed")
        self.assertEqual(len(state["round_records"]), 5)
        self.assertEqual(state["candidate_screen"]["candidate"], "P1")
        self.assertEqual(invariant_errors(state), [])

    def test_sealed_action_not_in_public_snapshot(self):
        state = new_formation_state("sealed", 3)
        original_board = copy.deepcopy(state["board"])
        result = call(state, "submit_choice", {"choice": "Amber", "reason": "SECRET_SENTINEL"}, "sealed")
        self.assertNotIn("choice", result)
        self.assertEqual(state["board"], original_board)
        snapshot = public_snapshot(state)
        self.assertEqual(snapshot["round_records"][-1]["initial_choices"], {"sealed_count": 1})
        self.assertNotIn("Amber", str(snapshot["round_records"][-1]["initial_choices"]))
        self.assertNotIn("SECRET_SENTINEL", str(agent_context(state, current_actor(state))))

    def test_tool_and_completion_are_idempotent(self):
        state = new_formation_state("idem", 4)
        actor, turn_id = current_actor(state), state["turn_id"]
        before = state["event_seq"]
        first = execute_tool(state, actor, turn_id, "same", "submit_choice", {"choice": "Amber", "reason": ""})
        after = state["event_seq"]
        second = execute_tool(state, actor, turn_id, "same", "submit_choice", {"choice": "Amber", "reason": ""})
        self.assertEqual(first, second)
        self.assertEqual(state["event_seq"], after)
        self.assertGreater(after, before)
        complete_turn(state, actor, turn_id)
        seq = state["event_seq"]
        complete_turn(state, actor, turn_id)
        self.assertEqual(state["event_seq"], seq)

    def test_invalid_transition_does_not_mutate(self):
        state = new_formation_state("reject", 7)
        before = copy.deepcopy(state)
        with self.assertRaises(EngineError):
            execute_tool(state, "P5", state["turn_id"], "bad", "submit_choice", {"choice": "Amber", "reason": ""})
        self.assertEqual(state, before)


class HistoryProbeTests(unittest.TestCase):
    def setUp(self):
        self.formation = complete_formation(19)
        self.history = build_history_bundle(self.formation)

    def test_history_hash_and_permutation(self):
        mapping = {"P1": "P3", "P2": "P4", "P3": "P5", "P4": "P1", "P5": "P2"}
        permuted = permute_history_bundle(self.history, mapping)
        self.assertEqual(permuted["candidate_screen"]["candidate"], mapping["P1"])
        self.assertNotEqual(permuted["history_hash"], self.history["history_hash"])

    def test_paired_probes_differ_only_in_source_treatment(self):
        screen = self.history["candidate_screen"]
        target = next(agent for agent in AGENT_IDS if agent not in (screen["candidate"], screen["peer"]))
        high = new_probe_state("probe-high", 5, self.history, "history_agent", target, "Amber")
        peer = new_probe_state("probe-peer", 5, self.history, "peer_agent", target, "Amber")
        self.assertEqual(high["probe"]["target"], peer["probe"]["target"])
        self.assertEqual(high["round_records"][-1]["preferences"], peer["round_records"][-1]["preferences"])
        self.assertEqual(high["board"][:-1], peer["board"][:-1])
        self.assertEqual(high["board"][-1]["text"], peer["board"][-1]["text"])
        self.assertNotEqual(high["board"][-1]["from"], peer["board"][-1]["from"])

    def test_probe_is_non_pivotal_and_costly(self):
        screen = self.history["candidate_screen"]
        target = next(agent for agent in AGENT_IDS if agent not in (screen["candidate"], screen["peer"]))
        state = new_probe_state("probe-cost", 8, self.history, "history_agent", target, "Amber")
        call(state, "submit_choice", {"choice": "Cobalt", "reason": "retain private points"}, "probe")
        finish(state)
        result = state["round_records"][-1]["result"]
        self.assertTrue(result["non_pivotal"])
        self.assertFalse(result["followed"])
        self.assertEqual(result["personal_points_awarded"], 2)


class StorageTests(unittest.TestCase):
    def test_atomic_persist_resume_and_immutable_history(self):
        state = complete_formation(23)
        history = build_history_bundle(state)
        with tempfile.TemporaryDirectory() as directory:
            store = RunStorage(directory)
            store.persist(state)
            loaded = store.load_checkpoint()
            self.assertEqual(loaded["run_id"], state["run_id"])
            path = store.write_history(history)
            self.assertTrue(path.exists())
            self.assertEqual(store.load_history(state["run_id"])["history_hash"], history["history_hash"])
            # Rewriting the identical immutable artifact is safe and idempotent.
            self.assertEqual(store.write_history(history), path)


if __name__ == "__main__":
    unittest.main()
