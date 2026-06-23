import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import sys

try:
    import numpy as np
except ImportError:  # Cayuga system Python does not include numpy; scFoundation env does.
    np = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1a_panel_signals import (
    TARGET_STATUS,
    embedding_file_summary,
    panel_internal_signal,
    run_phase1a_panel_scfoundation_signals,
)


class Phase1APanelSignalTests(unittest.TestCase):
    @unittest.skipIf(np is None, "numpy is required for embedding-summary tests")
    def test_panel_internal_signal_summarizes_distances_without_labels(self):
        panel = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        control = np.array([[0.0, 0.0], [0.5, 0.0]], dtype=np.float32)
        signal = panel_internal_signal(
            panel_id="A+B",
            panel_embeddings=panel,
            control_embeddings=control,
            control_centroid=control.mean(axis=0),
        )

        self.assertEqual(signal["status"], "ready")
        self.assertEqual(signal["panel_id"], "A+B")
        self.assertEqual(signal["embedding_dim"], 2)
        self.assertEqual(signal["n_cells"], 2)
        rendered = str(signal)
        self.assertNotIn("correct", rendered)
        self.assertNotIn("truth", rendered)

    @unittest.skipIf(np is None, "numpy is required for embedding-summary tests")
    def test_embedding_file_summary_records_shape_hash_and_finite_fraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "emb.npy"
            np.save(path, np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32))

            summary = embedding_file_summary(str(path))

        self.assertEqual(summary["shape"], [2, 2])
        self.assertEqual(summary["dtype"], "float32")
        self.assertEqual(summary["finite_fraction"], 1.0)
        self.assertEqual(len(summary["sha256"]), 64)

    @unittest.skipIf(np is None, "numpy is required for embedding-summary tests")
    def test_run_panel_signal_report_reaches_ready_status_when_embedding_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / "manifest.json"
            report = root / "report.json"
            out_dir = root / "out"
            model_dir = root / "scfoundation" / "model"
            model_dir.mkdir(parents=True)
            manifest.write_text('{"selected_panels": [{"panel_id": "A+B"}]}')
            expected_embedding = out_dir / "phase1a_panel_signal_01B-resolution_singlecell_cell_embedding_t4_resolution.npy"

            def fake_subset(**kwargs):
                return {"subset_shape": [3, 10], "panel_cell_counts": {"A+B": {"selected_cells": 2}}}

            def fake_run(*args, **kwargs):
                expected_embedding.parent.mkdir(parents=True, exist_ok=True)
                np.save(expected_embedding, np.ones((3, 4), dtype=np.float32))
                return SimpleNamespace(returncode=0, stdout="ok", stderr="")

            with patch("phase1a_panel_signals.write_panel_subset_h5ad", side_effect=fake_subset), \
                 patch("phase1a_panel_signals.subprocess.run", side_effect=fake_run), \
                 patch("phase1a_panel_signals.summarize_panel_embeddings", return_value={"panel_count": 1, "panels": {"A+B": {"status": "ready"}}}):
                payload = run_phase1a_panel_scfoundation_signals(
                    scfoundation_dir=str(root / "scfoundation"),
                    input_data=str(root / "input.h5ad"),
                    phase1a_manifest=str(manifest),
                    out_dir=str(out_dir),
                    report_out=str(report),
                )

        self.assertEqual(payload["status"], TARGET_STATUS)
        self.assertEqual(payload["embedding_summary"]["shape"], [3, 4])


if __name__ == "__main__":
    unittest.main()
