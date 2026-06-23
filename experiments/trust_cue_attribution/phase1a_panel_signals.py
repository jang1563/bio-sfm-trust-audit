"""Panel-specific scFoundation signal builder for Phase 1A.

This module creates a small, panel-matched h5ad subset from Norman cells, runs
the official scFoundation embedding script, and summarizes embeddings per panel.
It is a signal-construction step only; it does not call an LLM or score routing.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Any


TARGET_STATUS = "ready_for_phase1a_panel_specific_signal_packets"


def load_phase1a_panel_ids(manifest_path: str) -> list[str]:
    with open(manifest_path) as handle:
        manifest = json.load(handle)
    return [str(row["panel_id"]) for row in manifest.get("selected_panels", [])]


def run_phase1a_panel_scfoundation_signals(
    *,
    scfoundation_dir: str,
    input_data: str,
    phase1a_manifest: str,
    out_dir: str,
    report_out: str,
    max_cells_per_panel: int = 16,
    max_control_cells: int = 64,
    perturbation_col: str = "perturbation_name",
    control_label: str = "control",
    use_layer: str | None = "counts",
    task_name: str = "phase1a_panel_signal",
    pre_normalized: str = "F",
    tgthighres: str = "t4",
    seed: int = 37,
    timeout: int = 3600,
) -> dict[str, Any]:
    """Run a small panel-specific scFoundation embedding job and write report."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    report_path = Path(report_out)
    subset_h5ad = out_path / f"{task_name}_subset.h5ad"
    model_dir = Path(scfoundation_dir) / "model"
    embedding_path = out_path / f"{task_name}_01B-resolution_singlecell_cell_embedding_{tgthighres}_resolution.npy"
    panel_ids = load_phase1a_panel_ids(phase1a_manifest)

    report: dict[str, Any] = {
        "phase": "phase1a",
        "adapter": "ScFoundationAdapter",
        "status": "started",
        "claim_boundary": (
            "panel-specific scFoundation signal construction only; no LLM "
            "routing, true-SFM trust, or biological interpretation claim"
        ),
        "inputs": {
            "scfoundation_dir": scfoundation_dir,
            "model_dir": str(model_dir),
            "input_data": input_data,
            "phase1a_manifest": phase1a_manifest,
            "panel_ids": panel_ids,
            "perturbation_col": perturbation_col,
            "control_label": control_label,
            "use_layer": use_layer,
            "max_cells_per_panel": max_cells_per_panel,
            "max_control_cells": max_control_cells,
            "seed": seed,
        },
        "outputs": {
            "subset_h5ad": str(subset_h5ad),
            "embedding_path": str(embedding_path),
            "report_out": report_out,
        },
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
        },
    }

    try:
        subset_info = write_panel_subset_h5ad(
            input_data=input_data,
            out=str(subset_h5ad),
            panel_ids=panel_ids,
            perturbation_col=perturbation_col,
            control_label=control_label,
            max_cells_per_panel=max_cells_per_panel,
            max_control_cells=max_control_cells,
            use_layer=use_layer,
            seed=seed,
        )
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
            str(subset_h5ad),
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
            env=_runtime_env(),
        )
        report["process"] = {
            "returncode": proc.returncode,
            "stdout_tail": _tail(proc.stdout),
            "stderr_tail": _tail(proc.stderr),
        }
        if proc.returncode != 0:
            report["status"] = "blocked_scfoundation_panel_signal_failed"
            report["error"] = f"get_embedding.py exited with code {proc.returncode}"
        elif not embedding_path.is_file():
            report["status"] = "blocked_missing_panel_embedding_output"
            report["error"] = "get_embedding.py succeeded but expected embedding .npy was not found"
        else:
            report["embedding_summary"] = embedding_file_summary(str(embedding_path))
            report["panel_signals"] = summarize_panel_embeddings(
                embedding_path=str(embedding_path),
                subset_h5ad=str(subset_h5ad),
                panel_ids=panel_ids,
            )
            report["status"] = TARGET_STATUS
            report["next_actions"] = [
                "Regenerate Phase 1A packets using these per-panel internal_signal_summary values.",
                "Run a small Sonnet-only pilot only after leakage checks pass.",
            ]
    except Exception as exc:
        report["status"] = "blocked_phase1a_panel_signal_exception"
        report["error"] = f"{type(exc).__name__}: {exc}"

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return report


