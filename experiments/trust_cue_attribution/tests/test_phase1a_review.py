import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1a_review import phase1a_review


def panel():
    return {
        "panel_id": "P1",
        "edges": [
            {
                "edge_id": "P1::G1",
                "gene": "G1",
                "fm": {"correct": False},
                "baseline_signal": {"correct": True, "source": "observed_additive"},
            },
            {
                "edge_id": "P1::G2",
                "gene": "G2",
                "fm": {"correct": True},
                "baseline_signal": {"correct": True, "source": "observed_additive"},
            },
        ],
    }


def packets():
    base = {
        "panel_id": "P1",
        "scoring_key": [
            {"gene": "G1", "gene_display": "G1"},
            {"gene": "G2", "gene_display": "G2"},
        ],
    }
    return [
        {**base, "packet_id": "P1::no_internal_signal", "cue_condition": "no_internal_signal"},
        {
            **base,
            "packet_id": "P1::scfoundation_internal_signal_shown",
            "cue_condition": "scfoundation_internal_signal_shown",
        },
        {
            **base,
            "packet_id": "P1::shuffled_internal_signal_shown",
            "cue_condition": "shuffled_internal_signal_shown",
        },
    ]


def episode(packet_id, g1_action, g2_action):
    return {
        "packet_id": packet_id,
        "actions": {
            "G1": {"action": g1_action},
            "G2": {"action": g2_action},
        },
    }


class Phase1AReviewTests(unittest.TestCase):
    def test_review_flags_placebo_close_to_real_as_do_not_scale(self):
        panel_signal_report = {
            "panel_signals": {
                "panels": {
                    "P1": {
                        "centroid_distance_to_control": 3.0,
                        "mean_cell_distance_to_control": 4.0,
                    }
                }
            }
        }
        review = phase1a_review(
            [panel()],
            packets(),
            [
                episode("P1::no_internal_signal", "trust_sfm", "trust_sfm"),
                episode("P1::scfoundation_internal_signal_shown", "verify_assay", "trust_sfm"),
                episode("P1::shuffled_internal_signal_shown", "verify_assay", "trust_sfm"),
            ],
            panel_signal_report,
            lam=0.5,
        )

        self.assertEqual(review["status"], "review_ready")
        self.assertEqual(review["specificity"]["real_minus_placebo_delta_net"], 0.0)
        self.assertEqual(review["recommendation"]["decision"], "do_not_scale_yet")


if __name__ == "__main__":
    unittest.main()
