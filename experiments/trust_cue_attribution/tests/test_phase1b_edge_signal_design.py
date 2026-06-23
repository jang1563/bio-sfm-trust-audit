import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1b_edge_signal_design import (
    phase1b_edge_signal_design,
    write_phase1b_edge_signal_design,
)


def panel(panel_id, genes):
    return {
        "panel_id": panel_id,
        "edges": [
            {"gene": gene, "edge_id": f"{panel_id}::{gene}"}
            for gene in genes
        ],
    }


def manifest():
    return {
        "selected_panels": [
            {"panel_id": "P1"},
            {"panel_id": "P2"},
        ]
    }


class Phase1BEdgeSignalDesignTests(unittest.TestCase):
    def test_design_recommends_neighbor_route_when_gene_reuse_is_high(self):
        panels = [
            panel("P1", ["G1", "G2"]),
            panel("P2", ["G1", "G2"]),
            panel("P3", ["G1", "G2"]),
            panel("P4", ["G1", "G2"]),
            panel("P5", ["G1", "G2"]),
            panel("P6", ["G1", "G2"]),
            panel("P7", ["G1", "G2"]),
            panel("P8", ["G1", "G2"]),
            panel("P9", ["G1", "G2"]),
            panel("P10", ["G1", "G2"]),
            panel("P11", ["G1", "G2"]),
            panel("P12", ["G1", "G2"]),
        ]

        report = phase1b_edge_signal_design(panels, manifest())

        self.assertEqual(report["status"], "edge_signal_design_ready")
        self.assertEqual(report["scope"]["selected_edges"], 4)
        self.assertEqual(
            report["recommended_route"]["route"],
            "scfoundation_neighbor_edge_support",
        )
        self.assertEqual(
            report["recommended_route"]["decision"],
            "recommended_for_hpc_prototype",
        )
        self.assertEqual(
            report["edge_reuse_feasibility"]["coverage"]["edges_with_at_least_10_other_panels_same_gene"]["fraction"],
            1.0,
        )

    def test_write_phase1b_edge_signal_design_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "design.json"
            report = write_phase1b_edge_signal_design(
                panels=[
                    panel("P1", ["G1"]),
                    panel("P2", ["G1"]),
                    panel("P3", ["G1"]),
                ],
                manifest={"selected_panels": [{"panel_id": "P1"}]},
                out=str(out),
            )

            self.assertTrue(out.exists())
            self.assertEqual(report["scope"]["selected_edges"], 1)


if __name__ == "__main__":
    unittest.main()
