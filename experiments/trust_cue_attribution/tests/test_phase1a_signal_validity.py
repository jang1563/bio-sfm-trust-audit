import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1a_signal_validity import (
    phase1a_signal_validity,
    selected_panels_from_manifest,
    write_phase1a_signal_validity,
)


def panel(panel_id, wrong_rate, additive_disagreement_rate=0.0):
    return {
        "panel_id": panel_id,
        "wrong_rate": wrong_rate,
        "additive_disagreement_rate": additive_disagreement_rate,
        "high_risk_rate": additive_disagreement_rate,
        "mean_reliability_score": additive_disagreement_rate,
        "additive_coverage_rate": 1.0,
        "wrong_rate_bin": "test",
    }


def signal_report(distances):
    return {
        "panel_signals": {
            "panels": {
                panel_id: {
                    "status": "ready",
                    "centroid_distance_to_control": distance,
                    "mean_cell_distance_to_control": distance + 0.5,
                    "std_cell_distance_to_control": 1.0,
                    "centroid_l2_norm": 10.0 + distance,
                    "mean_cell_l2_norm": 20.0 + distance,
                    "std_cell_l2_norm": 0.1,
                }
                for panel_id, distance in distances.items()
            }
        }
    }


class Phase1ASignalValidityTests(unittest.TestCase):
    def test_validity_detects_promising_positive_panel_signal(self):
        panels = [
            panel(f"P{i}", i / 10)
            for i in range(1, 9)
        ]
        report = phase1a_signal_validity(
            panels,
            signal_report({f"P{i}": float(i) for i in range(1, 9)}),
        )

        self.assertEqual(report["status"], "signal_validity_ready")
        self.assertEqual(report["scope"]["matched_panels"], 8)
        self.assertEqual(report["decision"]["scale_decision"], "promising_but_small_n")
        self.assertGreater(
            report["strongest_by_target"]["wrong_rate"]["strongest_primary_signal"]["correlation"],
            0.9,
        )

    def test_validity_flags_opposite_direction(self):
        panels = [
            panel(f"P{i}", i / 10)
            for i in range(1, 9)
        ]
        report = phase1a_signal_validity(
            panels,
            signal_report({f"P{i}": float(9 - i) for i in range(1, 9)}),
        )

        self.assertEqual(report["decision"]["scale_decision"], "redesign_before_scaling")
        self.assertEqual(
            report["decision"]["reason"],
            "primary_signal_points_opposite_expected_direction",
        )

    def test_selected_panels_from_manifest_accepts_legacy_key(self):
        self.assertEqual(
            selected_panels_from_manifest({"panels": [panel("P1", 0.1)]})[0]["panel_id"],
            "P1",
        )

    def test_write_phase1a_signal_validity_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "validity.json"
            report = write_phase1a_signal_validity(
                selected_panels=[panel("P1", 0.1), panel("P2", 0.3), panel("P3", 0.5)],
                panel_signal_report=signal_report({"P1": 1.0, "P2": 2.0, "P3": 3.0}),
                out=str(out),
            )

            self.assertTrue(out.exists())
            self.assertEqual(report["scope"]["matched_panels"], 3)


if __name__ == "__main__":
    unittest.main()
