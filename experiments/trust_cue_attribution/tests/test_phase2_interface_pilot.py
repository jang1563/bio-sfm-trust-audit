import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase2_interface_pilot import (
    PHASE2_INTERFACE_CUES,
    generate_phase2_interface_packets,
    leakage_check,
    phase2_interface_packet,
    select_balanced_targets,
)


def rec(tid, regime, plddt, quality, iptm=None, nchains=1):
    return {"target_id": tid, "regime": regime, "mean_plddt": plddt, "iptm": iptm,
            "n_protein_chains": nchains, "template_baseline_correct": False,
            "truth": {"correct": quality >= 0.9, "quality": quality}}


def records(n=24):
    out = []
    for i in range(n):
        regime = "monomer" if i % 2 == 0 else "complex"
        out.append(rec(f"t{i}", regime, 50.0 + i, 0.5 + 0.02 * i,
                       iptm=(0.6 if regime == "complex" else None),
                       nchains=(2 if regime == "complex" else 1)))
    return out


class PacketArmTests(unittest.TestCase):
    def test_no_signal_has_no_confidence(self):
        p = phase2_interface_packet(rec("t", "monomer", 90, 0.95), "no_signal", 0.1)
        self.assertNotIn("confidence", p["evidence_packet"])
        self.assertNotIn("reliability", p["evidence_packet"])
        self.assertNotIn("reliability_interface", p["evidence_packet"])

    def test_raw_arm_shows_plddt(self):
        p = phase2_interface_packet(rec("t", "monomer", 90, 0.95), "raw_plddt_shown", 0.1)
        self.assertEqual(p["evidence_packet"]["confidence"]["mean_plddt_0_100"], 90)

    def test_risk_no_reco_omits_recommendation(self):
        p = phase2_interface_packet(rec("t", "monomer", 90, 0.95), "calibrated_risk_shown_no_recommendation", 0.2)
        rel = p["evidence_packet"]["reliability"]
        self.assertEqual(rel["estimated_wrong_risk"], 0.2)
        self.assertNotIn("recommended_action", rel)

    def test_interface_arm_has_recommendation(self):
        p = phase2_interface_packet(rec("t", "monomer", 90, 0.95), "calibrated_interface_shown", 0.2)
        self.assertEqual(p["evidence_packet"]["reliability_interface"]["recommended_action"], "trust_sfm")

    def test_inverted_arm_flips_and_notes(self):
        p = phase2_interface_packet(rec("t", "monomer", 90, 0.95), "inverted_reliability_interface_control", 0.2)
        ri = p["evidence_packet"]["reliability_interface"]
        self.assertEqual(ri["estimated_wrong_risk"], 0.8)  # inverted
        self.assertEqual(ri["recommended_action"], "verify_assay")
        self.assertIn("control_note", ri)


class GenerationTests(unittest.TestCase):
    def test_balanced_selection(self):
        sel = select_balanced_targets(records(24), n_per_regime=4)
        self.assertEqual(len(sel), 8)  # 4 per regime

    def test_generates_five_arms_per_target_and_no_leak(self):
        packets = generate_phase2_interface_packets(records(24), n_per_regime=4)
        self.assertEqual(len(packets), 8 * len(PHASE2_INTERFACE_CUES))
        self.assertTrue(leakage_check(packets)["passed"])

    def test_leakage_check_catches_truth_field(self):
        packets = generate_phase2_interface_packets(records(24), n_per_regime=2)
        packets[0]["evidence_packet"]["lddt"] = 0.83  # inject leak
        self.assertFalse(leakage_check(packets)["passed"])


if __name__ == "__main__":
    unittest.main()
