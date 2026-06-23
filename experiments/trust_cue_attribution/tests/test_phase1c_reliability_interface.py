import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1c_reliability_interface import (
    COMBINED_WEIGHTS,
    PHASE1C_INTERFACE_CUES,
    REAL_SIGNAL_KEY,
    attach_signal_records,
    edge_signal_map,
    generate_phase1c_interface_packets,
    phase1c_offline_gate,
    phase1c_interface_manifest,
    reliability_card,
    select_signal_matched_panels,
)


def panel():
    return {
        "panel_id": "P1",
        "perturbation": "PERT1",
        "edges": [
            {
                "edge_id": "P1::G1",
                "gene": "G1",
                "fm": {"correct": False, "log2fc": 0.26, "call": "effect"},
                "baseline_signal": {
                    "correct": True,
                    "call_disagreement": True,
                    "abs_fm_minus_baseline": 0.8,
                    "source": "observed_additive",
                },
                "reliability_signal": {"score": 0.9},
            },
            {
                "edge_id": "P1::G2",
                "gene": "G2",
                "fm": {"correct": True, "log2fc": 1.2, "call": "effect"},
                "baseline_signal": {
                    "correct": True,
                    "call_disagreement": False,
                    "abs_fm_minus_baseline": 0.1,
                    "source": "observed_additive",
                },
                "reliability_signal": {"score": 0.1},
            },
        ],
    }


def neighbor_report():
    def signal(rate):
        return {
            "neighbor_sfm_call_disagreement_rate": rate,
            "neighbor_sfm_call_agreement_rate": 1.0 - rate,
            "neighbor_count": 10,
            "same_readout_gene_neighbor_count": 10,
        }

    return {
        "model_visible_edge_signals": [
            {
                "panel_id": "P1",
                "gene_display": "G1",
                "real_edge_internal_signal_summary": signal(0.8),
                "random_same_gene_edge_internal_signal_summary": signal(0.2),
                "shuffled_readout_gene_edge_internal_signal_summary": signal(0.1),
            },
            {
                "panel_id": "P1",
                "gene_display": "G2",
                "real_edge_internal_signal_summary": signal(0.0),
                "random_same_gene_edge_internal_signal_summary": signal(0.0),
                "shuffled_readout_gene_edge_internal_signal_summary": signal(0.7),
            },
        ]
    }


def phase1b_summary():
    row = {
        "accuracy": 0.5,
        "assays_per_gene": 0.2,
        "net_reward_per_gene_lambda_0.5": 0.4,
        "trust_error_rate": 0.1,
    }
    return {
        "by_cue_condition_lambda_0.5": {
            "no_internal_signal": row,
            "scfoundation_edge_neighbor_signal_shown": row,
            "random_same_gene_neighbor_signal_shown": row,
            "shuffled_readout_gene_neighbor_signal_shown": row,
        }
    }


def eligible_gate():
    return {"decision": {"decision": "eligible_for_small_phase1c_interface_pilot"}}


class Phase1CInterfaceTests(unittest.TestCase):
    def test_select_signal_matched_panels_filters_to_available_edges(self):
        signals = edge_signal_map(neighbor_report())
        selected = select_signal_matched_panels([panel()], signals)

        self.assertEqual(len(selected), 1)
        self.assertEqual([edge["gene"] for edge in selected[0]["edges"]], ["G1", "G2"])

    def test_reliability_card_recommends_default_for_high_risk_disagreement(self):
        signals = edge_signal_map(neighbor_report())
        selected = attach_signal_records([panel()], signals)
        edge = selected[0]["edges"][0]
        card = reliability_card(
            panel_id="P1",
            edge=edge,
            weights=COMBINED_WEIGHTS,
            signal_key=REAL_SIGNAL_KEY,
        )

        self.assertEqual(card["recommended_action"], "default_baseline")
        self.assertIn(card["risk_bucket"], {"medium", "high"})
        self.assertIn("sfm_margin_risk", card["evidence_basis"])

    def test_offline_gate_returns_policy_scores_and_decision(self):
        gate = phase1c_offline_gate([panel()], neighbor_report(), phase1b_summary())

        self.assertEqual(gate["status"], "offline_gate_ready")
        self.assertEqual(gate["scope"]["edges"], 2)
        self.assertIn("combined_real_reliability_interface", gate["policy_scores"]["0.5"])
        self.assertIn("decision", gate["decision"])

    def test_phase1c_interface_packets_have_balanced_cues(self):
        packets = generate_phase1c_interface_packets([panel()], neighbor_report(), eligible_gate())

        self.assertEqual(len(packets), len(PHASE1C_INTERFACE_CUES))
        self.assertEqual(
            sorted(packet["cue_condition"] for packet in packets),
            sorted(PHASE1C_INTERFACE_CUES),
        )
        by_cue = {packet["cue_condition"]: packet for packet in packets}
        base_gene = by_cue["no_internal_signal"]["evidence_packet"]["genes"][0]
        signal_gene = by_cue["edge_neighbor_signal_shown"]["evidence_packet"]["genes"][0]
        calibrated_gene = by_cue["calibrated_reliability_interface_shown"]["evidence_packet"]["genes"][0]
        inverted_gene = by_cue["inverted_reliability_interface_control"]["evidence_packet"]["genes"][0]

        self.assertNotIn("edge_internal_signal_summary", base_gene)
        self.assertIn("edge_internal_signal_summary", signal_gene)
        self.assertIn("reliability_interface", calibrated_gene)
        self.assertEqual(calibrated_gene["reliability_interface"]["recommended_action"], "default_baseline")
        self.assertIn("control_note", inverted_gene["reliability_interface"])

    def test_phase1c_interface_manifest_summarizes_requests(self):
        packets = generate_phase1c_interface_packets([panel()], neighbor_report(), eligible_gate())
        requests = [{"packet_id": packet["packet_id"], "prompt": "stub"} for packet in packets]
        manifest = phase1c_interface_manifest(
            packets=packets,
            requests=requests,
            neighbor_report="missing_neighbor_report.json",
            offline_gate="missing_offline_gate.json",
            packet_out="packets.jsonl",
            request_out="requests.jsonl",
        )

        self.assertEqual(manifest["status"], "interface_request_pilot_ready")
        self.assertEqual(manifest["n_panels"], 1)
        self.assertEqual(manifest["n_requests"], len(PHASE1C_INTERFACE_CUES))
        self.assertTrue(manifest["model_visible_leakage_check"]["passed"])


if __name__ == "__main__":
    unittest.main()
