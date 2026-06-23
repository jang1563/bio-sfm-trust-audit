import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase2_score_episodes import episode_action, outcome, score_episodes


def ep(target, arm, action):
    e = {"packet_id": f"{target}::{arm}", "cue_condition": arm, "actions": {}}
    if action is not None:
        e["actions"] = {"target": {"action": action}}
    return e


def records():
    return [
        {"target_id": "good", "regime": "monomer", "template_baseline_correct": False, "truth": {"quality": 0.97}},
        {"target_id": "bad", "regime": "complex", "template_baseline_correct": False, "truth": {"quality": 0.40}},
    ]


class ActionTests(unittest.TestCase):
    def test_extract_action(self):
        self.assertEqual(episode_action(ep("t", "no_signal", "trust_sfm")), "trust_sfm")

    def test_missing_action_is_defer(self):
        self.assertEqual(episode_action(ep("t", "no_signal", None)), "defer")
        self.assertEqual(episode_action({"actions": {}, "parse_error": "x"}), "defer")


class OutcomeTests(unittest.TestCase):
    def test_trust_matches_target(self):
        self.assertEqual(outcome("trust_sfm", True, False, 0.5), (1, 0))
        self.assertEqual(outcome("trust_sfm", False, False, 0.5), (0, 0))

    def test_verify_always_correct_costs_assay(self):
        self.assertEqual(outcome("verify_assay", False, False, 0.5), (1, 1))

    def test_default_follows_template(self):
        self.assertEqual(outcome("default_baseline", False, True, 0.5), (1, 0))
        self.assertEqual(outcome("default_baseline", True, False, 0.5), (0, 0))

    def test_defer_zero(self):
        self.assertEqual(outcome("defer", True, True, 0.5), (0, 0))


class ScoreTests(unittest.TestCase):
    def test_per_arm_and_paired(self):
        eps = [
            # no_signal: trust both -> good correct, bad wrong (trust error)
            ep("good", "no_signal", "trust_sfm"), ep("bad", "no_signal", "trust_sfm"),
            # calibrated_interface: trust good, verify bad -> both correct, 1 assay
            ep("good", "calibrated_interface_shown", "trust_sfm"),
            ep("bad", "calibrated_interface_shown", "verify_assay"),
        ]
        res = score_episodes(eps, records(), lam=0.5, correct_lddt=0.9)
        ns = res["per_arm"]["no_signal"]
        ci = res["per_arm"]["calibrated_interface_shown"]
        self.assertAlmostEqual(ns["accuracy"], 0.5)          # 1/2 correct
        self.assertAlmostEqual(ns["trust_error_rate"], 0.5)  # trusted the bad one
        self.assertAlmostEqual(ci["accuracy"], 1.0)          # both correct
        self.assertAlmostEqual(ci["net_reward_per_target"], 1.0 - 0.5 * 0.5)  # 1 assay over 2
        paired = res["paired_cue_effects_vs_no_signal"]["calibrated_interface_shown"]
        self.assertGreater(paired["delta_net_per_target"], 0)  # calibrated routing helps here


if __name__ == "__main__":
    unittest.main()
