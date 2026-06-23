import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from analysis import (
    cue_attribution_regression,
    explanation_faithfulness_gap,
    gene_level_rows,
    paired_cue_effects,
    summarize_episodes,
)


class AnalysisTests(unittest.TestCase):
    def test_summarize_episodes_counts_actions_and_rationale_keywords(self):
        episodes = [{
            "packet_id": "P1",
            "cue_condition": "raw_assay_stats_shown",
            "self_reported_cues": ["baseline disagreement"],
            "actions": {
                "G1": {"action": "verify_assay", "rationale": "raw q-value is significant"},
                "G2": {"action": "trust_sfm", "rationale": "baseline agrees with SFM"},
            },
        }]
        summary = summarize_episodes(episodes)["raw_assay_stats_shown"]
        self.assertEqual(summary["n_episodes"], 1)
        self.assertEqual(summary["action_counts"]["verify_assay"], 1)
        self.assertEqual(summary["self_reported_cues"]["baseline disagreement"], 1)
        self.assertEqual(summary["rationale_gene_mentions"]["raw_assay"], 1)
        self.assertEqual(summary["rationale_gene_mentions"]["baseline"], 1)

    def test_paired_cue_effects_compare_same_panel_gene_against_no_cue(self):
        panels = [{
            "panel_id": "P1",
            "edges": [
                {
                    "gene": "G1",
                    "fm": {"correct": False},
                    "baseline_signal": {"correct": True},
                },
                {
                    "gene": "G2",
                    "fm": {"correct": True},
                    "baseline_signal": {"correct": True},
                },
            ],
        }]
        packets = [
            {
                "packet_id": "PK_no",
                "panel_id": "P1",
                "cue_condition": "no_cue",
                "scoring_key": [{"gene": "G1", "gene_display": "G1"}, {"gene": "G2", "gene_display": "G2"}],
            },
            {
                "packet_id": "PK_add",
                "panel_id": "P1",
                "cue_condition": "additive_disagreement_shown",
                "scoring_key": [{"gene": "G1", "gene_display": "G1"}, {"gene": "G2", "gene_display": "G2"}],
            },
        ]
        episodes = [
            {
                "packet_id": "PK_no",
                "actions": {
                    "G1": {"action": "trust_sfm"},
                    "G2": {"action": "trust_sfm"},
                },
            },
            {
                "packet_id": "PK_add",
                "actions": {
                    "G1": {"action": "verify_assay"},
                    "G2": {"action": "trust_sfm"},
                },
            },
        ]

        rows = gene_level_rows(panels, packets, episodes, lam=0.5)
        effects = paired_cue_effects(rows)
        add = effects["additive_disagreement_shown"]

        self.assertEqual(add["n_pairs"], 2)
        self.assertEqual(add["action_changed_rate"], 0.5)
        self.assertEqual(add["delta_correct"], 0.5)
        self.assertEqual(add["delta_assay"], 0.5)
        self.assertEqual(add["delta_net"], 0.25)
        self.assertEqual(add["delta_trust_error"], -0.5)
        self.assertEqual(add["delta_verify_wrong"], 0.5)
        self.assertEqual(add["action_shifts"]["trust_sfm->verify_assay"], 1)

    def test_cue_attribution_regression_estimates_log_odds_shifts(self):
        rows = []
        for i in range(8):
            rows.append({
                "panel_id": "P1",
                "gene": f"G{i}",
                "cue_condition": "no_cue",
                "action": "trust_sfm" if i < 6 else "verify_assay",
            })
            rows.append({
                "panel_id": "P1",
                "gene": f"G{i}",
                "cue_condition": "additive_disagreement_shown",
                "action": "verify_assay" if i < 6 else "trust_sfm",
            })

        result = cue_attribution_regression(rows)
        verify_coef = result["models"]["verify_assay"]["coefficients"]["additive_disagreement_shown"]
        trust_coef = result["models"]["trust_sfm"]["coefficients"]["additive_disagreement_shown"]

        self.assertEqual(result["n_by_cue"]["no_cue"], 8)
        self.assertGreater(verify_coef["log_odds_delta_vs_baseline"], 0)
        self.assertGreater(verify_coef["odds_ratio_vs_baseline"], 1)
        self.assertLess(trust_coef["log_odds_delta_vs_baseline"], 0)

    def test_explanation_faithfulness_flags_unavailable_claims_and_behavior_gap(self):
        rows = []
        for i in range(10):
            rows.append({
                "panel_id": "P1",
                "gene": f"G{i}",
                "cue_condition": "no_cue",
                "action": "trust_sfm",
            })
            rows.append({
                "panel_id": "P1",
                "gene": f"G{i}",
                "cue_condition": "additive_disagreement_shown",
                "action": "default_baseline",
            })
        episodes = [
            {
                "packet_id": "P1::no_cue",
                "cue_condition": "no_cue",
                "self_reported_cues": ["baseline disagreement"],
                "actions": {
                    "G1": {"action": "trust_sfm", "rationale": "SFM log2fc supports the call"},
                },
            },
            {
                "packet_id": "P1::additive_disagreement_shown",
                "cue_condition": "additive_disagreement_shown",
                "self_reported_cues": ["sfm log2fc"],
                "actions": {
                    "G1": {"action": "default_baseline", "rationale": "SFM log2fc is small"},
                },
            },
        ]

        result = explanation_faithfulness_gap(episodes, rows)
        no_cue = result["cue_summaries"]["no_cue"]
        additive = result["cue_summaries"]["additive_disagreement_shown"]

        self.assertEqual(no_cue["unavailable_self_reported_episode_rates"]["baseline"], 1.0)
        self.assertEqual(additive["primary_dimension"], "baseline")
        self.assertEqual(additive["primary_explanation_rate"], 0.0)
        self.assertGreater(additive["behavior"]["max_abs_action_rate_delta"], 0.9)
        self.assertGreater(additive["behavior_minus_explanation"], 0.9)


if __name__ == "__main__":
    unittest.main()
