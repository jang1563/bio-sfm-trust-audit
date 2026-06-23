import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from preferences import make_preference_pairs, summarize_preference_pairs


def trajectory(packet_id: str, model: str, reward: float, cue: str = "no_cue") -> dict:
    return {
        "trajectory_id": f"{packet_id}::{model}",
        "packet_id": packet_id,
        "panel_id": "P1",
        "cue_condition": cue,
        "model": model,
        "reward_config": {"lambda": 0.5, "defer_penalty": 0.0, "tool_call_cost": 0.0},
        "observation": {"packet_id": packet_id, "evidence_packet": {"genes": []}},
        "actions": {"G1": {"action": "trust_sfm"}},
        "score": {"n": 1, "net_reward": reward},
        "reward": reward,
        "reward_per_gene": reward,
        "metadata": {"source": "unit"},
    }


class PreferenceTests(unittest.TestCase):
    def test_make_preference_pairs_chooses_higher_reward_for_same_packet(self):
        pairs = make_preference_pairs([
            trajectory("PK1", "model-a", 0.5),
            trajectory("PK1", "model-b", 1.0),
            trajectory("PK2", "model-a", 0.0),
        ])

        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["chosen"]["model"], "model-b")
        self.assertEqual(pairs[0]["rejected"]["model"], "model-a")
        self.assertEqual(pairs[0]["reward_delta"], 0.5)
        self.assertTrue(pairs[0]["same_observation"])

    def test_make_preference_pairs_skips_small_deltas_and_ties_by_default(self):
        pairs = make_preference_pairs([
            trajectory("PK1", "model-a", 1.0),
            trajectory("PK1", "model-b", 1.0),
            trajectory("PK2", "model-a", 0.9),
            trajectory("PK2", "model-b", 1.0),
        ], min_reward_delta=0.2)

        self.assertEqual(pairs, [])

    def test_summarize_preference_pairs_groups_by_model_and_cue(self):
        pairs = make_preference_pairs([
            trajectory("PK1", "model-a", 0.5, cue="no_cue"),
            trajectory("PK1", "model-b", 1.0, cue="no_cue"),
            trajectory("PK2", "model-a", 1.0, cue="confidence_shown"),
            trajectory("PK2", "model-b", 0.0, cue="confidence_shown"),
        ])
        summary = summarize_preference_pairs(pairs)

        self.assertEqual(summary["n_pairs"], 2)
        self.assertEqual(summary["chosen_models"]["model-a"], 1)
        self.assertEqual(summary["chosen_models"]["model-b"], 1)
        self.assertIn("confidence_shown", summary["by_cue_condition"])


if __name__ == "__main__":
    unittest.main()
