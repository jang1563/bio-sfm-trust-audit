import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1c_specialist_metric_check import (
    auroc,
    lopo_threshold_accuracy,
    pearson,
    reward_respecification,
    score_edges,
    spearman,
)


def edge(gene, fm_log2fc, fm_call, fm_correct, base_log2fc, base_correct, real_call, raw_log2fc, source="observed_additive"):
    return {
        "edge_id": f"P::{gene}",
        "gene": gene,
        "fm": {"model_name": "GEARS", "log2fc": fm_log2fc, "call": fm_call, "correct": fm_correct},
        "baseline_signal": {"log2fc": base_log2fc, "call": ("effect" if abs(base_log2fc) >= 0.25 else "no_effect"),
                            "correct": base_correct, "source": source, "call_disagreement": True, "abs_fm_minus_baseline": 0.1},
        "truth": {"real_call": real_call, "real_label": "POSITIVE" if real_call == "effect" else "TESTED_NEGATIVE"},
        "raw": {"raw_log2FC": raw_log2fc, "raw_q": 0.01, "raw_se": 0.05, "n_trt": 100, "n_cntrl": 1000},
        "regime": "combo_in_train",
    }


def two_panels():
    return [
        {"panel_id": "A+B", "edges": [
            edge("G1", 0.9, "effect", True, 0.8, True, "effect", 1.0),
            edge("G2", 0.05, "no_effect", True, 0.02, True, "no_effect", 0.0),
        ]},
        {"panel_id": "C+D", "edges": [
            edge("G3", 0.6, "effect", False, 0.1, True, "no_effect", 0.02),
            edge("G4", 0.7, "effect", True, 0.7, True, "effect", 0.9),
        ]},
    ]


class StatHelperTests(unittest.TestCase):
    def test_auroc_perfect_and_inverted(self):
        self.assertEqual(auroc([1, 2, 3, 4], [0, 0, 1, 1]), 1.0)
        self.assertEqual(auroc([1, 2, 3, 4], [1, 1, 0, 0]), 0.0)

    def test_auroc_ties_give_half(self):
        self.assertEqual(auroc([1, 1, 2, 2], [0, 1, 0, 1]), 0.5)

    def test_auroc_degenerate_returns_none(self):
        self.assertIsNone(auroc([1, 2, 3], [1, 1, 1]))

    def test_pearson_and_spearman(self):
        self.assertAlmostEqual(pearson([1, 2, 3], [2, 4, 6]), 1.0, places=9)
        # monotonic but nonlinear -> spearman 1.0, pearson < 1
        self.assertAlmostEqual(spearman([1, 2, 3], [1, 4, 9]), 1.0, places=9)
        self.assertLess(pearson([1, 2, 3], [1, 4, 9]), 1.0)


class ScoreEdgesTests(unittest.TestCase):
    def test_binary_accuracy_matches_stored_correct(self):
        edges = [e for p in two_panels() for e in p["edges"]]
        out = score_edges(edges)
        # 3 of 4 GEARS calls correct, 4 of 4 additive correct
        self.assertAlmostEqual(out["gears"]["binary_call_accuracy"], 0.75, places=6)
        self.assertAlmostEqual(out["additive"]["binary_call_accuracy"], 1.0, places=6)
        self.assertEqual(out["n_effect"], 2)
        self.assertEqual(out["n_no_effect"], 2)

    def test_continuous_block_drops_nonfinite(self):
        edges = [e for p in two_panels() for e in p["edges"]]
        edges[0]["raw"]["raw_log2FC"] = float("nan")
        out = score_edges(edges)
        self.assertEqual(out["gears"]["n_continuous"], len(edges) - 1)


class RecalibrationTests(unittest.TestCase):
    def test_lopo_returns_valid_accuracy(self):
        panels = two_panels()
        res = lopo_threshold_accuracy(panels, lambda e: abs(e["fm"]["log2fc"]))
        self.assertIn("lopo_accuracy", res)
        self.assertTrue(0.0 <= res["lopo_accuracy"] <= 1.0)
        self.assertTrue(0.0 <= res["global_best_in_sample_accuracy"] <= 1.0)
        # in-sample best is an upper bound on the honest LOPO estimate
        self.assertGreaterEqual(res["global_best_in_sample_accuracy"], res["lopo_accuracy"])

    def test_reward_respecification_structure(self):
        panels = two_panels()
        out = reward_respecification({"slice": panels}, lam=0.5)
        block = out["slice"]
        self.assertEqual(block["n_edges"], 4)
        self.assertIn("net_reward_per_gene_lambda_0.5", block)
        nr = block["net_reward_per_gene_lambda_0.5"]
        self.assertAlmostEqual(nr["verify_all"], 0.5, places=6)
        # trust_all fixed net == mean(fm.correct) == 0.75 (0 assays)
        self.assertAlmostEqual(nr["trust_all_sfm_fixed_0.25"], 0.75, places=6)


if __name__ == "__main__":
    unittest.main()
