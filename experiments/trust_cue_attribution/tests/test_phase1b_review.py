import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1b_review import phase1b_review


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
            "packet_id": "P1::scfoundation_edge_neighbor_signal_shown",
            "cue_condition": "scfoundation_edge_neighbor_signal_shown",
        },
        {
            **base,
            "packet_id": "P1::random_same_gene_neighbor_signal_shown",
            "cue_condition": "random_same_gene_neighbor_signal_shown",
        },
        {
            **base,
            "packet_id": "P1::shuffled_readout_gene_neighbor_signal_shown",
            "cue_condition": "shuffled_readout_gene_neighbor_signal_shown",
        },
    ]


def episode(packet_id, cue, g1_action, g2_action):
    return {
        "packet_id": packet_id,
        "cue_condition": cue,
        "actions": {
            "G1": {"action": g1_action},
            "G2": {"action": g2_action},
        },
    }


def neighbor_report():
    signal = {
        "neighbor_count": 10,
        "same_readout_gene_neighbor_count": 12,
        "neighbor_baseline_disagreement_rate": 0.8,
        "neighbor_sfm_call_agreement_rate": 0.2,
        "neighbor_sfm_call_disagreement_rate": 0.8,
        "neighbor_embedding_distance": {"min": 1.0, "mean": 2.0, "max": 3.0},
    }
    return {
        "model_visible_edge_signals": [
            {
                "panel_id": "P1",
                "gene_display": gene,
                "real_edge_internal_signal_summary": signal,
                "random_same_gene_edge_internal_signal_summary": signal,
                "shuffled_readout_gene_edge_internal_signal_summary": signal,
            }
            for gene in ["G1", "G2"]
        ]
    }


class Phase1BReviewTests(unittest.TestCase):
    def test_review_blocks_scaling_when_real_signal_lowers_reward(self):
        episodes = [
            episode("P1::no_internal_signal", "no_internal_signal", "verify_assay", "trust_sfm"),
            episode(
                "P1::scfoundation_edge_neighbor_signal_shown",
                "scfoundation_edge_neighbor_signal_shown",
                "trust_sfm",
                "trust_sfm",
            ),
            episode(
                "P1::random_same_gene_neighbor_signal_shown",
                "random_same_gene_neighbor_signal_shown",
                "verify_assay",
                "trust_sfm",
            ),
            episode(
                "P1::shuffled_readout_gene_neighbor_signal_shown",
                "shuffled_readout_gene_neighbor_signal_shown",
                "verify_assay",
                "default_baseline",
            ),
        ]
        review = phase1b_review([panel()], packets(), episodes, neighbor_report(), lam=0.5)

        self.assertEqual(review["status"], "review_ready")
        self.assertLess(review["specificity"]["real_delta_net"], 0)
        self.assertEqual(
            review["recommendation"]["decision"],
            "do_not_scale_larger_llm_matrix",
        )
        self.assertEqual(
            review["recommendation"]["reason"],
            "real_signal_reduced_net_reward_vs_no_signal",
        )


if __name__ == "__main__":
    unittest.main()
