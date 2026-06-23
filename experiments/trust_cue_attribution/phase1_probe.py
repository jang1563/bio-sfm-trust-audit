"""Phase 1 true-SFM feasibility probes.

The probe is intentionally lightweight: it checks files, directories, import
availability, and adapter-contract readiness without loading model checkpoints
or running inference.
"""

from __future__ import annotations

import importlib.util
import json
import os
import platform
import sys
from pathlib import Path
from typing import Any

try:
    from .adapters import get_adapter_contract
except ImportError:  # direct script/test execution from this directory
    from adapters import get_adapter_contract


SCFOUNDATION_SOURCE_ANCHORS = [
    {
        "label": "official_repo",
        "url": "https://github.com/biomap-research/scFoundation",
        "accessed": "2026-06-18",
        "notes": [
            "Repository exposes model, GEARS, preprocessing, mapping, annotation, and downstream task folders.",
            "README says pretrained weight and code instructions are in the model folder.",
            "README says GEARS perturbation code commands are under GEARS/run_sh.",
            "README notes old Biomap API platform was discontinued on 2024-04-30 and points users to aigp.biomap.com.",
        ],
    },
    {
        "label": "intermediate_layer_motivation",
        "url": "https://arxiv.org/abs/2604.14838",
        "accessed": "2026-06-18",
        "notes": [
            "Recent layer-wise work motivates not defaulting blindly to final-layer embeddings.",
            "Phase 1 should preserve layer or representation summaries when available.",
        ],
    },
]

RECOMMENDED_MODULES = [
    "numpy",
    "pandas",
    "scipy",
    "torch",
    "yaml",
    "tqdm",
    "anndata",
    "scanpy",
]


def build_scfoundation_feasibility(
    *,
    scfoundation_dir: str | None = None,
    checkpoint: str | None = None,
    input_data: str | None = None,
    gene_index: str | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """Return a JSON-serializable scFoundation feasibility report."""
    contract = get_adapter_contract("ScFoundationAdapter").describe()
    repo = _path_record(
        "scfoundation_dir",
        scfoundation_dir,
        required=True,
        kind="dir",
        description="local checkout or staged copy of biomap-research/scFoundation",
    )
    inferred_gene_index = None
    if scfoundation_dir:
        inferred_gene_index = str(Path(scfoundation_dir) / "OS_scRNA_gene_index.19264.tsv")
    gene_index_path = gene_index or inferred_gene_index

    path_checks = [
        repo,
        _path_record("repo_readme", _join(scfoundation_dir, "README.md"), True, "file", "official repository README"),
        _path_record("repo_model_dir", _join(scfoundation_dir, "model"), True, "dir", "pretrained model and embedding inference instructions"),
        _path_record("repo_gears_dir", _join(scfoundation_dir, "GEARS"), False, "dir", "downstream perturbation code bridge"),
        _path_record("repo_gears_run_sh", _join(scfoundation_dir, "GEARS", "run_sh"), False, "any", "GEARS command examples"),
        _path_record("gene_index", gene_index_path, True, "file", "scFoundation gene vocabulary mapping"),
        _path_record("checkpoint", checkpoint, True, "file", "pretrained checkpoint or staged model weight"),
        _path_record("phase1_input_data", input_data, True, "file", "single-cell or perturbation dataset for adapter smoke run"),
        _path_record("phase1_output_dir", output_dir, False, "dir", "destination for Phase 1 generated JSONL artifacts"),
    ]
    module_checks = [
        {
            "module": module,
            "available": importlib.util.find_spec(module) is not None,
            "required_for_probe": False,
        }
        for module in RECOMMENDED_MODULES
    ]
    preflight_checks = _contract_preflight_checks(contract, path_checks)
    status = _readiness_status(path_checks, preflight_checks)
    return {
        "phase": "phase1",
        "adapter": "ScFoundationAdapter",
        "status": status,
        "claim_boundary": contract["claim_boundary"],
        "compute_target": contract["compute_target"],
        "python": {
            "executable": sys.executable,
            "version": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "source_anchors": SCFOUNDATION_SOURCE_ANCHORS,
        "path_checks": path_checks,
        "module_checks": module_checks,
        "contract_preflight_checks": preflight_checks,
        "next_actions": _next_actions(status, path_checks),
    }


def write_scfoundation_feasibility(out: str, **kwargs) -> dict[str, Any]:
    report = build_scfoundation_feasibility(**kwargs)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return report


def _join(base: str | None, *parts: str) -> str | None:
    if not base:
        return None
    return str(Path(base).joinpath(*parts))


def _path_record(label: str, path: str | None, required: bool, kind: str, description: str) -> dict[str, Any]:
    exists = False
    matches_kind = False
    if path:
        candidate = Path(path)
        exists = candidate.exists()
        if kind == "file":
            matches_kind = candidate.is_file()
        elif kind == "dir":
            matches_kind = candidate.is_dir()
        elif kind == "any":
            matches_kind = exists
        else:
            raise ValueError(f"unknown path check kind {kind!r}")
    return {
        "label": label,
        "path": path,
        "required": required,
        "kind": kind,
        "exists": exists,
        "matches_kind": matches_kind,
        "ready": (not required) or matches_kind,
        "description": description,
    }


def _contract_preflight_checks(contract: dict[str, Any], path_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    present = {row["label"]: row["ready"] for row in path_checks}
    internal_signal_fields = contract.get("internal_signal_fields", [])
    hidden_fields = contract.get("hidden_fields", [])
    return [
        {
            "check": "runs_on_cayuga_or_expanse_without_local_large_memory_use",
            "ready": contract.get("compute_target") == "cayuga_or_expanse",
        },
        {
            "check": "scfoundation_repo_available",
            "ready": present.get("scfoundation_dir", False) and present.get("repo_model_dir", False),
        },
        {
            "check": "gene_vocabulary_mapping_available",
            "ready": present.get("gene_index", False),
        },
        {
            "check": "checkpoint_available",
            "ready": present.get("checkpoint", False),
        },
        {
            "check": "phase1_input_data_available",
            "ready": present.get("phase1_input_data", False),
        },
        {
            "check": "produces_at_least_one_internal_signal_summary_field",
            "ready": bool(internal_signal_fields),
        },
        {
            "check": "hidden_fields_include_truth_and_reward_guards",
            "ready": any("held-out truth" in item for item in hidden_fields)
            and any("reward" in item for item in hidden_fields),
        },
    ]


def _readiness_status(path_checks: list[dict[str, Any]], preflight_checks: list[dict[str, Any]]) -> str:
    missing_required = [row for row in path_checks if row["required"] and not row["ready"]]
    failed_preflight = [row for row in preflight_checks if not row["ready"]]
    if not missing_required and not failed_preflight:
        return "ready_for_hpc_smoke"
    if missing_required:
        return "blocked_missing_required_artifacts"
    return "blocked_contract_preflight"


def _next_actions(status: str, path_checks: list[dict[str, Any]]) -> list[str]:
    if status == "ready_for_hpc_smoke":
        return [
            "Run a Cayuga/Expanse adapter smoke job that produces phase1_panels.jsonl and phase1_cue_packets.jsonl.",
            "Do not run full LLM calls until the adapter smoke output passes schema checks.",
        ]
    missing = [row["label"] for row in path_checks if row["required"] and not row["ready"]]
    return [
        f"Stage missing required artifacts: {', '.join(missing)}.",
        "Keep heavy model setup and inference on Cayuga or Expanse.",
        "After staging artifacts, rerun phase1-feasibility and commit the compact report only.",
    ]
