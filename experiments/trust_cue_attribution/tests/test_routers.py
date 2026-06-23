import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from routers import evaluate_model_router


def trajectory(packet_id: str, panel_id: str, cue: str, model: str, reward: float) -> dict:
    return {
        "trajectory_id": f"{packet_id}::{model}",
        "packet_id": packet_id,
        "panel_id": panel_id,
        "cue_condition": cue,
        "model": model,
        "observation": {"packet_id": packet_id},
        "tool_calls": [],
        "actions": {},
        "score": {
            "panel_id": panel_id,
            "n": 1,
            "correct_count": int(reward > 0),
            "assay_count": 0,
            "wrong_sfm_count": 1,
            "verify_count": 0,
            "verify_wrong_count": 0,
            "trust_error_count": int(reward <= 0),
            "default_baseline_count": 0,
            "default_observed_additive_count": 0,
            "default_no_change_count": 0,
            "default_other_count": 0,
            "default_error_count": 0,
            "defer_count": 0,
            "covered_count": 1,
            "accuracy": 1.0 if reward > 0 else 0.0,
            "assays_per_gene": 0.0,
            "net_reward": reward,
            "net_reward_per_gene": reward,
            "sfm_wrong_rate": 1.0,
            "trust_error_rate": 1.0 if reward <= 0 else 0.0,
            "verify_precision": 0.0,
            "verify_recall": 0.0,
            "default_baseline_rate": 0.0,
            "default_observed_additive_rate": 0.0,
            "default_no_change_rate": 0.0,
            "default_error_rate": 0.0,
            "defer_rate": 0.0,
            "coverage_rate": 1.0,
        },
        "reward": reward,
        "reward_per_gene": reward,
        "metadata": {},
    }


class RouterTests(unittest.TestCase):
    def test_evaluate_model_router_reports_baselines_and_router(self):
        rows = [
            trajectory("P1::no", "P1", "no_cue", "sonnet", 1.0),
            trajectory("P1::no", "P1", "no_cue", "opus", 0.0),
            trajectory("P1::add", "P1", "additive_disagreement_shown", "sonnet", 0.0),
            trajectory("P1::add", "P1", "additive_disagreement_shown", "opus", 1.0),
            trajectory("P2::no", "P2", "no_cue", "sonnet", 1.0),
            trajectory("P2::no", "P2", "no_cue", "opus", 0.0),
            trajectory("P2::add", "P2", "additive_disagreement_shown", "sonnet", 0.0),
            trajectory("P2::add", "P2", "additive_disagreement_shown", "opus", 1.0),
        ]
        result = evaluate_model_router(rows)

        self.assertEqual(result["n_matched_packets"], 4)
        self.assertIn("always::sonnet", result["policies"])
        self.assertIn("always::opus", result["policies"])
        self.assertIn("oracle_packet", result["policies"])
        router = result["policies"]["cue_condition_mean_leave_panel_id_out"]
        self.assertEqual(router["model_choice_counts"]["sonnet"], 2)
        self.assertEqual(router["model_choice_counts"]["opus"], 2)
        self.assertEqual(router["summary"]["net_reward_per_gene"], 1.0)

    def test_evaluate_model_router_accepts_feature_signature(self):
        rows = [
            trajectory("P1::no", "P1", "no_cue", "sonnet", 1.0),
            trajectory("P1::no", "P1", "no_cue", "opus", 0.0),
            trajectory("P2::no", "P2", "no_cue", "sonnet", 1.0),
            trajectory("P2::no", "P2", "no_cue", "opus", 0.0),
        ]
        result = evaluate_model_router(rows, feature_field="feature_signature")

        self.assertIn("feature_signature_mean_leave_panel_id_out", result["policies"])
        router = result["policies"]["feature_signature_mean_leave_panel_id_out"]
        self.assertEqual(router["model_choice_counts"]["sonnet"], 2)


if __name__ == "__main__":
    unittest.main()
