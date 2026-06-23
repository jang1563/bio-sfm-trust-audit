import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1a_signal_packets import (
    PHASE1A_SIGNAL_CUES,
    generate_phase1a_signal_packets,
    load_panel_specific_internal_signals,
    load_scfoundation_smoke_signal,
    phase1a_signal_packet,
    shuffled_internal_signal,
    write_phase1a_signal_packets,
)


def smoke_report():
    return {
        "adapter": "ScFoundationAdapter",
        "status": "ready_for_internal_signal_summary_adapter",
        "embedding_summary": {
            "shape": [3, 3072],
            "dtype": "float32",
            "finite_fraction": 1.0,
            "mean": 0.0694971457,
            "std": 1.0816756487,
            "l2_norm": 104.0549621582,
        },
        "subset": {
            "source_shape": [19464, 834],
            "subset_shape": [3, 834],
        },
        "process": {
            "stdout_tail": [
                "covert gene feature into 19264",
                "(3, 19264)",
                "(3, 3072)",
            ],
        },
    }


def panel(panel_id="A+B"):
    return {
        "panel_id": panel_id,
        "perturbation": panel_id,
        "adapter": "GEARSAdapter",
        "edges": [
            {
                "edge_id": f"{panel_id}::G1",
                "gene": "G1",
                "fm": {"call": "effect", "log2fc": 0.8, "correct": False},
                "truth": {"real_call": "no_effect"},
                "baseline_signal": {"source": "observed_additive", "call_disagreement": True},
                "reliability_signal": {"score": 0.9, "label": "high_sfm_error_risk"},
            },
            {
                "edge_id": f"{panel_id}::G2",
                "gene": "G2",
                "fm": {"call": "no_effect", "log2fc": 0.02, "correct": True},
                "truth": {"real_call": "no_effect"},
                "baseline_signal": {"source": "observed_additive", "call_disagreement": False},
                "reliability_signal": {"score": 0.1, "label": "low_sfm_error_risk"},
            },
        ],
    }


def panel_signal_report():
    return {
        "status": "ready_for_phase1a_panel_specific_signal_packets",
        "panel_signals": {
            "panels": {
                "A+B": {
                    "source": "scFoundation_panel_embedding_summary",
                    "status": "ready",
                    "panel_id": "A+B",
                    "signal_type": "panel_specific_cell_embedding_summary",
                    "signal_scope": "panel_matched_norman_cells",
                    "embedding_dim": 3072,
                    "n_cells": 16,
                    "finite_fraction": 1.0,
                    "centroid_distance_to_control": 2.5,
                },
                "C+D": {
                    "source": "scFoundation_panel_embedding_summary",
                    "status": "missing_panel_cells",
                    "panel_id": "C+D",
                },
                "E+F": {
                    "source": "scFoundation_panel_embedding_summary",
                    "status": "ready",
                    "panel_id": "E+F",
                    "signal_type": "panel_specific_cell_embedding_summary",
                    "signal_scope": "panel_matched_norman_cells",
                    "embedding_dim": 3072,
                    "n_cells": 16,
                    "finite_fraction": 1.0,
                    "centroid_distance_to_control": 9.5,
                },
            }
        },
    }


