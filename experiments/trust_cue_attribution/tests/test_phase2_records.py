import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase2_records import (
    assemble_record,
    assemble_records,
    find_confidence_json,
    parse_boltz_confidence,
    to_plddt_0_100,
)


def write_conf(out_dir: Path, target_id: str, **fields) -> Path:
    d = out_dir / f"boltz_results_{target_id}" / "predictions" / target_id
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"confidence_{target_id}_model_0.json"
    p.write_text(json.dumps(fields))
    return p


class PlddtScaleTests(unittest.TestCase):
    def test_normalizes_0_1_to_0_100(self):
        self.assertEqual(to_plddt_0_100(0.85), 85.0)

    def test_leaves_0_100_untouched(self):
        self.assertEqual(to_plddt_0_100(85.0), 85.0)

    def test_none_passthrough(self):
        self.assertIsNone(to_plddt_0_100(None))


class ParseAndAssembleTests(unittest.TestCase):
    def test_parse_and_find(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            write_conf(out, "T1", complex_plddt=0.9, ptm=0.7, iptm=0.8, protein_iptm=0.75)
            path = find_confidence_json(str(out), "T1")
            self.assertIsNotNone(path)
            conf = parse_boltz_confidence(path)
            self.assertEqual(conf["complex_plddt"], 0.9)
            self.assertEqual(conf["iptm"], 0.8)

    def test_monomer_record_has_null_iptm(self):
        rec = assemble_record(
            target_id="T1", regime="monomer",
            confidence={"complex_plddt": 0.9, "iptm": 0.8, "protein_iptm": 0.7},
            truth_correct=True, truth_quality=0.83, template_baseline_correct=False,
        )
        self.assertEqual(rec["mean_plddt"], 90.0)
        self.assertIsNone(rec["iptm"])
        self.assertEqual(rec["truth"], {"correct": True, "quality": 0.83})

    def test_complex_record_uses_iptm_then_protein_iptm(self):
        rec = assemble_record(
            target_id="C1", regime="complex",
            confidence={"complex_plddt": 0.6, "iptm": None, "protein_iptm": 0.55},
            truth_correct=False, truth_quality=0.10, template_baseline_correct=True,
        )
        self.assertEqual(rec["iptm"], 0.55)  # falls back to protein_iptm
        self.assertTrue(rec["template_baseline_correct"])

    def test_assemble_records_skips_missing_without_dropping(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            write_conf(out, "T1", complex_plddt=0.92, iptm=0.0, protein_iptm=0.0)
            targets = [
                {"target_id": "T1", "regime": "monomer"},
                {"target_id": "T2", "regime": "complex"},  # no confidence json -> skipped
            ]
            truth_by_id = {
                "T1": {"correct": True, "quality": 0.88, "template_baseline_correct": False},
                "T2": {"correct": False, "quality": 0.2, "template_baseline_correct": True},
            }
            records, skipped = assemble_records(
                boltz_out_dir=str(out), targets=targets, truth_by_id=truth_by_id,
            )
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["target_id"], "T1")
            self.assertEqual(len(skipped), 1)
            self.assertIn("T2", skipped[0])


if __name__ == "__main__":
    unittest.main()
