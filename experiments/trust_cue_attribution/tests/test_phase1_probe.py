import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1_probe import build_scfoundation_feasibility, write_scfoundation_feasibility


class Phase1ProbeTests(unittest.TestCase):
    def test_missing_artifacts_block_hpc_smoke(self):
        report = build_scfoundation_feasibility()

        self.assertEqual(report["status"], "blocked_missing_required_artifacts")
        missing = {
            row["label"]
            for row in report["path_checks"]
            if row["required"] and not row["ready"]
        }
        self.assertIn("scfoundation_dir", missing)
        self.assertIn("checkpoint", missing)
        self.assertIn("phase1_input_data", missing)

    def test_ready_fixture_passes_file_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "scFoundation"
            (repo / "model").mkdir(parents=True)
            (repo / "GEARS" / "run_sh").mkdir(parents=True)
            (repo / "README.md").write_text("scFoundation\n")
            gene_index = repo / "OS_scRNA_gene_index.19264.tsv"
            gene_index.write_text("gene\tindex\nA\t0\n")
            checkpoint = root / "checkpoint.pt"
            checkpoint.write_text("placeholder\n")
            input_data = root / "phase1_input.h5ad"
            input_data.write_text("placeholder\n")
            output_dir = root / "phase1_outputs"
            output_dir.mkdir()

            report = build_scfoundation_feasibility(
                scfoundation_dir=str(repo),
                checkpoint=str(checkpoint),
                input_data=str(input_data),
                output_dir=str(output_dir),
            )

        self.assertEqual(report["status"], "ready_for_hpc_smoke")
        self.assertTrue(all(row["ready"] for row in report["contract_preflight_checks"]))

    def test_write_feasibility_round_trips_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "feasibility.json"
            report = write_scfoundation_feasibility(str(out))
            loaded = json.loads(out.read_text())

        self.assertEqual(loaded, report)
        self.assertEqual(loaded["adapter"], "ScFoundationAdapter")


if __name__ == "__main__":
    unittest.main()