class Phase1ASignalPacketTests(unittest.TestCase):
    def test_load_smoke_signal_extracts_compact_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "smoke.json"
            path.write_text(json.dumps(smoke_report()))

            signal = load_scfoundation_smoke_signal(str(path))

        self.assertEqual(signal["embedding_shape"], [3, 3072])
        self.assertEqual(signal["embedding_dim"], 3072)
        self.assertEqual(signal["input_gene_count"], 834)
        self.assertEqual(signal["scfoundation_feature_gene_count"], 19264)
        self.assertEqual(signal["calibration_status"], "unverified_proxy_not_calibrated")

    def test_load_smoke_signal_rejects_blocked_report(self):
        report = smoke_report()
        report["status"] = "blocked_missing_embedding_output"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "smoke.json"
            path.write_text(json.dumps(report))

            with self.assertRaises(ValueError):
                load_scfoundation_smoke_signal(str(path))

    def test_phase1a_packets_have_three_balanced_cues_and_no_truth_leakage(self):
        signal = load_signal_from_dict(smoke_report())
        packets = generate_phase1a_signal_packets([panel()], signal)

        self.assertEqual(len(packets), len(PHASE1A_SIGNAL_CUES))
        self.assertEqual({packet["cue_condition"] for packet in packets}, set(PHASE1A_SIGNAL_CUES))

        by_cue = {packet["cue_condition"]: packet for packet in packets}
        self.assertNotIn("internal_signal_summary", by_cue["no_internal_signal"]["evidence_packet"])
        self.assertIn("internal_signal_summary", by_cue["scfoundation_internal_signal_shown"]["evidence_packet"])
        self.assertIn("internal_signal_summary", by_cue["shuffled_internal_signal_shown"]["evidence_packet"])

        for packet_row in packets:
            rendered = json.dumps(packet_row["evidence_packet"], sort_keys=True)
            self.assertNotIn("correct", rendered)
            self.assertNotIn("real_call", rendered)
            self.assertNotIn("truth", rendered)
            self.assertNotIn(packet_row["cue_condition"], rendered)

    def test_shuffled_signal_is_deterministic_and_changes_numeric_summary(self):
        signal = load_signal_from_dict(smoke_report())
        first = shuffled_internal_signal(signal, panel_id="A+B", seed=7)
        second = shuffled_internal_signal(signal, panel_id="A+B", seed=7)
        third = shuffled_internal_signal(signal, panel_id="C+D", seed=7)

        self.assertEqual(first, second)
        self.assertNotEqual(first["embedding_mean"], signal["embedding_mean"])
        self.assertNotEqual(first["embedding_l2_norm"], signal["embedding_l2_norm"])
        self.assertNotEqual(first, third)
        self.assertEqual(first["embedding_shape"], signal["embedding_shape"])

    def test_panel_specific_signal_report_filters_ready_panels(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "panel_signals.json"
            path.write_text(json.dumps(panel_signal_report()))

            signals = load_panel_specific_internal_signals(str(path))

        self.assertEqual(sorted(signals), ["A+B", "E+F"])
        self.assertEqual(signals["A+B"]["signal_scope"], "panel_matched_norman_cells")

    def test_phase1a_packet_uses_panel_specific_signal_when_available(self):
        signals = {"A+B": panel_signal_report()["panel_signals"]["panels"]["A+B"]}
        packet_row = phase1a_signal_packet(
            panel("A+B"),
            "scfoundation_internal_signal_shown",
            panel_signals=signals,
        )
        signal = packet_row["evidence_packet"]["internal_signal_summary"]

        self.assertEqual(signal["panel_id"], "A+B")
        self.assertEqual(signal["centroid_distance_to_control"], 2.5)
        self.assertEqual(packet_row["metadata"]["internal_signal_control"], "real_panel_specific_summary")

    def test_panel_specific_shuffled_signal_uses_placebo_values_without_visible_label(self):
        report = panel_signal_report()
        signals = {
            key: value
            for key, value in report["panel_signals"]["panels"].items()
            if value["status"] == "ready"
        }
        packet_row = phase1a_signal_packet(
            panel("A+B"),
            "shuffled_internal_signal_shown",
            panel_signals=signals,
            seed=11,
        )
        signal = packet_row["evidence_packet"]["internal_signal_summary"]

        self.assertEqual(signal["panel_id"], "A+B")
        self.assertNotEqual(signal["centroid_distance_to_control"], 2.5)
        self.assertEqual(packet_row["metadata"]["internal_signal_control"], "deterministic_shuffled_control")
        rendered = json.dumps(packet_row["evidence_packet"], sort_keys=True)
        self.assertNotIn("deterministic_shuffled_control", rendered)

    def test_write_phase1a_signal_packets_writes_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            smoke = root / "smoke.json"
            out = root / "packets.jsonl"
            manifest = root / "manifest.json"
            smoke.write_text(json.dumps(smoke_report()))

            summary = write_phase1a_signal_packets(
                panels=[panel("A+B"), panel("C+D")],
                smoke_report=str(smoke),
                out=str(out),
                manifest_out=str(manifest),
                n_panels=1,
                seed=11,
            )

            self.assertTrue(out.is_file())
            self.assertTrue(manifest.is_file())
            self.assertEqual(summary["n_panels"], 1)
            self.assertEqual(summary["n_packets"], 3)
            self.assertEqual(summary["cue_counts"]["no_internal_signal"], 1)

    def test_single_packet_metadata_keeps_control_label_out_of_prompt(self):
        signal = load_signal_from_dict(smoke_report())
        packet_row = phase1a_signal_packet(panel(), "shuffled_internal_signal_shown", signal)

        self.assertEqual(packet_row["metadata"]["internal_signal_control"], "deterministic_shuffled_control")
        rendered = json.dumps(packet_row["evidence_packet"], sort_keys=True)
        self.assertNotIn("deterministic_shuffled_control", rendered)


def load_signal_from_dict(report):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "smoke.json"
        path.write_text(json.dumps(report))
        return load_scfoundation_smoke_signal(str(path))


if __name__ == "__main__":
    unittest.main()
