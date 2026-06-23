import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase2_calibrated_gate import (
    _pava,
    calibrated_gate,
    isotonic_calibrator,
    loo_calibrated_risks,
)


def make_records(n_per_regime=35, wrong_frac=0.4, calibrated=True):
    recs = []
    for regime in ("monomer", "complex"):
        n_wrong = round(n_per_regime * wrong_frac)
        for i in range(n_per_regime):
            wrong = i >= (n_per_regime - n_wrong)
            if calibrated:
                plddt = 60.0 if wrong else 92.0
                iptm = (0.40 if wrong else 0.85) if regime == "complex" else None
            else:
                plddt = 80.0
                iptm = 0.70 if regime == "complex" else None
            recs.append({
                "target_id": f"{regime}_{i}", "regime": regime,
                "mean_plddt": plddt, "iptm": iptm,
                "template_baseline_correct": False,
                "truth": {"correct": (not wrong), "quality": (0.50 if wrong else 0.95)},
            })
    return recs


class IsotonicTests(unittest.TestCase):
    def test_pava_is_non_decreasing_and_pools(self):
        out = _pava([3.0, 1.0, 2.0])
        self.assertEqual(out, [2.0, 2.0, 2.0])  # pooled to the mean
        self.assertTrue(all(out[i] <= out[i + 1] + 1e-9 for i in range(len(out) - 1)))

    def test_pava_passthrough_when_sorted(self):
        self.assertEqual(_pava([0.0, 0.0, 1.0, 1.0]), [0.0, 0.0, 1.0, 1.0])

    def test_calibrator_monotonic_maps_low_to_low(self):
        cal = isotonic_calibrator([0.1, 0.2, 0.8, 0.9], [0, 0, 1, 1])
        self.assertLessEqual(cal(0.1), cal(0.85))
        self.assertEqual(cal(0.05), 0.0)
        self.assertEqual(cal(0.95), 1.0)

    def test_loo_returns_probabilities(self):
        raw = [0.1, 0.15, 0.2, 0.8, 0.85, 0.9]
        wrong = [0, 0, 0, 1, 1, 1]
        out = loo_calibrated_risks(raw, wrong)
        self.assertEqual(len(out), 6)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in out))


class CalibratedGateTests(unittest.TestCase):
    def test_calibrated_signal_passes(self):
        gate = calibrated_gate(make_records(calibrated=True), correct_lddt=0.9)
        self.assertEqual(gate["decision"], "eligible_for_phase2_interface_pilot")
        self.assertTrue(gate["checks"]["policy_beats_trust_all"])
        self.assertGreaterEqual(gate["margins"]["real_minus_shuffled"], 0.05)

    def test_uncalibrated_signal_fails_validity(self):
        gate = calibrated_gate(make_records(calibrated=False), correct_lddt=0.9)
        self.assertFalse(gate["checks"]["signal_validity_auroc_ok"])
        self.assertEqual(gate["decision"], "do_not_run_signal_not_calibrated")


if __name__ == "__main__":
    unittest.main()
