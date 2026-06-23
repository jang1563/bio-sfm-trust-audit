import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1a_signal_granularity import (
    phase1a_signal_granularity,
    write_phase1a_signal_granularity,
)


def edge(gene, correct, reliability_score):
    return {
        "gene": gene,
        "fm": {"correct": correct, "log2fc": reliability_score},
        "baseline_signal": {
            "abs_fm_minus_baseline": reliability_score,
            "call_disagreement": reliability_score > 0.5,
        },
        "reliability_signal": {"score": reliability_score},
    }


def panel(panel_id, edges):
    return {"panel_id": panel_id, "edges": edges}


def manifest():
    return {
        "selected_panels": [
            {"panel_id": "P1", "wrong_rate": 0.5},
            {"panel_id": "P2", "wrong_rate": 0.5},
        ]
    }


def signal_report():
    return {
        "panel_signals": {
            "panels": {
                "P1": {
                    "centroid_distance_to_control": 1.0,
                    "mean_cell_distance_to_control": 1.0,
                    "std_cell_distance_to_control": 1.0,
                },
                "P2": {
                    "centroid_distance_to_control": 2.0,
                    "mean_cell_distance_to_control": 2.0,
                    "std_cell_distance_to_control": 2.0,
                },
            }
        }
    }


class Phase1ASignalGranularityTests(unittest.TestCase):
    def test_granularity_flags_mixed_panel_unit_mismatch(self):
        report = phase1a_signal_granularity(
            panels=[
                panel("P1", [edge("G1", False, 0.9), edge("G2", True, 0.1)]),
                panel("P2", [edge("G3", False, 0.8), edge("G4", True, 0.2)]),
            ],
            manifest=manifest(),
            panel_signal_report=signal_report(),
        )

        self.assertEqual(report["status"], "signal_granularity_ready")
        self.assertEqual(report["panel_mixture"]["mixed_panel_fraction"], 1.0)
        self.assertEqual(report["decision"]["scale_decision"], "edge_level_signal_required")
        self.assertEqual(
            report["decision"]["best_reference_edge_score_auc"]["score_field"],
            "baseline_abs_fm_minus_baseline",
        )
        self.assertGreater(report["decision"]["best_reference_edge_score_auc"]["auc"], 0.9)

    def test_write_phase1a_signal_granularity_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "granularity.json"
            report = write_phase1a_signal_granularity(
                panels=[
                    panel("P1", [edge("G1", False, 0.9), edge("G2", True, 0.1)]),
                    panel("P2", [edge("G3", False, 0.8), edge("G4", True, 0.2)]),
                ],
                manifest=manifest(),
                panel_signal_report=signal_report(),
                out=str(out),
            )

            self.assertTrue(out.exists())
            self.assertEqual(report["scope"]["edge_rows"], 4)


if __name__ == "__main__":
    unittest.main()
