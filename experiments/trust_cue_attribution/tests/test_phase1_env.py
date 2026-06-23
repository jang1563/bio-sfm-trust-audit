import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from phase1_env import (
    _module_import_record,
    _readiness_status,
    build_scfoundation_inference_env_report,
)


class Phase1EnvTests(unittest.TestCase):
    def test_missing_paths_block_report(self):
        with patch("phase1_env.REQUIRED_INFERENCE_MODULES", ["json"]), \
                patch("phase1_env._torch_info", return_value={"import_ok": True, "cuda_available": False}), \
                patch("phase1_env._nvidia_smi_record", return_value={"available": False}):
            report = build_scfoundation_inference_env_report(
                scfoundation_dir="/missing/scfoundation",
                checkpoint="/missing/checkpoint.pt",
                require_cuda=False,
                check_scfoundation_import=False,
            )

        self.assertEqual(report["status"], "blocked_missing_artifacts")
        self.assertEqual(report["adapter"], "ScFoundationAdapter")
        json.dumps(report)

    def test_import_record_reports_standard_module(self):
        record = _module_import_record("json")

        self.assertTrue(record["ok"])
        self.assertEqual(record["module"], "json")

    def test_readiness_order(self):
        paths = {
            "scfoundation_dir": {"matches_kind": True},
            "model_dir": {"matches_kind": True},
            "load_py": {"matches_kind": True},
            "get_embedding_py": {"matches_kind": True},
            "checkpoint": {"matches_kind": True},
        }
        modules = [{"module": "numpy", "ok": True}]
        status = _readiness_status(
            paths=paths,
            modules=modules,
            torch_info={"cuda_available": False},
            scfoundation_import={"enabled": True, "ok": True},
            require_cuda=True,
        )

        self.assertEqual(status, "blocked_no_cuda_visible")

    def test_ready_without_cuda_requirement_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "scFoundation"
            (repo / "model").mkdir(parents=True)
            (repo / "model" / "load.py").write_text("VALUE = 1\n")
            (repo / "model" / "get_embedding.py").write_text("print('placeholder')\n")
            checkpoint = root / "model.ckpt"
            checkpoint.write_text("placeholder\n")

            with patch("phase1_env.REQUIRED_INFERENCE_MODULES", ["json"]), \
                    patch("phase1_env._torch_info", return_value={"import_ok": True, "cuda_available": False}), \
                    patch("phase1_env._nvidia_smi_record", return_value={"available": False}):
                report = build_scfoundation_inference_env_report(
                    scfoundation_dir=str(repo),
                    checkpoint=str(checkpoint),
                    require_cuda=False,
                    check_scfoundation_import=True,
                )

        self.assertIn(report["status"], {"ready_for_gpu_env_probe", "blocked_missing_or_broken_modules"})
        self.assertTrue(report["scfoundation_import"]["ok"])


if __name__ == "__main__":
    unittest.main()
