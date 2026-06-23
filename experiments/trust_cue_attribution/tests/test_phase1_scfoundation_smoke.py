import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1_scfoundation_smoke import _tail, run_scfoundation_smoke


class Phase1ScFoundationSmokeTests(unittest.TestCase):
    def test_tail_limits_lines(self):
        text = "\n".join(str(i) for i in range(100))

        self.assertEqual(_tail(text, max_lines=3), ["97", "98", "99"])

    def test_exception_report_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "report.json"
            with patch("phase1_scfoundation_smoke._write_tiny_h5ad", side_effect=RuntimeError("boom")):
                report = run_scfoundation_smoke(
                    scfoundation_dir=str(root / "missing_scfoundation"),
                    input_data=str(root / "missing_input.h5ad"),
                    out_dir=str(root / "out"),
                    report_out=str(out),
                    n_cells=1,
                )
            self.assertTrue(out.is_file())

        self.assertEqual(report["status"], "blocked_scfoundation_smoke_exception")

    def test_success_report_reaches_adapter_ready_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model_dir = root / "scfoundation" / "model"
            model_dir.mkdir(parents=True)
            out_dir = root / "out"
            expected_embedding = out_dir / "phase1_smoke_01B-resolution_singlecell_cell_embedding_t4_resolution.npy"
            out = root / "report.json"

            def fake_run(*args, **kwargs):
                expected_embedding.parent.mkdir(parents=True, exist_ok=True)
                expected_embedding.write_bytes(b"fake embedding")
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")

            with patch("phase1_scfoundation_smoke._write_tiny_h5ad", return_value={"subset_shape": [1, 2]}), \
                 patch("phase1_scfoundation_smoke.subprocess.run", side_effect=fake_run), \
                 patch("phase1_scfoundation_smoke._embedding_summary", return_value={"shape": [1, 512]}):
                report = run_scfoundation_smoke(
                    scfoundation_dir=str(root / "scfoundation"),
                    input_data=str(root / "input.h5ad"),
                    out_dir=str(out_dir),
                    report_out=str(out),
                    n_cells=1,
                )

        self.assertEqual(report["status"], "ready_for_internal_signal_summary_adapter")
        self.assertEqual(report["embedding_summary"]["shape"], [1, 512])


if __name__ == "__main__":
    unittest.main()
