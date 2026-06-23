"""Phase 1B edge-level scFoundation neighbor-signal prototype.

This module builds a public-Norman scFoundation embedding pool and evaluates a
readout-gene-specific neighbor cue before any additional LLM spend. It is a
pre-LLM gate: no Claude call, no true-SFM trust claim, and no biological
interpretation claim.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from .phase1a_signal_validity import selected_panels_from_manifest
except ImportError:  # direct script/test execution from this directory
    from phase1a_signal_validity import selected_panels_from_manifest


TARGET_POOL_STATUS = "ready_for_phase1b_edge_neighbor_signals"
TARGET_DIAGNOSTIC_STATUS = "phase1b_edge_neighbor_signal_diagnostic_ready"
PRIMARY_REAL_SCORE = "neighbor_sfm_call_disagreement_rate"
REFERENCE_PANEL_CARD_AUC = 0.467366
FORBIDDEN_VISIBLE_KEYS = {
    "correct",
    "fm_correct",
    "truth",
    "real_call",
    "real_label",
    "reward",
    "raw",
    "raw_log2FC",
    "raw_se",
    "raw_q",
    "n_trt",
    "n_cntrl",
    "scoring_key",
}


def run_phase1b_embedding_pool(
    *,
    scfoundation_dir: str,
    input_data: str,
    panels: list[dict[str, Any]],
    out_dir: str,
    pool_out: str,
    report_out: str,
    max_cells_per_panel: int = 12,
    max_control_cells: int = 128,
    perturbation_col: str = "perturbation_name",
    control_label: str = "control",
    use_layer: str | None = "counts",
    task_name: str = "phase1b_embedding_pool",
    pre_normalized: str = "F",
    tgthighres: str = "t4",
    seed: int = 41,
    timeout: int = 7200,
) -> dict[str, Any]:
    """Run scFoundation embeddings for the full Phase 0 panel pool."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    report_path = Path(report_out)
    subset_h5ad = out_path / f"{task_name}_subset.h5ad"
    model_dir = Path(scfoundation_dir) / "model"
    embedding_path = out_path / f"{task_name}_01B-resolution_singlecell_cell_embedding_{tgthighres}_resolution.npy"
    panel_ids = sorted({str(panel["panel_id"]) for panel in panels})

    report: dict[str, Any] = {
        "phase": "phase1b",
        "adapter": "ScFoundationAdapter",
        "status": "started",
        "claim_boundary": (
            "Embedding-pool construction only; no LLM routing, true-SFM trust, "
            "or biological interpretation claim."
        ),
        "inputs": {
            "scfoundation_dir": scfoundation_dir,
            "model_dir": str(model_dir),
            "input_data": input_data,
            "panel_count": len(panel_ids),
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
            "pool_out": pool_out,
            "report_out": report_out,
        },
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
        },
    }

    try:
        subset_info = write_phase1b_embedding_subset_h5ad(
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
            report["status"] = "blocked_scfoundation_phase1b_pool_failed"
            report["error"] = f"get_embedding.py exited with code {proc.returncode}"
        elif not embedding_path.is_file():
            report["status"] = "blocked_missing_phase1b_embedding_output"
            report["error"] = "get_embedding.py succeeded but expected embedding .npy was not found"
        else:
            pool = summarize_phase1b_embedding_pool(
                embedding_path=str(embedding_path),
                subset_h5ad=str(subset_h5ad),
                panel_ids=panel_ids,
                pool_out=pool_out,
            )
            report["embedding_summary"] = embedding_file_summary(str(embedding_path))
            report["pool_summary"] = {
                "status": pool["status"],
                "panel_count": pool["summary"]["panel_count"],
                "matched_panel_count": pool["summary"]["matched_panel_count"],
                "missing_panel_count": pool["summary"]["missing_panel_count"],
                "control_n_cells": pool["summary"]["control_n_cells"],
                "embedding_dim": pool["summary"]["embedding_dim"],
                "pool_sha256": sha256(pool_out),
            }
            report["status"] = TARGET_POOL_STATUS
            report["next_actions"] = [
                "Build edge-level neighbor signals for the 12-panel Phase 1A surface.",
                "Run leakage, within-panel variation, and edge-level AUROC diagnostics before LLM spend.",
            ]
    except Exception as exc:
        report["status"] = "blocked_phase1b_embedding_pool_exception"
        report["error"] = f"{type(exc).__name__}: {exc}"

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return report


def write_phase1b_embedding_subset_h5ad(
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
    """Write a deterministic h5ad subset for all Phase 1B panels plus controls."""
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
    subset.obs["phase1b_signal_group"] = [
        "control" if str(value) == control_label else "panel"
        for value in subset.obs[perturbation_col].astype(str)
    ]
    subset.obs["phase1b_panel_id"] = [
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

    missing = [panel_id for panel_id, counts in panel_counts.items() if counts["selected_cells"] == 0]
    return {
        "source_shape": source_shape,
        "subset_shape": [int(subset.n_obs), int(subset.n_vars)],
        "requested_panel_count": len(panel_ids),
        "matched_panel_count": len(panel_ids) - len(missing),
        "missing_panel_count": len(missing),
        "missing_panels": missing,
        "panel_cell_counts": panel_counts,
        "control_available_cells": len(control_available),
        "control_selected_cells": len(control_chosen),
        "layer_used_as_X": layer_used,
        "obs_columns_added": ["phase1b_signal_group", "phase1b_panel_id"],
        "var_names_sample": [str(value) for value in subset.var_names[:12]],
    }


def summarize_phase1b_embedding_pool(
    *,
    embedding_path: str,
    subset_h5ad: str,
    panel_ids: list[str],
    pool_out: str,
) -> dict[str, Any]:
    """Summarize cell embeddings into a panel-centroid pool for neighbor signals."""
    import anndata as ad  # type: ignore
    import numpy as np  # type: ignore

    embeddings = np.load(embedding_path)
    adata = ad.read_h5ad(subset_h5ad, backed="r")
    if embeddings.shape[0] != adata.n_obs:
        adata.file.close()
        raise ValueError(f"embedding/cell count mismatch: {embeddings.shape[0]} != {adata.n_obs}")

    labels = list(map(str, adata.obs["phase1b_panel_id"].astype(str)))
    control_idx = [idx for idx, label in enumerate(labels) if label == "control"]
    if not control_idx:
        adata.file.close()
        raise ValueError("no control embeddings available")

    control_embeddings = embeddings[control_idx]
    control_centroid = control_embeddings.mean(axis=0)
    panel_embeddings = {}
    missing = []
    for panel_id in panel_ids:
        idxs = [idx for idx, label in enumerate(labels) if label == panel_id]
        if not idxs:
            missing.append(panel_id)
            continue
        arr = embeddings[idxs]
        centroid = arr.mean(axis=0)
        panel_embeddings[panel_id] = {
            "panel_id": panel_id,
            "n_cells": int(arr.shape[0]),
            "embedding_dim": int(arr.shape[1]),
            "centroid": [_round(float(value), 8) for value in centroid.tolist()],
            "centroid_l2_norm": _round(float(np.linalg.norm(centroid)), 6),
            "centroid_distance_to_control": _round(float(np.linalg.norm(centroid - control_centroid)), 6),
            "mean_cell_distance_to_control": _round(float(np.linalg.norm(arr - control_centroid, axis=1).mean()), 6),
        }
    adata.file.close()

    pool = {
        "phase": "phase1b",
        "adapter": "ScFoundationAdapter",
        "status": TARGET_POOL_STATUS,
        "claim_boundary": (
            "Panel-centroid embedding pool for edge-neighbor diagnostics only; "
            "not a calibrated uncertainty estimate."
        ),
        "summary": {
            "panel_count": len(panel_ids),
            "matched_panel_count": len(panel_embeddings),
            "missing_panel_count": len(missing),
            "missing_panels": missing,
            "control_n_cells": int(len(control_idx)),
            "embedding_dim": int(embeddings.shape[1]),
            "embedding_path": embedding_path,
            "embedding_sha256": sha256(embedding_path),
        },
        "panel_embeddings": panel_embeddings,
    }
    os.makedirs(os.path.dirname(pool_out) or ".", exist_ok=True)
    with open(pool_out, "w") as handle:
        json.dump(pool, handle, sort_keys=True)
        handle.write("\n")
    return pool


def phase1b_neighbor_signal_diagnostic(
    *,
    panels: list[dict[str, Any]],
    manifest: dict[str, Any],
    embedding_pool: dict[str, Any],
    k_neighbors: int = 10,
    seed: int = 41,
) -> dict[str, Any]:
    """Evaluate edge-level neighbor signals before building LLM packets."""
    if embedding_pool.get("status") != TARGET_POOL_STATUS:
        raise ValueError(f"embedding pool is not ready: {embedding_pool.get('status')!r}")

    selected_panels = selected_panels_from_manifest(manifest)
    selected_ids = {str(panel["panel_id"]) for panel in selected_panels}
    panel_embeddings = embedding_pool.get("panel_embeddings", {})
    edge_rows = _edge_rows(panels)
    rows_by_gene = _rows_by_gene(edge_rows)
    selected_rows = [
        row for row in edge_rows
        if row["panel_id"] in selected_ids
    ]

    signal_rows = []
    visible_records = []
    real_visible_by_edge = {}
    random_visible_by_edge = {}
    for row in selected_rows:
        real_summary, real_scores = _neighbor_summary(
            target=row,
            rows_by_gene=rows_by_gene,
            panel_embeddings=panel_embeddings,
            k_neighbors=k_neighbors,
            seed=seed,
            mode="embedding_nearest",
        )
        random_summary, random_scores = _neighbor_summary(
            target=row,
            rows_by_gene=rows_by_gene,
            panel_embeddings=panel_embeddings,
            k_neighbors=k_neighbors,
            seed=seed,
            mode="random_same_gene",
        )
        visible_records.append({
            "panel_id": row["panel_id"],
            "gene_display": row["gene"],
            "edge_internal_signal_summary": real_summary,
        })
        real_visible_by_edge[row["edge_id"]] = {
            "panel_id": row["panel_id"],
            "gene_display": row["gene"],
            "edge_internal_signal_summary": real_summary,
        }
        random_visible_by_edge[row["edge_id"]] = {
            "panel_id": row["panel_id"],
            "gene_display": row["gene"],
            "edge_internal_signal_summary": random_summary,
        }
        signal_rows.append({
            "panel_id": row["panel_id"],
            "gene": row["gene"],
            "edge_id": row["edge_id"],
            "sfm_wrong": int(row["sfm_wrong"]),
            "target_baseline_call_disagreement": int(row["baseline_call_disagreement"]),
            "target_reliability_signal_score": row["reliability_signal_score"],
            **{f"real_{key}": value for key, value in real_scores.items()},
            **{f"random_same_gene_{key}": value for key, value in random_scores.items()},
        })

    shuffled_rows = _add_shuffled_readout_gene_scores(signal_rows, seed=seed)
    signal_rows = shuffled_rows
    model_visible_edge_signals = _model_visible_edge_signals(
        rows=signal_rows,
        real_visible_by_edge=real_visible_by_edge,
        random_visible_by_edge=random_visible_by_edge,
        seed=seed,
    )
    leakage = leakage_check(visible_records)
    full_leakage = leakage_check(model_visible_edge_signals)
    variation = within_panel_variation(signal_rows)
    aucs = edge_signal_aucs(signal_rows)
    decision = phase1b_gate_decision(
        rows=signal_rows,
        leakage=full_leakage,
        variation=variation,
        aucs=aucs,
    )

    return {
        "phase": "phase1b",
        "status": TARGET_DIAGNOSTIC_STATUS,
        "claim_boundary": (
            "Pre-LLM edge-neighbor diagnostic only; no LLM routing result, no "
            "faithful scFoundation interpretation claim, and no biological claim."
        ),
        "scope": {
            "selected_panels": len(selected_ids),
            "selected_edges": len(selected_rows),
            "matched_signal_edges": len(signal_rows),
            "full_panels": len(panels),
            "embedding_pool_panels": len(panel_embeddings),
            "k_neighbors": k_neighbors,
            "public_data_source_policy": "public Norman 2019 only; no local unpublished FRAM2 data",
        },
        "model_visible_schema": {
            "evidence_packet.genes[].edge_internal_signal_summary": _visible_schema(),
            "model_visible_edge_signals[].real_edge_internal_signal_summary": _visible_schema(),
            "model_visible_edge_signals[].random_same_gene_edge_internal_signal_summary": _visible_schema(),
            "model_visible_edge_signals[].shuffled_readout_gene_edge_internal_signal_summary": _visible_schema(),
        },
        "leakage_check": leakage,
        "full_model_visible_signal_leakage_check": full_leakage,
        "within_panel_variation": variation,
        "edge_level_auc": aucs,
        "decision": decision,
        "model_visible_edge_signals": model_visible_edge_signals,
        "model_visible_edge_signal_preview": visible_records[:5],
        "diagnostic_rows_preview": signal_rows[:5],
    }


def write_phase1b_neighbor_signal_diagnostic(
    *,
    panels: list[dict[str, Any]],
    manifest: dict[str, Any],
    embedding_pool: dict[str, Any],
    out: str,
    k_neighbors: int = 10,
    seed: int = 41,
) -> dict[str, Any]:
    report = phase1b_neighbor_signal_diagnostic(
        panels=panels,
        manifest=manifest,
        embedding_pool=embedding_pool,
        k_neighbors=k_neighbors,
        seed=seed,
    )
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return report


def leakage_check(visible_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Check model-visible signal records for forbidden scoring/truth fields."""
    hits = _find_forbidden_visible_keys(visible_records)
    return {
        "passed": len(hits) == 0,
        "forbidden_key_hits": hits,
        "forbidden_keys": sorted(FORBIDDEN_VISIBLE_KEYS),
    }


def within_panel_variation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize whether edge signals vary across genes within panels."""
    fields = [
        "real_neighbor_sfm_call_disagreement_rate",
        "real_neighbor_baseline_disagreement_rate",
        "real_neighbor_embedding_distance_mean",
        "random_same_gene_neighbor_sfm_call_disagreement_rate",
        "shuffled_readout_gene_neighbor_sfm_call_disagreement_rate",
    ]
    by_panel: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_panel[str(row["panel_id"])].append(row)

    field_reports = {}
    for field in fields:
        varied = 0
        panel_reports = []
        for panel_id, panel_rows in sorted(by_panel.items()):
            values = {
                _round(float(row[field]), 6)
                for row in panel_rows
                if _finite(row.get(field))
            }
            has_variation = len(values) > 1
            varied += int(has_variation)
            panel_reports.append({
                "panel_id": panel_id,
                "edge_count": len(panel_rows),
                "unique_value_count": len(values),
                "varies_within_panel": has_variation,
            })
        field_reports[field] = {
            "panels_with_variation": varied,
            "panel_count": len(by_panel),
            "fraction": _round(varied / len(by_panel), 6) if by_panel else 0.0,
            "panels": panel_reports,
        }
    return field_reports


def edge_signal_aucs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute edge-level AUROC diagnostics against hidden GEARS wrongness."""
    score_fields = [
        "real_neighbor_sfm_call_disagreement_rate",
        "real_neighbor_baseline_disagreement_rate",
        "real_neighbor_embedding_distance_mean",
        "random_same_gene_neighbor_sfm_call_disagreement_rate",
        "random_same_gene_neighbor_baseline_disagreement_rate",
        "shuffled_readout_gene_neighbor_sfm_call_disagreement_rate",
        "target_baseline_call_disagreement",
        "target_reliability_signal_score",
    ]
    out = {}
    for field in score_fields:
        pairs = [
            (float(row[field]), int(row["sfm_wrong"]))
            for row in rows
            if _finite(row.get(field))
        ]
        auc = _roc_auc(pairs)
        out[field] = {
            "n": len(pairs),
            "auc_higher_score_means_more_wrong": _round(auc, 6),
            "auc_direction_invariant": _round(max(auc, 1 - auc), 6) if auc is not None else None,
        }
    return out


def phase1b_gate_decision(
    *,
    rows: list[dict[str, Any]],
    leakage: dict[str, Any],
    variation: dict[str, Any],
    aucs: dict[str, Any],
) -> dict[str, Any]:
    """Decide whether the edge-neighbor signal is ready for a small LLM pilot."""
    primary_field = f"real_{PRIMARY_REAL_SCORE}"
    primary_auc = aucs.get(primary_field, {}).get("auc_higher_score_means_more_wrong")
    random_auc = aucs.get(f"random_same_gene_{PRIMARY_REAL_SCORE}", {}).get("auc_higher_score_means_more_wrong")
    shuffled_auc = aucs.get(f"shuffled_readout_gene_{PRIMARY_REAL_SCORE}", {}).get("auc_higher_score_means_more_wrong")
    variation_fraction = variation.get(primary_field, {}).get("fraction", 0.0)
    matched_edges = len(rows)

    reasons = []
    if not leakage.get("passed"):
        reasons.append("visible_signal_failed_leakage_check")
    if matched_edges == 0:
        reasons.append("no_matched_edges")
    if variation_fraction < 0.75:
        reasons.append("insufficient_within_panel_variation")
    if primary_auc is None or primary_auc <= 0.55:
        reasons.append("primary_real_signal_not_predictive_enough")
    if random_auc is not None and primary_auc is not None and primary_auc <= random_auc + 0.02:
        reasons.append("real_signal_does_not_clear_random_same_gene_control")
    if shuffled_auc is not None and primary_auc is not None and primary_auc <= shuffled_auc + 0.02:
        reasons.append("real_signal_does_not_clear_shuffled_readout_gene_control")

    decision = "eligible_for_small_llm_pilot" if not reasons else "diagnostic_only_do_not_run_llm_yet"
    return {
        "decision": decision,
        "reasons": reasons,
        "primary_real_score": primary_field,
        "primary_real_auc": primary_auc,
        "random_same_gene_control_auc": random_auc,
        "shuffled_readout_gene_control_auc": shuffled_auc,
        "within_panel_variation_fraction": variation_fraction,
        "reference_panel_card_auc_from_phase1a": REFERENCE_PANEL_CARD_AUC,
        "required_before_llm": [
            "leakage_check_passed",
            "within_panel_variation_fraction_at_least_0.75",
            "primary_real_auc_above_0.55",
            "primary_real_auc_clears_random_and_shuffled_controls_by_0.02",
        ],
    }


def _neighbor_summary(
    *,
    target: dict[str, Any],
    rows_by_gene: dict[str, list[dict[str, Any]]],
    panel_embeddings: dict[str, dict[str, Any]],
    k_neighbors: int,
    seed: int,
    mode: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = [
        row for row in rows_by_gene.get(target["gene"], [])
        if row["panel_id"] != target["panel_id"]
        and row["panel_id"] in panel_embeddings
        and target["panel_id"] in panel_embeddings
    ]
    if mode == "embedding_nearest":
        ranked = sorted(
            (
                {
                    **candidate,
                    "embedding_distance": _euclidean(
                        panel_embeddings[target["panel_id"]]["centroid"],
                        panel_embeddings[candidate["panel_id"]]["centroid"],
                    ),
                }
                for candidate in candidates
            ),
            key=lambda row: (row["embedding_distance"], row["panel_id"], row["edge_id"]),
        )
        selected = ranked[:k_neighbors]
        source = "scFoundation_neighbor_edge_support"
    elif mode == "random_same_gene":
        rng = random.Random(f"{seed}:{target['edge_id']}:random_same_gene")
        ranked = [
            {
                **candidate,
                "embedding_distance": _euclidean(
                    panel_embeddings[target["panel_id"]]["centroid"],
                    panel_embeddings[candidate["panel_id"]]["centroid"],
                ),
            }
            for candidate in candidates
        ]
        selected = sorted(rng.sample(ranked, min(k_neighbors, len(ranked))), key=lambda row: (row["panel_id"], row["edge_id"]))
        source = "random_same_readout_gene_neighbor_control"
    else:
        raise ValueError(f"unknown neighbor mode {mode!r}")

    distances = [float(row["embedding_distance"]) for row in selected]
    agreement = _mean(row["fm_call"] == target["fm_call"] for row in selected)
    baseline_rate = _mean(row["baseline_call_disagreement"] for row in selected)
    disagreement = None if agreement is None else 1.0 - agreement

    summary = {
        "source": source,
        "adapter": "ScFoundationAdapter",
        "signal_scope": "readout_gene_specific",
        "readout_gene_display": target["gene"],
        "neighbor_count": len(selected),
        "same_readout_gene_neighbor_count": len(candidates),
        "neighbor_embedding_distance": {
            "mean": _round(_mean(distances), 6),
            "min": _round(min(distances), 6) if distances else None,
            "max": _round(max(distances), 6) if distances else None,
        },
        "neighbor_sfm_call_agreement_rate": _round(agreement, 6),
        "neighbor_sfm_call_disagreement_rate": _round(disagreement, 6),
        "neighbor_baseline_disagreement_rate": _round(baseline_rate, 6),
        "calibration_status": "unverified_proxy_not_calibrated",
        "limitations": [
            "not_a_calibrated_uncertainty",
            "does_not_contain_hidden_labels",
            "neighbor_similarity_may_not_equal_error_risk",
        ],
    }
    scores = {
        "neighbor_count": float(len(selected)),
        "same_readout_gene_neighbor_count": float(len(candidates)),
        "neighbor_embedding_distance_mean": _none_to_nan(_mean(distances)),
        "neighbor_sfm_call_agreement_rate": _none_to_nan(agreement),
        "neighbor_sfm_call_disagreement_rate": _none_to_nan(disagreement),
        "neighbor_baseline_disagreement_rate": _none_to_nan(baseline_rate),
    }
    return summary, scores


def _add_shuffled_readout_gene_scores(rows: list[dict[str, Any]], *, seed: int) -> list[dict[str, Any]]:
    candidates = [row for row in rows if _finite(row.get("real_neighbor_sfm_call_disagreement_rate"))]
    out = []
    for row in rows:
        rng = random.Random(f"{seed}:{row['edge_id']}:shuffled_readout_gene")
        pool = [candidate for candidate in candidates if candidate["gene"] != row["gene"]]
        source = rng.choice(pool) if pool else row
        copied = dict(row)
        for key, value in source.items():
            if key.startswith("real_neighbor_"):
                copied[f"shuffled_readout_gene_{key.removeprefix('real_')}"] = value
        out.append(copied)
    return out


def _model_visible_edge_signals(
    *,
    rows: list[dict[str, Any]],
    real_visible_by_edge: dict[str, dict[str, Any]],
    random_visible_by_edge: dict[str, dict[str, Any]],
    seed: int,
) -> list[dict[str, Any]]:
    candidates = [
        row for row in rows
        if _finite(row.get("real_neighbor_sfm_call_disagreement_rate"))
        and row["edge_id"] in real_visible_by_edge
    ]
    out = []
    for row in rows:
        edge_id = row["edge_id"]
        real_record = real_visible_by_edge[edge_id]
        random_record = random_visible_by_edge[edge_id]
        rng = random.Random(f"{seed}:{edge_id}:shuffled_readout_gene")
        pool = [candidate for candidate in candidates if candidate["gene"] != row["gene"]]
        source_row = rng.choice(pool) if pool else row
        source_record = real_visible_by_edge.get(source_row["edge_id"], real_record)
        shuffled_summary = _shuffled_visible_summary(
            source_record["edge_internal_signal_summary"],
            target_gene=row["gene"],
        )
        out.append({
            "panel_id": row["panel_id"],
            "gene_display": row["gene"],
            "real_edge_internal_signal_summary": real_record["edge_internal_signal_summary"],
            "random_same_gene_edge_internal_signal_summary": random_record["edge_internal_signal_summary"],
            "shuffled_readout_gene_edge_internal_signal_summary": shuffled_summary,
        })
    return sorted(out, key=lambda record: (record["panel_id"], record["gene_display"]))


def _shuffled_visible_summary(summary: dict[str, Any], *, target_gene: str) -> dict[str, Any]:
    out = json.loads(json.dumps(summary))
    out["source"] = "shuffled_readout_gene_neighbor_control"
    out["readout_gene_display"] = target_gene
    limitations = list(out.get("limitations", []))
    if "signal_values_copied_from_different_readout_gene_control" not in limitations:
        limitations.append("signal_values_copied_from_different_readout_gene_control")
    out["limitations"] = limitations
    out["calibration_status"] = "unverified_proxy_not_calibrated"
    return out


def _edge_rows(panels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for panel in panels:
        panel_id = str(panel.get("panel_id"))
        for edge in panel.get("edges", []):
            baseline = edge.get("baseline_signal", {})
            reliability = edge.get("reliability_signal", {})
            rows.append({
                "panel_id": panel_id,
                "gene": str(edge.get("gene")),
                "edge_id": str(edge.get("edge_id", f"{panel_id}::{edge.get('gene')}")),
                "fm_call": str(edge.get("fm", {}).get("call")),
                "sfm_wrong": not bool(edge.get("fm", {}).get("correct")),
                "baseline_call_disagreement": bool(baseline.get("call_disagreement")),
                "reliability_signal_score": _float_or_none(reliability.get("score")),
            })
    return sorted(rows, key=lambda row: (row["panel_id"], row["gene"], row["edge_id"]))


def _rows_by_gene(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        out[row["gene"]].append(row)
    return dict(out)


def _visible_schema() -> dict[str, Any]:
    return {
        "source": "scFoundation_neighbor_edge_support",
        "signal_scope": "readout_gene_specific",
        "readout_gene_display": "model-visible gene label",
        "neighbor_count": "int",
        "same_readout_gene_neighbor_count": "int",
        "neighbor_embedding_distance": {
            "mean": "float|null",
            "min": "float|null",
            "max": "float|null",
        },
        "neighbor_sfm_call_agreement_rate": "float|null",
        "neighbor_sfm_call_disagreement_rate": "float|null",
        "neighbor_baseline_disagreement_rate": "float|null",
        "calibration_status": "unverified_proxy_not_calibrated",
        "limitations": [
            "not_a_calibrated_uncertainty",
            "does_not_contain_hidden_labels",
            "neighbor_similarity_may_not_equal_error_risk",
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


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def _tail(text: str, max_lines: int = 80) -> list[str]:
    return text.splitlines()[-max_lines:]


def _walk_json(value: Any, path: tuple[Any, ...] = ()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_json(item, (*path, key))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from _walk_json(item, (*path, idx))
    else:
        yield path, value


def _find_forbidden_visible_keys(value: Any, path: tuple[Any, ...] = ()) -> list[str]:
    hits = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = (*path, key)
            if key in FORBIDDEN_VISIBLE_KEYS:
                hits.append(".".join(map(str, child_path)))
            hits.extend(_find_forbidden_visible_keys(item, child_path))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            hits.extend(_find_forbidden_visible_keys(item, (*path, idx)))
    return hits


def _euclidean(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError("embedding dimensions do not match")
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _roc_auc(pairs: list[tuple[float, int]]) -> float | None:
    pairs = [(score, label) for score, label in pairs if _finite(score)]
    if not pairs:
        return None
    positives = sum(label for _, label in pairs)
    negatives = len(pairs) - positives
    if positives == 0 or negatives == 0:
        return None
    sorted_pairs = sorted(pairs, key=lambda pair: pair[0])
    rank_sum_positive = 0.0
    idx = 0
    while idx < len(sorted_pairs):
        end = idx + 1
        while end < len(sorted_pairs) and sorted_pairs[end][0] == sorted_pairs[idx][0]:
            end += 1
        avg_rank = (idx + 1 + end) / 2
        labels = [label for _, label in sorted_pairs[idx:end]]
        rank_sum_positive += avg_rank * sum(labels)
        idx = end
    return (rank_sum_positive - positives * (positives + 1) / 2) / (positives * negatives)


def _mean(values) -> float | None:
    vals = [float(value) for value in values if _finite(value)]
    return sum(vals) / len(vals) if vals else None


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not math.isnan(float(value))


def _float_or_none(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if not math.isnan(out) else None


def _none_to_nan(value: float | None) -> float | None:
    return float(value) if value is not None else None


def _round(value: float | int | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    if math.isnan(float(value)):
        return None
    return round(float(value), digits)
