import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1b_neighbor_signals import (
    TARGET_DIAGNOSTIC_STATUS,
    TARGET_POOL_STATUS,
    leakage_check,
    phase1b_neighbor_signal_diagnostic,
    write_phase1b_neighbor_signal_diagnostic,
)


def edge(panel_id, gene, fm_call, correct, baseline_disagree=False, score=0.1):
    return {
        "edge_id": f"{panel_id}::{gene}",
        "gene": gene,
        "fm": {
            "call": fm_call,
            "correct": correct,
        },
        "baseline_signal": {
            "call_disagreement": baseline_disagree,
        },
        "reliability_signal": {
            "score": score,
        },
    }


def panel(panel_id, edges):
    return {
        "panel_id": panel_id,
        "perturbation": panel_id,
        "edges": edges,
    }


def manifest():
    return {
        "selected_panels": [
            {"panel_id": "P1"},
            {"panel_id": "P2"},
        ]
    }


def embedding_pool():
    return {
        "phase": "phase1b",
        "status": TARGET_POOL_STATUS,
        "summary": {
            "panel_count": 5,
            "matched_panel_count": 5,
            "embedding_dim": 2,
        },
        "panel_embeddings": {
            "P1": {"centroid": [0.0, 0.0]},
            "P2": {"centroid": [1.0, 0.0]},
            "P3": {"centroid": [0.1, 0.0]},
            "P4": {"centroid": [1.1, 0.0]},
            "P5": {"centroid": [3.0, 0.0]},
        },
    }


def panels():
    return [
        panel("P1", [
            edge("P1", "G1", "effect", False, baseline_disagree=True, score=0.8),
            edge("P1", "G2", "no_effect", True, baseline_disagree=False, score=0.1),
        ]),
        panel("P2", [
            edge("P2", "G1", "effect", True, baseline_disagree=False, score=0.1),
            edge("P2", "G2", "no_effect", False, baseline_disagree=True, score=0.8),
        ]),
        panel("P3", [
            edge("P3", "G1", "no_effect", False, baseline_disagree=True, score=0.7),
            edge("P3", "G2", "no_effect", True, baseline_disagree=False, score=0.1),
        ]),
        panel("P4", [
            edge("P4", "G1", "effect", True, baseline_disagree=False, score=0.1),
            edge("P4", "G2", "effect", False, baseline_disagree=True, score=0.7),
        ]),
        panel("P5", [
            edge("P5", "G1", "effect", True, baseline_disagree=False, score=0.1),
            edge("P5", "G2", "no_effect", True, baseline_disagree=False, score=0.1),
        ]),
    ]


class Phase1BNeighborSignalTests(unittest.TestCase):
    def test_neighbor_signal_diagnostic_builds_leakage_safe_edge_signals(self):
        report = phase1b_neighbor_signal_diagnostic(
            panels=panels(),
            manifest=manifest(),
            embedding_pool=embedding_pool(),
            k_neighbors=2,
            seed=7,
        )

        self.assertEqual(report["status"], TARGET_DIAGNOSTIC_STATUS)
        self.assertEqual(report["scope"]["selected_panels"], 2)
        self.assertEqual(report["scope"]["selected_edges"], 4)
        self.assertTrue(report["leakage_check"]["passed"])
        self.assertIn(
            "real_neighbor_sfm_call_disagreement_rate",
            report["edge_level_auc"],
        )
        preview_signal = report["model_visible_edge_signal_preview"][0]["edge_internal_signal_summary"]
        self.assertEqual(preview_signal["source"], "scFoundation_neighbor_edge_support")
        self.assertIn("neighbor_embedding_distance", preview_signal)
        self.assertTrue(report["full_model_visible_signal_leakage_check"]["passed"])
        self.assertEqual(len(report["model_visible_edge_signals"]), 4)
        self.assertIn(
            "random_same_gene_edge_internal_signal_summary",
            report["model_visible_edge_signals"][0],
        )
        self.assertIn(
            "shuffled_readout_gene_edge_internal_signal_summary",
            report["model_visible_edge_signals"][0],
        )
        self.assertIn(report["decision"]["decision"], {
            "eligible_for_small_llm_pilot",
            "diagnostic_only_do_not_run_llm_yet",
        })

    def test_leakage_check_catches_forbidden_keys(self):
        result = leakage_check([
            {
                "edge_internal_signal_summary": {
                    "source": "bad",
                    "truth": {"real_call": "effect"},
                }
            }
        ])

        self.assertFalse(result["passed"])
        self.assertIn("0.edge_internal_signal_summary.truth", result["forbidden_key_hits"])

    def test_write_phase1b_neighbor_signal_diagnostic_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "neighbor_signal_report.json"
            report = write_phase1b_neighbor_signal_diagnostic(
                panels=panels(),
                manifest=manifest(),
                embedding_pool=embedding_pool(),
                out=str(out),
                k_neighbors=2,
                seed=7,
            )

            self.assertTrue(out.exists())
            with open(out) as handle:
                saved = json.load(handle)
            self.assertEqual(saved["status"], report["status"])


if __name__ == "__main__":
    unittest.main()