def write_panel_subset_h5ad(
    *,
    input_data: str,
    out: str,
    panel_ids: list[str],
    perturbation_col: str,
    control_label: str,
    max_cells_per_panel: int,
    max_control_cells: int,
    use_layer: str | None,
    seed: int,
) -> dict[str, Any]:
    """Write a deterministic h5ad subset for selected panels plus controls."""
    import anndata as ad  # type: ignore

    adata = ad.read_h5ad(input_data, backed="r")
    if perturbation_col not in adata.obs.columns:
        adata.file.close()
        raise ValueError(f"missing perturbation column {perturbation_col!r}")

    labels = adata.obs[perturbation_col].astype(str)
    source_shape = [int(adata.n_obs), int(adata.n_vars)]
    positions_by_label: dict[str, list[int]] = {}
    for idx, label in enumerate(labels):
        positions_by_label.setdefault(str(label), []).append(idx)

    rng = random.Random(seed)
    selected_positions: list[int] = []
    panel_counts: dict[str, dict[str, int]] = {}
    for panel_id in panel_ids:
        available = list(positions_by_label.get(panel_id, []))
        chosen = _sample_positions(available, max_cells_per_panel, rng)
        selected_positions.extend(chosen)
        panel_counts[panel_id] = {
            "available_cells": len(available),
            "selected_cells": len(chosen),
        }

    control_available = list(positions_by_label.get(control_label, []))
    control_chosen = _sample_positions(control_available, max_control_cells, rng)
    selected_positions.extend(control_chosen)

    selected_positions = sorted(set(selected_positions))
    subset = adata[selected_positions, :].to_memory()
    subset.obs["phase1a_signal_group"] = [
        "control" if str(value) == control_label else "panel"
        for value in subset.obs[perturbation_col].astype(str)
    ]
    subset.obs["phase1a_panel_id"] = [
        "control" if str(value) == control_label else str(value)
        for value in subset.obs[perturbation_col].astype(str)
    ]
    layer_used = None
    if use_layer and use_layer in subset.layers:
        subset.X = subset.layers[use_layer].copy()
        layer_used = use_layer
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    subset.write_h5ad(out)
    adata.file.close()
    return {
        "source_shape": source_shape,
        "subset_shape": [int(subset.n_obs), int(subset.n_vars)],
        "selected_panel_count": len(panel_ids),
        "panel_cell_counts": panel_counts,
        "control_available_cells": len(control_available),
        "control_selected_cells": len(control_chosen),
        "layer_used_as_X": layer_used,
        "obs_columns_added": ["phase1a_signal_group", "phase1a_panel_id"],
        "var_names_sample": [str(value) for value in subset.var_names[:12]],
    }


def summarize_panel_embeddings(
    *,
    embedding_path: str,
    subset_h5ad: str,
    panel_ids: list[str],
) -> dict[str, Any]:
    """Summarize cell embeddings into per-panel internal-signal records."""
    import anndata as ad  # type: ignore
    import numpy as np  # type: ignore

    embeddings = np.load(embedding_path)
    adata = ad.read_h5ad(subset_h5ad, backed="r")
    if embeddings.shape[0] != adata.n_obs:
        adata.file.close()
        raise ValueError(f"embedding/cell count mismatch: {embeddings.shape[0]} != {adata.n_obs}")
    panel_labels = list(map(str, adata.obs["phase1a_panel_id"].astype(str)))
    control_idx = [idx for idx, label in enumerate(panel_labels) if label == "control"]
    if not control_idx:
        adata.file.close()
        raise ValueError("no control embeddings available")
    control_embeddings = embeddings[control_idx]
    control_centroid = control_embeddings.mean(axis=0)

    panel_signals = {}
    for panel_id in panel_ids:
        idxs = [idx for idx, label in enumerate(panel_labels) if label == panel_id]
        if not idxs:
            panel_signals[panel_id] = {
                "source": "scFoundation_panel_embedding_summary",
                "status": "missing_panel_cells",
                "panel_id": panel_id,
                "n_cells": 0,
            }
            continue
        panel_embeddings = embeddings[idxs]
        panel_signals[panel_id] = panel_internal_signal(
            panel_id=panel_id,
            panel_embeddings=panel_embeddings,
            control_embeddings=control_embeddings,
            control_centroid=control_centroid,
        )
    adata.file.close()
    return {
        "signal_type": "panel_specific_cell_embedding_summary",
        "control_n_cells": int(len(control_idx)),
        "panel_count": len(panel_ids),
        "panels": panel_signals,
    }


