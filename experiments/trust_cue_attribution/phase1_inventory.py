"""Phase 1 scFoundation input compatibility inventory.

This module checks whether a staged single-cell input can be mapped onto the
scFoundation gene vocabulary. It does not load model weights or run inference.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


SCFOUNDATION_REQUIRED_INFERENCE_MODULES = [
    "numpy",
    "pandas",
    "scipy",
    "torch",
    "einops",
    "scanpy",
    "local_attention",
]


def build_scfoundation_input_inventory(
    *,
    input_data: str,
    gene_index: str,
    min_overlap: int = 500,
    sample_gene_count: int = 12,
) -> dict[str, Any]:
    """Return a compact compatibility report for a Phase 1 input h5ad."""
    module_checks = _module_checks()
    gene_index_record = _path_record(gene_index, "file")
    input_record = _path_record(input_data, "file")

    vocabulary = _read_gene_index(gene_index) if gene_index_record["matches_kind"] else []
    h5ad = _read_h5ad_metadata(input_data, sample_gene_count=sample_gene_count) if input_record["matches_kind"] else {
        "readable": False,
        "error": "input_data_missing",
    }
    input_genes = h5ad.get("gene_names", []) if h5ad.get("readable") else []
    overlap = summarize_gene_overlap(input_genes, vocabulary)

    status = _inventory_status(
        gene_index_ready=gene_index_record["matches_kind"],
        input_ready=input_record["matches_kind"],
        h5ad_readable=bool(h5ad.get("readable")),
        overlap_count=overlap["overlap_count"],
        min_overlap=min_overlap,
    )
    return {
        "phase": "phase1",
        "adapter": "ScFoundationAdapter",
        "status": status,
        "claim_boundary": "input compatibility inventory only; no scFoundation inference or LLM trust claim",
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "paths": {
            "input_data": input_record,
            "gene_index": gene_index_record,
        },
        "module_checks": module_checks,
        "h5ad": _redact_gene_names(h5ad),
        "gene_vocabulary": {
            "gene_count": len(vocabulary),
            "sample": vocabulary[:sample_gene_count],
        },
        "gene_overlap": overlap,
        "quality_warnings": _quality_warnings(overlap),
        "thresholds": {
            "min_overlap": min_overlap,
        },
        "next_actions": _next_actions(status, module_checks),
    }


def write_scfoundation_input_inventory(out: str, **kwargs) -> dict[str, Any]:
    report = build_scfoundation_input_inventory(**kwargs)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return report


def summarize_gene_overlap(input_genes: Iterable[str], vocabulary_genes: Iterable[str]) -> dict[str, Any]:
    input_set = {_normalize_gene(gene) for gene in input_genes if _normalize_gene(gene)}
    vocab_set = {_normalize_gene(gene) for gene in vocabulary_genes if _normalize_gene(gene)}
    overlap = input_set & vocab_set
    input_count = len(input_set)
    vocab_count = len(vocab_set)
    return {
        "input_gene_count": input_count,
        "vocabulary_gene_count": vocab_count,
        "overlap_count": len(overlap),
        "missing_vocabulary_gene_count": max(vocab_count - len(overlap), 0),
        "extra_input_gene_count": max(input_count - len(overlap), 0),
        "overlap_fraction_of_input": _safe_fraction(len(overlap), input_count),
        "vocabulary_coverage_fraction": _safe_fraction(len(overlap), vocab_count),
    }


def _read_gene_index(path: str) -> list[str]:
    with open(path, newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if not reader.fieldnames:
            return []
        gene_field = "gene_name" if "gene_name" in reader.fieldnames else reader.fieldnames[0]
        return [row[gene_field] for row in reader if row.get(gene_field)]


def _read_h5ad_metadata(path: str, *, sample_gene_count: int) -> dict[str, Any]:
    if importlib.util.find_spec("anndata") is None:
        fallback = _read_h5ad_metadata_with_h5dump(path, sample_gene_count=sample_gene_count)
        if fallback["readable"]:
            fallback["anndata_error"] = "missing_anndata"
            return fallback
        fallback["error"] = f"missing_anndata; {fallback.get('error')}"
        return fallback
    try:
        import anndata as ad  # type: ignore
        import scipy.sparse  # type: ignore

        adata = ad.read_h5ad(path, backed="r")
        gene_names = _h5ad_gene_names(adata)
        x_shape = list(adata.shape)
        x_is_sparse = scipy.sparse.issparse(adata.X)
        obs_columns = list(adata.obs.columns)
        var_columns = list(adata.var.columns)
        obs_names_sample = [str(value) for value in list(adata.obs_names[:sample_gene_count])]
        adata.file.close()
        return {
            "readable": True,
            "format": "h5ad",
            "n_obs": int(x_shape[0]),
            "n_vars": int(x_shape[1]),
            "x_is_sparse": bool(x_is_sparse),
            "obs_columns": obs_columns,
            "var_columns": var_columns,
            "obs_names_sample": obs_names_sample,
            "gene_names": gene_names,
            "gene_names_sample": gene_names[:sample_gene_count],
        }
    except Exception as exc:  # pragma: no cover - exact h5ad failures are environment-specific.
        fallback = _read_h5ad_metadata_with_h5dump(path, sample_gene_count=sample_gene_count)
        if fallback["readable"]:
            fallback["anndata_error"] = f"{type(exc).__name__}: {exc}"
            return fallback
        return {
            "readable": False,
            "error": f"{type(exc).__name__}: {exc}",
            "h5dump_fallback_error": fallback.get("error"),
        }


def _read_h5ad_metadata_with_h5dump(path: str, *, sample_gene_count: int) -> dict[str, Any]:
    h5dump = shutil.which("h5dump")
    if not h5dump:
        return {
            "readable": False,
            "error": "missing_h5dump",
        }
    try:
        var_dump = subprocess.run(
            [h5dump, "-d", "/var/_index", path],
            check=True,
            capture_output=True,
            text=True,
        )
        obs_header = subprocess.run(
            [h5dump, "-H", "-d", "/obs/_index", path],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        return {
            "readable": False,
            "error": f"h5dump_{type(exc).__name__}: {exc}",
        }
    gene_names = _quoted_h5dump_strings(var_dump.stdout)
    return {
        "readable": True,
        "format": "h5ad",
        "reader": "h5dump",
        "n_obs": _h5dump_dataspace_size(obs_header.stdout),
        "n_vars": len(gene_names),
        "x_is_sparse": None,
        "obs_columns": [],
        "var_columns": ["_index"],
        "obs_names_sample": [],
        "gene_names": gene_names,
        "gene_names_sample": gene_names[:sample_gene_count],
    }


def _h5ad_gene_names(adata: Any) -> list[str]:
    if "gene_name" in adata.var.columns:
        values = adata.var["gene_name"].astype(str).tolist()
    elif "gene_names" in adata.var.columns:
        values = adata.var["gene_names"].astype(str).tolist()
    else:
        values = [str(value) for value in adata.var_names.tolist()]
    return values


def _redact_gene_names(h5ad: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(h5ad)
    redacted.pop("gene_names", None)
    return redacted


def _module_checks() -> list[dict[str, Any]]:
    rows = [
        {
            "module": module,
            "available": importlib.util.find_spec(module) is not None,
            "required_for_scFoundation_inference": True,
        }
        for module in SCFOUNDATION_REQUIRED_INFERENCE_MODULES
    ]
    rows.append({
        "module": "h5dump",
        "available": shutil.which("h5dump") is not None,
        "required_for_scFoundation_inference": False,
    })
    return rows


def _inventory_status(
    *,
    gene_index_ready: bool,
    input_ready: bool,
    h5ad_readable: bool,
    overlap_count: int,
    min_overlap: int,
) -> str:
    if not gene_index_ready:
        return "blocked_missing_gene_index"
    if not input_ready:
        return "blocked_missing_input_data"
    if not h5ad_readable:
        return "blocked_input_unreadable"
    if overlap_count < min_overlap:
        return "blocked_low_gene_overlap"
    return "ready_for_adapter_smoke"


def _next_actions(status: str, module_checks: list[dict[str, Any]]) -> list[str]:
    missing_modules = [row["module"] for row in module_checks if not row["available"]]
    if status == "ready_for_adapter_smoke":
        actions = [
            "Run a minimal scFoundation adapter smoke job that writes internal-signal summaries for a tiny input subset.",
            "Use this HVG/subset input for wiring only; use a fuller gene-space input before scientific interpretation.",
            "Keep hidden truth, reward, and scorer fields out of model-visible cue packets.",
        ]
        if missing_modules:
            actions.append(f"Before full inference, install or select an environment with: {', '.join(missing_modules)}.")
        return actions
    if status == "blocked_input_unreadable":
        return ["Use a Python environment with anndata/scanpy support or choose a readable h5ad input."]
    if status == "blocked_low_gene_overlap":
        return ["Choose an input dataset with gene symbols that overlap the scFoundation vocabulary or add a gene-symbol mapping step."]
    return ["Stage the missing Phase 1 input artifact on Cayuga or Expanse and rerun the inventory."]


def _quality_warnings(overlap: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    input_fraction = overlap.get("overlap_fraction_of_input")
    vocab_fraction = overlap.get("vocabulary_coverage_fraction")
    if input_fraction is not None and input_fraction < 0.8:
        warnings.append("low_fraction_of_input_genes_mapped_to_scfoundation_vocabulary")
    if vocab_fraction is not None and vocab_fraction < 0.1:
        warnings.append("low_fraction_of_scfoundation_vocabulary_observed_input_is_likely_hvg_or_subset")
    return warnings


def _path_record(path: str, kind: str) -> dict[str, Any]:
    candidate = Path(path)
    exists = candidate.exists()
    if kind == "file":
        matches_kind = candidate.is_file()
    elif kind == "dir":
        matches_kind = candidate.is_dir()
    else:
        raise ValueError(f"unknown path kind {kind!r}")
    return {
        "path": path,
        "exists": exists,
        "kind": kind,
        "matches_kind": matches_kind,
    }


def _normalize_gene(gene: object) -> str:
    return str(gene).strip().upper()


def _safe_fraction(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _quoted_h5dump_strings(text: str) -> list[str]:
    in_data = False
    values: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("DATA {"):
            in_data = True
            continue
        if in_data and stripped == "}":
            break
        if in_data:
            values.extend(re.findall(r'"([^"]*)"', stripped))
    return values


def _h5dump_dataspace_size(text: str) -> int | None:
    match = re.search(r"DATASPACE\s+SIMPLE\s+\{\s+\(\s*(\d+)\s*\)", text)
    if not match:
        return None
    return int(match.group(1))
