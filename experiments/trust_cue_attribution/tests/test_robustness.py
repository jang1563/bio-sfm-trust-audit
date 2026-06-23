import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from robustness import build_phase0b_robustness, _percentile


class RobustnessTests(unittest.TestCase):
    def test_percentile_interpolates(self):
        self.assertEqual(_percentile([0, 10], 0.5), 5)
        self.assertEqual(_percentile([3], 0.975), 3)
        self.assertEqual(_percentile([], 0.5), 0.0)

    def test_phase0b_robustness_is_seed_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            panels = [
                _panel("P1", g1_fm_correct=False, g2_fm_correct=True),
                _panel("P2", g1_fm_correct=False, g2_fm_correct=True),
            ]
            packets = []
            episodes = []
            for panel in panels:
                for cue in ("no_cue", "additive_disagreement_shown"):
                    packet_id = f"{panel['panel_id']}::{cue}"
                    packets.append(_packet(panel["panel_id"], packet_id, cue))
                    episodes.append(_episode(packet_id, cue))

            _write_jsonl(root / "panels_full.jsonl", panels)
            _write_jsonl(root / "cue_packets_full.jsonl", packets)
            _write_jsonl(root / "llm_claude-sonnet-4-6_phase0b_main_episodes.jsonl", episodes)

            first = build_phase0b_robustness(str(root), n_boot=25, seed=7)
            second = build_phase0b_robustness(str(root), n_boot=25, seed=7)

        self.assertEqual(first, second)
        effect = first["paired_cue_effects"]["additive_disagreement_shown"]
        self.assertEqual(effect["n_pairs"], 4)
        self.assertIn("delta_net", effect)
        self.assertIn("ci_low", effect["delta_net"])
        self.assertIn("trust_all_sfm", first["baseline_delta_net_reward_per_gene"])


def _panel(panel_id, g1_fm_correct, g2_fm_correct):
    return {
        "panel_id": panel_id,
        "edges": [
            {
                "gene": "G1",
                "fm": {"correct": g1_fm_correct},
                "baseline_signal": {"correct": True, "source": "observed_additive"},
                "reliability_signal": {"score": 0.9},
            },
            {
                "gene": "G2",
                "fm": {"correct": g2_fm_correct},
                "baseline_signal": {"correct": True, "source": "observed_additive"},
                "reliability_signal": {"score": 0.1},
            },
        ],
    }


def _packet(panel_id, packet_id, cue):
    return {
        "packet_id": packet_id,
        "panel_id": panel_id,
        "cue_condition": cue,
        "evidence_packet": {
            "genes": [
                {"gene_display": "G1"},
                {"gene_display": "G2"},
            ],
        },
        "scoring_key": [
            {"gene": "G1", "gene_display": "G1"},
            {"gene": "G2", "gene_display": "G2"},
        ],
    }


def _episode(packet_id, cue):
    if cue == "no_cue":
        actions = {
            "G1": {"action": "trust_sfm", "rationale": "SFM log2fc"},
            "G2": {"action": "trust_sfm", "rationale": "SFM log2fc"},
        }
    else:
        actions = {
            "G1": {"action": "verify_assay", "rationale": "baseline disagreement"},
            "G2": {"action": "trust_sfm", "rationale": "SFM log2fc"},
        }
    return {
        "packet_id": packet_id,
        "cue_condition": cue,
        "model": "claude-sonnet-4-6",
        "self_reported_cues": ["baseline disagreement"] if cue == "no_cue" else ["baseline"],
        "actions": actions,
    }


def _write_jsonl(path, rows):
    with open(path, "w") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


if __name__ == "__main__":
    unittest.main()
