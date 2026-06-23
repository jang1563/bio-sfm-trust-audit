import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase2_calibration_gate import (
    confidence_to_risk,
    phase2_calibration_gate,
    risk_threshold_policy_net,
)


def make_records(n_per_regime=40, calibrated=True, wrong_frac=0.35):
    """Synthetic per-target records. Calibrated: confident<->correct. Uncalibrated:
    constant confidence (no signal)."""
    recs = []
    for regime in ("monomer", "complex"):
        n_wrong = round(n_per_regime * wrong_frac)
        for i in range(n_per_regime):
            wrong = i >= (n_per_regime - n_wrong)
            if calibrated:
                plddt = 40.0 if wrong else 90.0
                iptm = (0.40 if wrong else 0.85) if regime == "complex" else None
            else:
                plddt = 70.0
                iptm = 0.70 if regime == "complex" else None
            recs.append({
                "target_id": f"{regime}_{i}",
                "regime": regime,
                "mean_plddt": plddt,
                "iptm": iptm,
                "template_baseline_correct": (i % 2 == 0),
                "truth": {"correct": (not wrong), "quality": (0.30 if wrong else 0.85)},
            })
    return recs


class RiskHelperTests(unittest.TestCase):
    def test_confidence_to_risk_monomer(self):
        self.assertAlmostEqual(confidence_to_risk({"regime": "monomer", "mean_plddt": 90.0}), 0.10, places=6)

    def test_confidence_to_risk_complex_blends_iptm(self):
        r = confidence_to_risk({"regime": "complex", "mean_plddt": 80.0, "iptm": 0.40})
        self.assertAlmostEqual(r, 1.0 - 0.5 * 0.80 - 0.5 * 0.40, places=6)

    def test_policy_verifies_high_risk_and_trusts_low(self):
        recs = [
            {"truth": {"correct": False}},  # high risk -> verify -> correct
            {"truth": {"correct": True}},   # low risk -> trust -> correct
        ]
        net = risk_threshold_policy_net(recs, [0.9, 0.1], lam=0.5)
        # both correct (1.0), one assay (0.5 cost over 2 targets = 0.25)
        self.assertAlmostEqual(net, 1.0 - 0.5 * 0.5, places=6)


class CalibrationGateTests(unittest.TestCase):
    def test_calibrated_signal_passes_gate(self):
        gate = phase2_calibration_gate(make_records(calibrated=True))
        self.assertEqual(gate["decision"], "eligible_for_phase2_interface_pilot")
        self.assertGreaterEqual(gate["signal_validity"]["wrong_risk_auroc"], 0.70)
        self.assertGreaterEqual(gate["margins"]["real_minus_shuffled"], 0.05)
        self.assertTrue(all(gate["checks"].values()))

    def test_uncalibrated_signal_fails_gate(self):
        gate = phase2_calibration_gate(make_records(calibrated=False))
        self.assertEqual(gate["decision"], "do_not_run_signal_not_calibrated")
        self.assertFalse(gate["checks"]["signal_validity_auroc_ok"])

    def test_power_floor_blocks_when_too_few_targets(self):
        gate = phase2_calibration_gate(make_records(n_per_regime=10, calibrated=True))
        self.assertFalse(gate["checks"]["power_sufficient"])
        self.assertEqual(gate["decision"], "eligible_pending_more_targets")


if __name__ == "__main__":
    unittest.main()
