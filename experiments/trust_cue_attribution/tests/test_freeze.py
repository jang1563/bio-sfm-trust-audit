import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from freeze import (
    MAIN_NON_LEAKAGE_CUES,
    break_even_lambda,
    _episode_integrity,
    _normalize_json_floats,
    _validate_counts,
    _validate_cues,
    _validate_phase0b_cues,
    _validate_phase0b_integrity,
    _validate_panel_balance,
    _validate_sanity,
)


class Phase0AFreezeTests(unittest.TestCase):
    def test_break_even_lambda_uses_accuracy_over_assay_delta(self):
        value = break_even_lambda(
            sonnet_accuracy=0.78,
            sonnet_assays_per_gene=0.18,
            opus_accuracy=0.81,
            opus_assays_per_gene=0.30,
        )
        self.assertAlmostEqual(value, 0.25)

    def test_break_even_lambda_handles_equal_assay_rate(self):
        value = break_even_lambda(
            sonnet_accuracy=0.78,
            sonnet_assays_per_gene=0.20,
            opus_accuracy=0.81,
            opus_assays_per_gene=0.20,
        )
        self.assertIsNone(value)

    def test_phase0a_validators_accept_expected_freeze_shape(self):
        _validate_counts({"panels": 2}, {"panels": 2})
        _validate_cues(sorted(MAIN_NON_LEAKAGE_CUES))
        _validate_panel_balance({"high": 4, "low": 4, "mid": 4})
        _validate_sanity({"a": True, "b": True})

    def test_phase0a_validators_reject_leaky_or_mismatched_inputs(self):
        with self.assertRaises(ValueError):
            _validate_counts({"panels": 1}, {"panels": 2})
        with self.assertRaises(ValueError):
            _validate_cues(sorted(MAIN_NON_LEAKAGE_CUES + ["raw_assay_stats_shown"]))
        with self.assertRaises(ValueError):
            _validate_phase0b_cues(sorted(MAIN_NON_LEAKAGE_CUES + ["raw_assay_stats_shown"]), {})
        with self.assertRaises(ValueError):
            _validate_panel_balance({"high": 5, "low": 4, "mid": 3})
        with self.assertRaises(ValueError):
            _validate_sanity({"a": True, "b": False})

    def test_freeze_float_normalization_is_stable(self):
        payload = {
            "metric": 0.7500515995872034,
            "negative_zero": -0.0,
            "nested": [0.036532507739938096],
        }
        self.assertEqual(
            _normalize_json_floats(payload),
            {
                "metric": 0.750051599587,
                "negative_zero": 0.0,
                "nested": [0.03653250774],
            },
        )

    def test_phase0b_validators_accept_expected_cue_counts(self):
        _validate_phase0b_cues(
            sorted(MAIN_NON_LEAKAGE_CUES),
            {cue: 107 for cue in MAIN_NON_LEAKAGE_CUES},
        )
        _validate_phase0b_integrity({
            "parse_errors": 0,
            "provider_errors": 0,
            "episodes_missing_actions": 0,
        })

    def test_episode_integrity_reports_gene_key_mismatch(self):
        packets = [{
            "packet_id": "P1::no_cue",
            "cue_condition": "no_cue",
            "evidence_packet": {
                "genes": [
                    {"gene_display": "CDKN1C"},
                    {"gene_display": "MAPK1"},
                ]
            },
        }]
        episodes = [{
            "packet_id": "P1::no_cue",
            "cue_condition": "no_cue",
            "actions": {
                "CDKN1B": {"action": "trust_sfm"},
                "MAPK1": {"action": "default_baseline"},
            },
        }]
        integrity = _episode_integrity(packets, episodes)
        self.assertEqual(integrity["episodes"], 1)
        self.assertEqual(integrity["total_expected_genes"], 2)
        self.assertEqual(integrity["total_action_keys"], 2)
        self.assertEqual(integrity["gene_key_mismatch_episode_count"], 1)
        self.assertEqual(
            integrity["gene_key_mismatch_examples"][0]["missing_expected_genes"],
            ["CDKN1C"],
        )
        self.assertEqual(
            integrity["gene_key_mismatch_examples"][0]["extra_action_genes"],
            ["CDKN1B"],
        )


if __name__ == "__main__":
    unittest.main()
