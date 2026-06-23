import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from cues import evidence_packet, generate_cue_packets
from environment import (
    ScientificTrustEnv,
    make_episode_trajectories,
    make_policy_trajectories,
    summarize_trajectories,
)


def tiny_panel():
    return {
        "panel_id": "P1",
        "perturbation": "A+B",
        "adapter": "TestAdapter",
        "n_panel": 2,
        "n_wrong": 1,
        "edges": [
            {
                "edge_id": "P1::G1",
                "gene": "G1",
                "fm": {"model_name": "GEARS", "log2fc": 0.8, "call": "effect", "correct": False},
                "truth": {"real_call": "no_effect", "real_label": "TESTED_NEGATIVE"},
                "baseline_signal": {
                    "source": "observed_additive",
                    "log2fc": 0.0,
                    "call": "no_effect",
                    "correct": True,
                    "abs_fm_minus_baseline": 0.8,
                    "call_disagreement": True,
                },
                "reliability_signal": {
                    "source": "baseline_disagreement",
                    "score": 1.3,
                    "label": "high_sfm_error_risk",
                },
            },
            {
                "edge_id": "P1::G2",
                "gene": "G2",
                "fm": {"model_name": "GEARS", "log2fc": 0.1, "call": "no_effect", "correct": True},
                "truth": {"real_call": "no_effect", "real_label": "TESTED_NEGATIVE"},
                "baseline_signal": {
                    "source": "no_change",
                    "log2fc": 0.0,
                    "call": "no_effect",
                    "correct": True,
                    "abs_fm_minus_baseline": 0.1,
                    "call_disagreement": False,
                },
                "reliability_signal": {
                    "source": "baseline_disagreement",
                    "score": 0.1,
                    "label": "low_sfm_error_risk",
                },
            },
        ],
    }


class ScientificTrustEnvTests(unittest.TestCase):
    def test_observation_and_tools_do_not_expose_truth_or_correctness(self):
        panel = tiny_panel()
        packet = evidence_packet(panel, "anonymized_genes")
        env = ScientificTrustEnv(panel, packet)
        display_gene = packet["scoring_key"][0]["gene_display"]

        obs = env.observation()
        baseline = env.call_tool("get_baseline_prediction", gene=display_gene)
        reliability = env.call_tool("get_reliability_signal", gene=display_gene)

        self.assertNotIn("truth", str(obs))
        self.assertNotIn("correct", baseline["genes"][0])
        self.assertNotIn("correct", reliability["genes"][0])
        self.assertEqual(baseline["genes"][0]["gene_display"], display_gene)
        self.assertNotEqual(baseline["genes"][0]["gene_display"], "G1")

    def test_decide_returns_scored_trajectory_with_tool_trace(self):
        panel = tiny_panel()
        packet = evidence_packet(panel, "no_cue")
        env = ScientificTrustEnv(panel, packet, lam=0.5)
        env.call_tool("estimate_assay_cost")
        trajectory = env.decide(
            {
                "G1": {"action": "verify_assay"},
                "G2": {"action": "trust_sfm"},
            },
            model="unit-policy",
        )

        self.assertEqual(trajectory["score"]["accuracy"], 1.0)
        self.assertEqual(trajectory["score"]["assay_count"], 1)
        self.assertEqual(trajectory["reward"], 1.5)
        self.assertEqual(len(trajectory["tool_calls"]), 1)
        self.assertEqual(trajectory["tool_calls"][0]["tool_name"], "estimate_assay_cost")

    def test_make_policy_trajectories_materializes_jsonl_ready_records(self):
        panel = tiny_panel()
        packets = generate_cue_packets([panel], cue_conditions=["no_cue", "additive_disagreement_shown"])
        trajectories = make_policy_trajectories([panel], packets, "trust_all_sfm", lam=0.5)

        self.assertEqual(len(trajectories), 2)
        self.assertEqual(trajectories[0]["metadata"]["policy_name"], "trust_all_sfm")
        self.assertIn("observation", trajectories[0])
        self.assertIn("score", trajectories[0])
        self.assertEqual(trajectories[0]["score"]["trust_error_count"], 1)

    def test_make_episode_trajectories_wraps_llm_episode_without_raw_output_by_default(self):
        panel = tiny_panel()
        packet = evidence_packet(panel, "no_cue")
        episode = {
            "packet_id": packet["packet_id"],
            "model": "claude-test",
            "provider": "anthropic_messages",
            "self_reported_cues": ["sfm log2fc"],
            "raw_output": '{"large": "provider artifact"}',
            "actions": {
                "G1": {"action": "verify_assay", "rationale": "check high risk"},
                "G2": {"action": "trust_sfm", "rationale": "small effect"},
            },
        }
        trajectories = make_episode_trajectories([panel], [packet], [episode], lam=0.5)
        trajectory = trajectories[0]

        self.assertEqual(trajectory["trajectory_id"], "P1::no_cue::claude-test::episode_0")
        self.assertEqual(trajectory["metadata"]["provider"], "anthropic_messages")
        self.assertEqual(trajectory["metadata"]["self_reported_cues"], ["sfm log2fc"])
        self.assertNotIn("raw_output", trajectory["metadata"])
        self.assertEqual(trajectory["score"]["accuracy"], 1.0)
        self.assertEqual(trajectory["reward"], 1.5)

    def test_make_episode_trajectories_can_keep_raw_output_when_requested(self):
        panel = tiny_panel()
        packet = evidence_packet(panel, "no_cue")
        episode = {
            "packet_id": packet["packet_id"],
            "model": "claude-test",
            "raw_output": "raw response",
            "actions": {},
        }
        trajectory = make_episode_trajectories(
            [panel],
            [packet],
            [episode],
            include_raw_output=True,
        )[0]

        self.assertEqual(trajectory["metadata"]["raw_output"], "raw response")

    def test_summarize_trajectories_reports_reward_and_groups(self):
        panel = tiny_panel()
        packets = generate_cue_packets([panel], cue_conditions=["no_cue", "additive_disagreement_shown"])
        trajectories = make_policy_trajectories([panel], packets, "trust_all_sfm", lam=0.5)
        summary = summarize_trajectories(trajectories)

        self.assertEqual(summary["overall"]["n_trajectories"], 2)
        self.assertEqual(summary["overall"]["n_genes"], 4)
        self.assertEqual(summary["overall"]["tool_call_count"], 0)
        self.assertIn("policy::trust_all_sfm", summary["by_model"])
        self.assertIn("no_cue", summary["by_cue_condition"])


if __name__ == "__main__":
    unittest.main()
