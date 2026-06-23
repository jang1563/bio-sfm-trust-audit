import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1b_neighbor_signals import TARGET_DIAGNOSTIC_STATUS
from phase1b_signal_packets import (
    PHASE1B_SIGNAL_CUES,
    generate_phase1b_signal_packets,
    load_phase1b_edge_signals,
    phase1b_signal_packet,
    write_phase1b_signal_packets,
)


def summary(source, gene):
    return {
        "source": source,
        "adapter": "ScFoundationAdapter",
        "signal_scope": "readout_gene_specific",
        "readout_gene_display": gene,
        "neighbor_count": 2,
        "same_readout_gene_neighbor_count": 3,
        "neighbor_embedding_distance": {
            "mean": 1.2,
            "min": 0.7,
            "max": 1.9,
        },
        "neighbor_sfm_call_agreement_rate": 0.5,
        "neighbor_sfm_call_disagreement_rate": 0.5,
        "neighbor_baseline_disagreement_rate": 0.25,
        "calibration_status": "unverified_proxy_not_calibrated",
        "limitations": [
            "not_a_calibrated_uncertainty",
            "does_not_contain_hidden_labels",
        ],
    }


def report():
    return {
        "phase": "phase1b",
        "status": TARGET_DIAGNOSTIC_STATUS,
        "decision": {"decision": "eligible_for_small_llm_pilot"},
        "model_visible_edge_signals": [
            {
                "panel_id": "P1",
                "gene_display": "G1",
                "real_edge_internal_signal_summary": summary("scFoundation_neighbor_edge_support", "G1"),
                "random_same_gene_edge_internal_signal_summary": summary("random_same_readout_gene_neighbor_control", "G1"),
                "shuffled_readout_gene_edge_internal_signal_summary": summary("shuffled_readout_gene_neighbor_control", "G1"),
            },
            {
                "panel_id": "P1",
                "gene_display": "G2",
                "real_edge_internal_signal_summary": summary("scFoundation_neighbor_edge_support", "G2"),
                "random_same_gene_edge_internal_signal_summary": summary("random_same_readout_gene_neighbor_control", "G2"),
                "shuffled_readout_gene_edge_internal_signal_summary": summary("shuffled_readout_gene_neighbor_control", "G2"),
            },
        ],
    }


def panels():
    return [
        {
            "panel_id": "P1",
            "perturbation": "P1",
            "edges": [
                {
                    "edge_id": "P1::G1",
                    "gene": "G1",
                    "fm": {"call": "effect", "log2fc": 0.4},
                },
                {
                    "edge_id": "P1::G2",
                    "gene": "G2",
                    "fm": {"call": "no_effect", "log2fc": 0.1},
                },
            ],
        },
        {
            "panel_id": "P2",
            "perturbation": "P2",
            "edges": [
                {
                    "edge_id": "P2::G1",
                    "gene": "G1",
                    "fm": {"call": "effect", "log2fc": 0.3},
                },
            ],
        },
    ]


class Phase1BSignalPacketTests(unittest.TestCase):
    def test_load_phase1b_edge_signals_requires_eligible_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            with open(path, "w") as handle:
                json.dump(report(), handle)

            signals = load_phase1b_edge_signals(str(path))

            self.assertIn(("P1", "G1"), signals)
            self.assertIn("real_edge_internal_signal_summary", signals[("P1", "G1")])

    def test_generate_phase1b_signal_packets_balances_four_conditions(self):
        signals = {
            (record["panel_id"], record["gene_display"]): {
                "real_edge_internal_signal_summary": record["real_edge_internal_signal_summary"],
                "random_same_gene_edge_internal_signal_summary": record["random_same_gene_edge_internal_signal_summary"],
                "shuffled_readout_gene_edge_internal_signal_summary": record["shuffled_readout_gene_edge_internal_signal_summary"],
            }
            for record in report()["model_visible_edge_signals"]
        }

        packets = generate_phase1b_signal_packets(panels(), signals)

        self.assertEqual(len(packets), len(PHASE1B_SIGNAL_CUES))
        self.assertEqual({packet["panel_id"] for packet in packets}, {"P1"})
        with_signal = [
            packet for packet in packets
            if packet["cue_condition"] == "scfoundation_edge_neighbor_signal_shown"
        ][0]
        self.assertIn("edge_internal_signal_summary", with_signal["evidence_packet"]["genes"][0])
        no_signal = [
            packet for packet in packets
            if packet["cue_condition"] == "no_internal_signal"
        ][0]
        self.assertNotIn("edge_internal_signal_summary", no_signal["evidence_packet"]["genes"][0])

    def test_phase1b_signal_packet_rejects_missing_signal(self):
        with self.assertRaises(KeyError):
            phase1b_signal_packet(
                panels()[0],
                "scfoundation_edge_neighbor_signal_shown",
                {},
            )

    def test_write_phase1b_signal_packets_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_path = Path(tmp) / "neighbor_report.json"
            out = Path(tmp) / "packets.jsonl"
            manifest_out = Path(tmp) / "manifest.json"
            with open(report_path, "w") as handle:
                json.dump(report(), handle)

            manifest = write_phase1b_signal_packets(
                panels=panels(),
                neighbor_report=str(report_path),
                out=str(out),
                manifest_out=str(manifest_out),
            )

            self.assertTrue(out.exists())
            self.assertTrue(manifest_out.exists())
            self.assertEqual(manifest["status"], "signal_packet_pilot_ready")
            self.assertEqual(manifest["n_packets"], len(PHASE1B_SIGNAL_CUES))
            self.assertTrue(manifest["model_visible_leakage_check"]["passed"])


if __name__ == "__main__":
    unittest.main()