def panel_internal_signal(
    *,
    panel_id: str,
    panel_embeddings: np.ndarray,
    control_embeddings: np.ndarray,
    control_centroid: np.ndarray,
) -> dict[str, Any]:
    import numpy as np  # type: ignore

    centroid = panel_embeddings.mean(axis=0)
    panel_norms = np.linalg.norm(panel_embeddings, axis=1)
    control_norms = np.linalg.norm(control_embeddings, axis=1)
    panel_to_control = np.linalg.norm(panel_embeddings - control_centroid, axis=1)
    centroid_distance = float(np.linalg.norm(centroid - control_centroid))
    return {
        "source": "scFoundation_panel_embedding_summary",
        "adapter": "ScFoundationAdapter",
        "status": "ready",
        "panel_id": panel_id,
        "signal_type": "panel_specific_cell_embedding_summary",
        "signal_scope": "panel_matched_norman_cells",
        "calibration_status": "unverified_proxy_not_calibrated",
        "embedding_dim": int(panel_embeddings.shape[1]),
        "n_cells": int(panel_embeddings.shape[0]),
        "control_reference_n_cells": int(control_embeddings.shape[0]),
        "finite_fraction": _round(float(np.isfinite(panel_embeddings).mean()), 6),
        "centroid_l2_norm": _round(float(np.linalg.norm(centroid)), 6),
        "mean_cell_l2_norm": _round(float(panel_norms.mean()), 6),
        "std_cell_l2_norm": _round(float(panel_norms.std()), 6),
        "control_mean_cell_l2_norm": _round(float(control_norms.mean()), 6),
        "centroid_distance_to_control": _round(centroid_distance, 6),
        "mean_cell_distance_to_control": _round(float(panel_to_control.mean()), 6),
        "std_cell_distance_to_control": _round(float(panel_to_control.std()), 6),
        "limitations": [
            "sampled_cells_only",
            "not_a_calibrated_uncertainty",
            "does_not_contain_hidden_labels",
        ],
    }


def embedding_file_summary(path: str) -> dict[str, Any]:
    import numpy as np  # type: ignore

    arr = np.load(path)
    return {
        "path": path,
        "sha256": sha256(path),
        "shape": [int(value) for value in arr.shape],
        "dtype": str(arr.dtype),
        "finite_fraction": _round(float(np.isfinite(arr).mean()), 6) if arr.size else None,
        "mean": _round(float(arr.mean()), 6) if arr.size else None,
        "std": _round(float(arr.std()), 6) if arr.size else None,
        "l2_norm": _round(float(np.linalg.norm(arr)), 6) if arr.size else None,
    }


def _sample_positions(positions: list[int], n: int, rng: random.Random) -> list[int]:
    if n <= 0:
        return []
    if len(positions) <= n:
        return list(positions)
    return sorted(rng.sample(positions, n))


def _runtime_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONNOUSERSITE", "1")
    env.setdefault("MPLCONFIGDIR", "/tmp/trustcue_mplconfig")
    return env


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _tail(text: str, max_lines: int = 80) -> list[str]:
    return text.splitlines()[-max_lines:]


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    if math.isnan(float(value)):
        return None
    return round(float(value), digits)
