import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from baselines import run_baselines
from cues import CUE_CONDITIONS, generate_cue_packets
from episodes import make_policy_episode_records, make_request_records, normalize_episode_actions, score_episode_record, score_episode_records
from panels import PanelConfig, build_panels_from_rows
from scoring import action_net_reward, score_actions, summarize_scores


def synthetic_rows():
    rows = []
    for p in ("A+B", "C+D"):
        for i in range(20):
            real_effect = i % 2 == 0
            fm_wrong = i % 5 in (0, 1)
            if real_effect:
                fm_call = "no_effect" if fm_wrong else "effect"
            else:
                fm_call = "effect" if fm_wrong else "no_effect"
            rows.append({
                "perturbation": p,
                "gene": f"G{i}",
                "fm_log2FC": "0.8" if fm_call == "effect" else "0.05",
                "fm_call": fm_call,
                "real_label": "POSITIVE" if real_effect else "TESTED_NEGATIVE",
                "regime": "combo_seen2",
                "raw_log2FC": "0.7" if real_effect else "0.0",
                "raw_se": "0.1",
                "raw_q": "0.01",
                "n_trt": "100",
                "n_cntrl": "200",
            })
    return rows


def single_effects():
    out = {}
    for pert in ("A", "B", "C", "D"):
        for i in range(20):
            # Additive baseline deliberately matches truth more often than the FM.
            out[(pert, f"G{i}")] = 0.4 if i % 2 == 0 else 0.0
    return out


