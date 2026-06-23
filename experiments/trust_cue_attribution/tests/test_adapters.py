import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from adapters import adapter_contracts, get_adapter_contract, write_adapter_contract


class AdapterContractTests(unittest.TestCase):
    def test_sc_foundation_contract_has_phase1_boundaries(self):
        contract = get_adapter_contract("ScFoundationAdapter")
        payload = contract.describe()

        self.assertEqual(payload["phase"], "phase1")
        self.assertEqual(payload["compute_target"], "cayuga_or_expanse")
        self.assertIn("internal_signal_summary", payload["evidence_fields"])
        self.assertIn("held-out truth labels", payload["hidden_fields"])
        self.assertIn(
            "produces at least one internal_signal_summary field",
            payload["preflight_checks"],
        )
        self.assertIn("interface preflight only", payload["claim_boundary"])

    def test_boltz_structure_contract_has_phase2_calibration_boundaries(self):
        payload = get_adapter_contract("BoltzStructureAdapter").describe()

        self.assertEqual(payload["phase"], "phase2")
        self.assertEqual(payload["compute_target"], "cayuga_or_expanse")
        self.assertTrue(any("reliability_interface" in f for f in payload["evidence_fields"]))
        self.assertIn(
            "offline_calibration_gate_passes_before_any_llm_call",
            payload["preflight_checks"],
        )
        self.assertTrue(any("post_training_cutoff" in c for c in payload["preflight_checks"]))
        self.assertIn("calibrated", payload["claim_boundary"])

    def test_adapter_registry_contains_planned_expansion_targets(self):
        contracts = adapter_contracts()
        self.assertEqual(
            sorted(contracts),
            [
                "AlphaGenomeAdapter",
                "BoltzStructureAdapter",
                "Evo2Adapter",
                "GEARSAdapter",
                "ScFoundationAdapter",
            ],
        )

    def test_unknown_adapter_raises_clear_error(self):
        with self.assertRaises(ValueError):
            get_adapter_contract("MissingAdapter")

    def test_write_adapter_contract_round_trips_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "scfoundation_contract.json"
            payload = write_adapter_contract("ScFoundationAdapter", str(out))
            loaded = json.loads(out.read_text())

        self.assertEqual(loaded, payload)
        self.assertEqual(loaded["name"], "ScFoundationAdapter")


if __name__ == "__main__":
    unittest.main()
