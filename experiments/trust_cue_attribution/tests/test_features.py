import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from features import feature_signature, observation_features, trajectory_feature_rows


class FeatureTests(unittest.TestCase):
    def test_observation_features_use_visible_packet_fields(self):
        observation = {
            "packet_id": "P::add",
            "panel_id": "P",
            "cue_condition": "additive_disagreement_shown",
            "evidence_packet": {
                "model_card": {"display_name": "specialist model A", "adapter": "hidden"},
                "genes": [
                    {
                        "gene_display": "G1",
                        "sfm_call": "effect",
                        "sfm_log2fc": 0.8,
                        "baseline_signal": {
                            "source": "observed_additive",
                            "baseline_call": "no_effect",
                            "baseline_log2fc": 0.0,
                            "abs_fm_minus_baseline": 0.8,
                            "call_disagreement": True,
                        },
                    },
                    {
                        "gene_display": "G2",
                        "sfm_call": "no_effect",
                        "sfm_log2fc": 0.1,
                        "baseline_signal": {
                            "source": "no_change",
                            "baseline_call": "no_effect",
                            "baseline_log2fc": 0.0,
                            "abs_fm_minus_baseline": 0.1,
                            "call_disagreement": False,
                        },
                    },
                ],
            },
        }
        features = observation_features(observation)

        self.assertEqual(features["n_genes"], 2)
        self.assertEqual(features["sfm_effect_rate"], 0.5)
        self.assertEqual(features["baseline_present_rate"], 1.0)
        self.assertEqual(features["baseline_call_disagreement_rate"], 0.5)
        self.assertEqual(features["baseline_observed_additive_rate"], 0.5)
        self.assertIn("baseline=", feature_signature(features))
        self.assertNotIn("correct", features)

    def test_observation_features_include_internal_signal_visibility(self):
        observation = {
            "packet_id": "P::scf",
            "panel_id": "P",
            "cue_condition": "scfoundation_internal_signal_shown",
            "evidence_packet": {
                "model_card": {"display_name": "specialist model A", "adapter": "hidden"},
                "genes": [{"gene_display": "G1", "sfm_call": "effect", "sfm_log2fc": 0.4}],
                "internal_signal_summary": {
                    "signal_scope": "global_three_cell_smoke_subset_not_panel_specific",
                    "embedding_dim": 3072,
                    "embedding_finite_fraction": 1.0,
                },
            },
        }
        features = observation_features(observation)

        self.assertEqual(features["internal_signal_present"], 1)
        self.assertEqual(features["internal_signal_embedding_dim"], 3072)
        self.assertEqual(features["internal_signal_finite_fraction"], 1.0)
        self.assertEqual(features["internal_signal_scope"], "global_three_cell_smoke_subset_not_panel_specific")
        self.assertIn("internal_signal=yes", feature_signature(features))

    def test_trajectory_feature_rows_include_reward_metadata_and_signature(self):
        rows = trajectory_feature_rows([
            {
                "trajectory_id": "T1",
                "model": "m1",
                "reward": 1.0,
                "reward_per_gene": 0.5,
                "score": {"n": 2},
                "observation": {
                    "packet_id": "P::no",
                    "panel_id": "P",
                    "cue_condition": "no_cue",
                    "evidence_packet": {"model_card": {"adapter": "hidden"}, "genes": []},
                },
            }
        ])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["model"], "m1")
        self.assertEqual(rows[0]["reward"], 1.0)
        self.assertIn("cue=no_cue", rows[0]["feature_signature"])


if __name__ == "__main__":
    unittest.main()
