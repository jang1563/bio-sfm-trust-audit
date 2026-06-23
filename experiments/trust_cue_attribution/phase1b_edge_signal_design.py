"""Phase 1B edge-level scFoundation signal design gate."""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from statistics import median
from typing import Any

try:
    from .phase1a_signal_validity import selected_panels_from_manifest
except ImportError:  # direct script/test execution from this directory
    from phase1a_signal_validity import selected_panels_from_manifest


NEIGHBOR_COVERAGE_THRESHOLDS = [1, 3, 5, 10, 20]


def phase1b_edge_signal_design(
    panels: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Build a data-driven design brief for the next edge-level signal."""
    selected_panels = selected_panels_from_manifest(manifest)
    selected_ids = {str(panel["panel_id"]) for panel in selected_panels}
    rows = _selected_edge_rows(panels, selected_ids)
    reuse = _readout_gene_reuse(panels)
    feasibility = _feasibility(rows, reuse)
    candidates = _candidate_signals(feasibility)
    recommendation = _recommendation(feasibility, candidates)

    return {
        "phase": "phase1b",
        "status": "edge_signal_design_ready",
        "claim_boundary": (
            "Design gate only; no new LLM call, no full Phase 1B result, and "
            "no claim that scFoundation internals are used faithfully."
        ),
        "why_this_exists": (
            "Phase 1A showed that panel-level scFoundation cards are too coarse "
            "for edge-level verify/trust decisions."
        ),
        "scope": {
            "selected_panels": len(selected_ids),
            "selected_edges": len(rows),
            "selected_unique_readout_genes": len({row["gene"] for row in rows}),
            "full_panels": len(panels),
            "full_unique_readout_genes": len(reuse),
        },
        "edge_reuse_feasibility": feasibility,
        "proposed_model_visible_schema": _model_visible_schema(),
        "candidate_signal_routes": candidates,
        "recommended_route": recommendation,
        "next_phase1b_pilot": _pilot_plan(),
        "acceptance_gates_before_llm_spend": _acceptance_gates(),
    }


def write_phase1b_edge_signal_design(
    *,
    panels: list[dict[str, Any]],
    manifest: dict[str, Any],
    out: str,
) -> dict[str, Any]:
    report = phase1b_edge_signal_design(panels, manifest)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return report


def _selected_edge_rows(panels: list[dict[str, Any]], selected_ids: set[str]) -> list[dict[str, str]]:
    rows = []
    for panel in panels:
        panel_id = str(panel.get("panel_id"))
        if panel_id not in selected_ids:
            continue
        for edge in panel.get("edges", []):
            rows.append({
                "panel_id": panel_id,
                "gene": str(edge.get("gene")),
                "edge_id": str(edge.get("edge_id", f"{panel_id}::{edge.get('gene')}")),
            })
    return sorted(rows, key=lambda row: (row["panel_id"], row["gene"], row["edge_id"]))


def _readout_gene_reuse(panels: list[dict[str, Any]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for panel in panels:
        panel_id = str(panel.get("panel_id"))
        for edge in panel.get("edges", []):
            out[str(edge.get("gene"))].add(panel_id)
    return dict(out)


def _feasibility(
    rows: list[dict[str, str]],
    reuse: dict[str, set[str]],
) -> dict[str, Any]:
    other_panel_counts = [
        len(reuse.get(row["gene"], set()) - {row["panel_id"]})
        for row in rows
    ]
    coverage = {
        f"edges_with_at_least_{threshold}_other_panels_same_gene": _coverage(other_panel_counts, threshold)
        for threshold in NEIGHBOR_COVERAGE_THRESHOLDS
    }
    gene_counts = Counter(row["gene"] for row in rows)
    return {
        "rationale": (
            "Neighbor-style edge signals are feasible when the same readout gene "
            "appears in other perturbation panels, allowing gene-specific support "
            "without using the target edge's hidden correctness label."
        ),
        "selected_edges": len(rows),
        "selected_unique_readout_genes": len(gene_counts),
        "other_panel_same_gene_counts": {
            "min": min(other_panel_counts) if other_panel_counts else 0,
            "median": median(other_panel_counts) if other_panel_counts else 0,
            "max": max(other_panel_counts) if other_panel_counts else 0,
        },
        "coverage": coverage,
        "top_selected_readout_genes": [
            {"gene": gene, "selected_edge_count": count}
            for gene, count in gene_counts.most_common(10)
        ],
    }


def _candidate_signals(feasibility: dict[str, Any]) -> list[dict[str, Any]]:
    coverage10 = feasibility["coverage"]["edges_with_at_least_10_other_panels_same_gene"]["fraction"]
    neighbor_status = "recommended_for_hpc_prototype" if coverage10 >= 0.8 else "needs_more_gene_reuse"
    return [
        {
            "name": "scfoundation_neighbor_edge_support",
            "status": neighbor_status,
            "evidence_unit": "(perturbation, readout_gene)",
            "model_dependency": "scFoundation panel/cell embeddings plus same-readout-gene neighbor retrieval",
            "model_visible_fields": [
                "neighbor_count",
                "same_readout_gene_neighbor_count",
                "neighbor_embedding_distance_summary",
                "neighbor_sfm_call_agreement_rate",
                "neighbor_baseline_disagreement_rate",
                "calibration_status",
            ],
            "hidden_for_scoring_only": [
                "target edge correctness",
                "held-out truth labels",
                "target edge measured assay stats",
                "reward",
            ],
            "why_it_matches_the_task": (
                "It varies by readout gene within a panel, so it can support "
                "edge-level verify/trust decisions."
            ),
            "main_risk": (
                "Nearest neighbors may encode experimental similarity without "
                "being calibrated reliability evidence."
            ),
        },
        {
            "name": "masked_readout_gene_prediction_delta",
            "status": "blocked_until_model_output_probe",
            "evidence_unit": "(perturbation, readout_gene)",
            "model_dependency": "scFoundation must expose a gene-level prediction or reconstruction path",
            "model_visible_fields": [
                "predicted_readout_gene_delta",
                "prediction_uncertainty_proxy",
                "gene_in_vocabulary",
                "calibration_status",
            ],
            "hidden_for_scoring_only": [
                "measured readout gene DE label",
                "reward",
            ],
            "why_it_matches_the_task": "It is directly aligned to the readout gene.",
            "main_risk": "The current official smoke path only proved embeddings, not gene prediction output.",
        },
        {
            "name": "gene_token_attribution_or_gradient",
            "status": "research_probe_needed",
            "evidence_unit": "(perturbation, readout_gene)",
            "model_dependency": "checkpoint instrumentation for readout-gene token attribution",
            "model_visible_fields": [
                "readout_gene_attribution_rank",
                "readout_gene_attribution_score",
                "layer_or_head_summary_if_available",
                "calibration_status",
            ],
            "hidden_for_scoring_only": ["held-out truth labels", "reward"],
            "why_it_matches_the_task": "It can test whether inside-model features align with a specific gene decision.",
            "main_risk": "Attribution can be unstable and easy for the LLM to overinterpret.",
        },
        {
            "name": "panel_signal_plus_edge_baseline_fusion",
            "status": "diagnostic_control_only",
            "evidence_unit": "(perturbation, readout_gene)",
            "model_dependency": "current panel signal plus existing baseline disagreement",
            "model_visible_fields": [
                "panel_internal_signal_summary",
                "edge_baseline_disagreement",
                "calibration_status",
            ],
            "hidden_for_scoring_only": ["held-out truth labels", "reward"],
            "why_it_matches_the_task": "It tests whether edge-level formatting alone improves routing.",
            "main_risk": "It is not clean evidence that the LLM used SFM internals faithfully.",
        },
    ]


def _recommendation(feasibility: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    recommended = next(candidate for candidate in candidates if candidate["name"] == "scfoundation_neighbor_edge_support")
    coverage10 = feasibility["coverage"]["edges_with_at_least_10_other_panels_same_gene"]["fraction"]
    return {
        "route": recommended["name"],
        "decision": recommended["status"],
        "reason": (
            "The same readout gene usually appears in many other panels, so a "
            "nearest-neighbor, readout-gene-specific cue is feasible without "
            "using the target edge's hidden truth."
        ),
        "coverage_at_10_other_panels_same_gene": coverage10,
        "why_not_masked_prediction_first": (
            "The current scFoundation smoke path verified embeddings only; a "
            "gene-prediction path must be probed separately."
        ),
    }


def _model_visible_schema() -> dict[str, Any]:
    return {
        "evidence_packet.genes[].edge_internal_signal_summary": {
            "source": "scFoundation_neighbor_edge_support",
            "signal_scope": "readout_gene_specific",
            "readout_gene_display": "model-visible gene label",
            "neighbor_count": "int",
            "same_readout_gene_neighbor_count": "int",
            "neighbor_embedding_distance": {
                "mean": "float",
                "min": "float",
                "max": "float",
            },
            "neighbor_sfm_call_agreement_rate": "float",
            "neighbor_baseline_disagreement_rate": "float",
            "calibration_status": "unverified_proxy_not_calibrated",
            "limitations": [
                "not_a_calibrated_uncertainty",
                "does_not_contain_hidden_labels",
                "neighbor_similarity_may_not_equal_error_risk",
            ],
        }
    }


def _pilot_plan() -> dict[str, Any]:
    return {
        "phase": "phase1b_small_pilot",
        "cue_conditions": [
            "no_internal_signal",
            "scfoundation_edge_neighbor_signal_shown",
            "shuffled_readout_gene_signal_shown",
            "panel_signal_card_control",
        ],
        "scope": "reuse the 12 Phase 1A selected panels first",
        "llm_gate": "run only after leakage checks and edge-signal validity diagnostics pass",
        "primary_pre_llm_metric": "edge-level AUROC for GEARS wrongness versus current panel-card AUROC",
    }


def _acceptance_gates() -> list[dict[str, Any]]:
    return [
        {
            "gate": "leakage_check",
            "requirement": "model-visible edge signal contains no truth, correctness, reward, or target raw assay stats",
        },
        {
            "gate": "within_panel_variation",
            "requirement": "edge signal varies across readout genes within most selected panels",
        },
        {
            "gate": "edge_signal_validity",
            "requirement": "edge-level signal beats the panel-card AUROC directionally before LLM spend",
        },
        {
            "gate": "placebo_control",
            "requirement": "include shuffled readout-gene signal with matched style and missing truth labels",
        },
        {
            "gate": "claim_boundary",
            "requirement": "report as method-development until a scored LLM pilot separates real signal from placebo",
        },
    ]


def _coverage(counts: list[int], threshold: int) -> dict[str, Any]:
    numerator = sum(count >= threshold for count in counts)
    denominator = len(counts)
    return {
        "count": numerator,
        "denominator": denominator,
        "fraction": round(numerator / denominator, 6) if denominator else 0.0,
    }
