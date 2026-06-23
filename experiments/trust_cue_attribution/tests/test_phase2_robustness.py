import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase2_robustness import bootstrap_contrasts, build_outcome_table, lambda_sweep


def ep(target, arm, action):
    return {"packet_id": f"{target}::{arm}", "cue_condition": arm, "actions": {"target": {"action": action}}}


def make(n=30):
    """n targets: half good/half bad. no_signal trusts (bad->wrong); calibrated verifies the bad."""
    eps, recs = [], []
    for i in range(n):
        tid = f"t{i}"
        good = i % 2 == 0
        recs.append({"target_id": tid, "regime": "monomer", "template_baseline_correct": False,
                     "truth": {"quality": 0.97 if good else 0.4}})
        eps.append(ep(tid, "no_signal", "trust_sfm"))
        eps.append(ep(tid, "calibrated_interface_shown", "trust_sfm" if good else "verify_assay"))
        eps.append(ep(tid, "raw_plddt_shown", "trust_sfm" if good else "verify_assay"))
        eps.append(ep(tid, "calibrated_risk_shown_no_recommendation", "trust_sfm" if good else "verify_assay"))
        eps.append(ep(tid, "inverted_reliability_interface_control", "verify_assay"))
    return eps, recs


class RobustnessTests(unittest.TestCase):
    def setUp(self):
        eps, recs = make()
        self.table = build_outcome_table(eps, recs, correct_lddt=0.9)

    def test_lambda_sweep_net_drops_with_cost(self):
        sweep = lambda_sweep(self.table)
        # calibrated verifies the bad half -> assays>0 -> net falls as lambda rises
        self.assertGreater(sweep["0.2"]["calibrated_interface_shown"], sweep["0.8"]["calibrated_interface_shown"])
        # no_signal trusts all -> 0 assays -> net constant in lambda
        self.assertAlmostEqual(sweep["0.2"]["no_signal"], sweep["0.8"]["no_signal"])

    def test_calibrated_beats_no_signal_robustly(self):
        cis = bootstrap_contrasts(self.table, lam=0.5, n_boot=300, seed=13)
        c = cis["calibrated_interface_shown_vs_no_signal"]
        self.assertTrue(c["robust_positive"])      # CI strictly above 0
        self.assertGreater(c["delta_net_point"], 0)

    def test_a4_contrast_is_near_zero(self):
        # calibrated_interface vs no_recommendation are identical actions here -> delta 0
        cis = bootstrap_contrasts(self.table, lam=0.5, n_boot=300, seed=13)
        c = cis["calibrated_interface_shown_vs_calibrated_risk_shown_no_recommendation"]
        self.assertEqual(c["delta_net_point"], 0.0)
        self.assertTrue(c["ci_crosses_zero"])


if __name__ == "__main__":
    unittest.main()
