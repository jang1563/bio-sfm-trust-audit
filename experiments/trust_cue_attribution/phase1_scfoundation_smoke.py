"""Tiny scFoundation inference smoke.

This module runs the official scFoundation `model/get_embedding.py` on a tiny
h5ad subset and writes a compact summary. It is a wiring smoke only, not a
scientific result.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def run_scfoundation_smoke(
    *,
    scfoundation_dir: str,
    input_data: str,
    out_dir: str,
    report_out: str,
    n_cells: int = 3,
    task_name: str = "phase1_smoke",
    pre_normalized: str = "F",
    tgthighres: str = "t4",
    timeout: int = 1200,
) -> dict[str, Any]:
    """Run a tiny official scFoundation embedding smoke and write a report."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    tiny_h5ad = out_path / f"{task_name}_first_{n_cells}_cells.h5ad"
    report_path = Path(report_out)
    model_dir = Path(scfoundation_dir) / "model"
    embedding_path = out_path / f"{task_name}_01B-resolution_singlecell_cell_embedding_{tgthighres}_resolution.npy"

    report: dict[str, Any] = {
        "phase": "phase1",
        "adapter": "ScFoundationAdapter",
        "status": "started",
        "claim_boundary": "tiny scFoundation inference smoke only; no LLM trust or scientific interpretation claim",
        "inputs": {
            "scfoundation_dir": scfoundation_dir,
            "model_dir": str(model_dir),
            "input_data": input_data,
            "tiny_h5ad": str(tiny_h5ad),
            "n_cells": n_cells,
            "pre_normalized": pre_normalized,
            "tgthighres": tgthighres,
        },
        "outputs": {
            "embedding_path": str(embedding_path),
            "report_out": report_out,
        },
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
        },
    }

    try:
        subset_info = _write_tiny_h5ad(input_data, str(tiny_h5ad), n_cells=n_cells)
        report["subset"] = subset_info
        command = [
            sys.executable,
            "get_embedding.py",
            "--task_name",
            task_name,
            "--input_type",
            "singlecell",
            "--output_type",
            "cell",
            "--pool_type",
            "all",
            "--tgthighres",
            tgthighres,
            "--data_path",
            str(tiny_h5ad),
            "--save_path",
            str(out_path),
            "--pre_normalized",
            pre_normalized,
            "--version",
            "ce",
        ]
        report["command"] = command
        proc = subprocess.run(
            command,
            cwd=str(model_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=_smoke_env(),
        )
        report["process"] = {
            "returncode": proc.returncode,
            "stdout_tail": _tail(proc.stdout),
            "stderr_tail": _tail(proc.stderr),
        }
        if proc.returncode != 0:
            report["status"] = "blocked_scfoundation_smoke_failed"
            report["error"] = f"get_embedding.py exited with code {proc.returncode}"
        elif not embedding_path.is_file():
            report["status"] = "blocked_missing_embedding_output"
            report["error"] = "get_embedding.py succeeded but expected embedding .npy was not found"
        else:
            report["embedding_summary"] = _embedding_summary(str(embedding_path))
            report["status"] = "ready_for_internal_signal_summary_adapter"
            report["next_actions"] = [
                "Convert the compact embedding summary into standardized Phase 1 internal-signal evidence packets.",
                "Do not expose held-out truth, reward, or correctness fields in model-visible packets.",
            ]
    except Exception as exc:
        report["status"] = "blocked_scfoundation_smoke_exception"
        report["error"] = f"{type(exc).__name__}: {exc}"

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return report


def _write_tiny_h5ad(input_data: str, out: str, *, n_cells: int) -> dict[str, Any]:
    import anndata as ad  # type: ignore

    adata = ad.read_h5ad(input_data, backed="r")
    subset = adata[:n_cells, :].to_memory()
    info = {
        "source_shape": [int(adata.n_obs), int(adata.n_vars)],
        "subset_shape": [int(subset.n_obs), int(subset.n_vars)],
        "var_names_sample": [str(value) for value in subset.var_names[:12]],
        "obs_names_sample": [str(value) for value in subset.obs_names[:12]],
    }
    subset.write_h5ad(out)
    adata.file.close()
    return info


def _embedding_summary(path: str) -> dict[str, Any]:
    import numpy as np  # type: ignore

    arr = np.load(path)
    finite = np.isfinite(arr)
    return {
        "path": path,
        "sha256": _sha256(path),
        "shape": [int(value) for value in arr.shape],
        "dtype": str(arr.dtype),
        "finite_fraction": float(finite.mean()) if arr.size else None,
        "mean": float(arr.mean()) if arr.size else None,
        "std": float(arr.std()) if arr.size else None,
        "l2_norm": float(np.linalg.norm(arr)) if arr.size else None,
    }


def _smoke_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONNOUSERSITE", "1")
    env.setdefault("MPLCONFIGDIR", "/tmp/trustcue_mplconfig")
    return env


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _tail(text: str, max_lines: int = 80) -> list[str]:
    lines = text.splitlines()
    return lines[-max_lines:]