class PanelCueScoringTests(unittest.TestCase):
    def test_build_panels_deterministic(self):
        cfg = PanelConfig(n=12, min_wrong=3, min_correct=3, seed=7)
        a = build_panels_from_rows(synthetic_rows(), single_effects(), cfg)
        b = build_panels_from_rows(synthetic_rows(), single_effects(), cfg)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 2)
        self.assertTrue(all(p["n_panel"] == 12 for p in a))
        self.assertTrue(all("baseline_signal" in e for p in a for e in p["edges"]))

    def test_require_additive_filters_single_edges(self):
        rows = synthetic_rows()
        rows.append({
            "perturbation": "A",
            "gene": "G0",
            "fm_log2FC": "0.8",
            "fm_call": "effect",
            "real_label": "POSITIVE",
            "regime": "single_seen",
            "raw_log2FC": "0.8",
            "raw_se": "0.1",
            "raw_q": "0.01",
            "n_trt": "100",
            "n_cntrl": "200",
        })
        panels = build_panels_from_rows(rows, single_effects(), PanelConfig(n=10, min_wrong=3, min_correct=3, require_additive=True))
        self.assertTrue(panels)
        self.assertTrue(all(e["baseline_signal"]["source"] == "observed_additive" for p in panels for e in p["edges"]))

    def test_cue_packets_are_balanced(self):
        panels = build_panels_from_rows(synthetic_rows(), single_effects(), PanelConfig(n=10, min_wrong=3, min_correct=3))
        packets = generate_cue_packets(panels)
        self.assertEqual(len(packets), len(panels) * len(CUE_CONDITIONS))
        self.assertEqual({p["cue_condition"] for p in packets}, set(CUE_CONDITIONS))
        self.assertTrue(all("scoring_key" in p for p in packets))

    def test_raw_assay_stats_are_positive_control_only(self):
        panel = build_panels_from_rows(synthetic_rows(), single_effects(), PanelConfig(n=10, min_wrong=3, min_correct=3))[0]
        packets = {p["cue_condition"]: p for p in generate_cue_packets([panel])}
        self.assertNotIn("assay_stats", packets["no_cue"]["evidence_packet"]["genes"][0])
        assay_gene = packets["raw_assay_stats_shown"]["evidence_packet"]["genes"][0]
        self.assertIn("assay_stats", assay_gene)
        self.assertEqual(assay_gene["assay_stats"]["source"], "heldout_measured_de_positive_control")

    def test_confidence_cue_marks_proxy_source(self):
        panel = build_panels_from_rows(synthetic_rows(), single_effects(), PanelConfig(n=10, min_wrong=3, min_correct=3))[0]
        packet = [p for p in generate_cue_packets([panel]) if p["cue_condition"] == "confidence_shown"][0]
        gene = packet["evidence_packet"]["genes"][0]
        self.assertIn("sfm_confidence", gene)
        self.assertEqual(gene["sfm_confidence_source"], "magnitude_proxy_not_calibrated")

    def test_anonymized_episode_actions_map_back_to_true_genes(self):
        panel = build_panels_from_rows(synthetic_rows(), single_effects(), PanelConfig(n=10, min_wrong=3, min_correct=3))[0]
        packet = [p for p in generate_cue_packets([panel]) if p["cue_condition"] == "anonymized_genes"][0]
        display = packet["scoring_key"][0]["gene_display"]
        true_gene = packet["scoring_key"][0]["gene"]
        episode = {"packet_id": packet["packet_id"], "actions": {display: {"action": "verify"}}}
        actions = normalize_episode_actions(packet, episode)
        self.assertEqual(actions[true_gene], "verify_assay")
        score = score_episode_record(panel, packet, episode, lam=0.5)
        self.assertEqual(score["packet_id"], packet["packet_id"])

    def test_make_request_records_renders_prompt(self):
        panel = build_panels_from_rows(synthetic_rows(), single_effects(), PanelConfig(n=10, min_wrong=3, min_correct=3))[0]
        packet = generate_cue_packets([panel])[0]
        records = make_request_records([packet], "Evidence:\n{{EVIDENCE_PACKET_JSON}}\n", model="test-model")
        self.assertEqual(records[0]["model"], "test-model")
        self.assertIn("Evidence:", records[0]["prompt"])
        self.assertIn("genes", records[0]["prompt"])

    def test_policy_episode_records_round_trip_through_scorer(self):
        panels = build_panels_from_rows(synthetic_rows(), single_effects(), PanelConfig(n=10, min_wrong=3, min_correct=3))
        packets = generate_cue_packets(panels)
        episodes = make_policy_episode_records(panels, packets, "always_additive")
        result = score_episode_records(panels, packets, episodes, lam=0.5)
        self.assertEqual(len(result["rows"]), len(packets))
        self.assertGreaterEqual(result["summary"]["accuracy"], 0.5)

    def test_scoring_actions(self):
        panel = build_panels_from_rows(synthetic_rows(), single_effects(), PanelConfig(n=10, min_wrong=3, min_correct=3))[0]
        actions = {e["gene"]: "verify_assay" for e in panel["edges"]}
        score = score_actions(panel, actions, lam=0.5)
        self.assertEqual(score["accuracy"], 1.0)
        self.assertEqual(score["assays_per_gene"], 1.0)
        self.assertEqual(score["defer_rate"], 0.0)
        self.assertEqual(score["coverage_rate"], 1.0)

    def test_summarize_scores_reports_micro_and_macro_metrics(self):
        def edge(gene: str, fm_correct: bool = False) -> dict:
            return {
                "gene": gene,
                "fm": {"correct": fm_correct},
                "baseline_signal": {"correct": True, "source": "observed_additive"},
            }

        small = {"panel_id": "small", "edges": [edge("G1")]}
        large = {"panel_id": "large", "edges": [edge("G2"), edge("G3"), edge("G4")]}
        rows = [
            score_actions(small, {"G1": "verify_assay"}, lam=0.5),
            score_actions(large, {"G2": "trust_sfm", "G3": "trust_sfm", "G4": "trust_sfm"}, lam=0.5),
        ]
        summary = summarize_scores(rows)

        self.assertEqual(summary["n_panels"], 2)
        self.assertEqual(summary["n_genes"], 4)
        self.assertEqual(summary["accuracy"], 0.25)
        self.assertEqual(summary["macro_panel_accuracy"], 0.5)
        self.assertEqual(summary["assays_per_gene"], 0.25)
        self.assertEqual(summary["verify_recall"], 0.25)

    def test_defer_penalty_is_optional_and_visible(self):
        edge = {
            "gene": "G1",
            "fm": {"correct": False},
            "baseline_signal": {"correct": True, "source": "observed_additive"},
        }
        panel = {"panel_id": "P", "edges": [edge]}
        score = score_actions(panel, {}, lam=0.5, defer_penalty=0.2)

        self.assertEqual(action_net_reward(edge, "defer", lam=0.5, defer_penalty=0.2), -0.2)
        self.assertEqual(score["defer_rate"], 1.0)
        self.assertEqual(score["coverage_rate"], 0.0)
        self.assertEqual(score["net_reward_per_gene"], -0.2)

    def test_default_baseline_source_breakdown_is_reported(self):
        panel = {
            "panel_id": "P",
            "edges": [
                {"gene": "G1", "fm": {"correct": False}, "baseline_signal": {"correct": True, "source": "observed_additive"}},
                {"gene": "G2", "fm": {"correct": False}, "baseline_signal": {"correct": False, "source": "no_change"}},
            ],
        }
        score = score_actions(panel, {"G1": "default_baseline", "G2": "default_baseline"}, lam=0.5)

        self.assertEqual(score["default_baseline_rate"], 1.0)
        self.assertEqual(score["default_observed_additive_rate"], 0.5)
        self.assertEqual(score["default_no_change_rate"], 0.5)
        self.assertEqual(score["default_error_rate"], 0.5)

    def test_baselines_include_required_policies(self):
        panels = build_panels_from_rows(synthetic_rows(), single_effects(), PanelConfig(n=10, min_wrong=3, min_correct=3))
        res = run_baselines(panels, seed=0)
        policies = set(res["0.5"])
        self.assertTrue({
            "trust_all_sfm",
            "verify_all",
            "random_verify_at_budget",
            "oracle_verify",
            "always_additive",
            "signal_gated_verify",
        } <= policies)
        self.assertGreater(res["0.5"]["oracle_verify"]["accuracy"], res["0.5"]["trust_all_sfm"]["accuracy"])
        self.assertGreaterEqual(res["0.5"]["always_additive"]["accuracy"], res["0.5"]["trust_all_sfm"]["accuracy"])


if __name__ == "__main__":
    unittest.main()
