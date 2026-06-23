"""Phase 1A signal granularity diagnostics.

The Phase 1A reward is edge-level, but the first scFoundation signal card was
panel-level. This diagnostic checks whether panel-constant signals can plausibly
support per-gene routing decisions before we spend on a larger LLM matrix.
"""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from typing import Any

try:
    from .phase1a_signal_validity import (
        PRIMARY_SIGNAL_FIELDS,
        SIGNAL_FIELDS,
        selected_panels_from_manifest,
    )
except ImportError:  # direct script/test execution from this directory
    from phase1a_signal_validity import (
        PRIMARY_SIGNAL_FIELDS,
        SIGNAL_FIELDS,
        selected_panels_from_manifest,
    )


REFERENCE_EDGE_SCORE_FIELDS = [
    "reliability_signal_score",
    "baseline_abs_fm_minus_baseline",
    "baseline_call_disagreement",
    "sfm_abs_log2fc",
]


def phase1a_signal_granularity(
    panels: list[dict[str, Any]],
    manifest: dict[str, Any],
    panel_signal_report: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate panel-constant signal scores as edge-level wrongness predictors."""
    selected_panels = selected_panels_from_manifest(manifest)
    selected_ids = {str(panel["panel_id"]) for panel in selected_panels}
    selected_summary = {str(panel["panel_id"]): panel for panel in selected_panels}
    signal_by_panel = _panel_signals(panel_signal_report)
    rows = _edge_rows(panels, selected_ids, selected_summary, signal_by_panel)
    by_panel = _panel_mixture(rows)
    aucs = _aucs(rows)
    decision = _decision(rows, by_panel, aucs)

    return {
        "phase": "phase1a",
        "status": "signal_granularity_ready",
        "claim_boundary": (
            "Exploratory granularity diagnostic only; no full Phase 1A, "
            "true-SFM trust, or biological interpretation claim."
        ),
        "primary_question": (
            "Is a panel-level scFoundation signal granular enough for "
            "edge-level verify/trust decisions?"
        ),
        "scope": {
            "selected_panels": len(selected_ids),
            "matched_panels": int(by_panel["panel_count"]),
            "edge_rows": len(rows),
            "wrong_edges": sum(int(row["sfm_wrong"]) for row in rows),
            "correct_edges": sum(1 - int(row["sfm_wrong"]) for row in rows),
            "primary_panel_signal_fields": PRIMARY_SIGNAL_FIELDS,
            "reference_edge_score_fields": REFERENCE_EDGE_SCORE_FIELDS,
        },
        "panel_mixture": _round_nested(by_panel),
        "edge_level_auc": _round_nested(aucs),
        "decision": decision,
        "interpretation": {
            "short_read": decision["short_read"],
            "method_note": (
                "Panel-constant scores give every gene in a perturbation the "
                "same risk value, so mixed panels expose a unit mismatch."
            ),
            "next_design_step": (
                "Build the next scFoundation cue around readout-gene-specific "
                "or task-aligned evidence, not only perturbation-level distance."
            ),
        },
    }


def write_phase1a_signal_granularity(
    *,
    panels: list[dict[str, Any]],
    manifest: dict[str, Any],
    panel_signal_report: dict[str, Any],
    out: str,
) -> dict[str, Any]:
    report = phase1a_signal_granularity(panels, manifest, panel_signal_report)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return report


def _panel_signals(report: dict[str, Any]) -> dict[str, dict[str, float]]:
    panels = report.get("panel_signals", {}).get("panels", {})
    out: dict[str, dict[str, float]] = {}
    for panel_id, signal in panels.items():
        if not isinstance(signal, dict):
            continue
        values = {
            field: float(signal[field])
            for field in SIGNAL_FIELDS
            if _finite(signal.get(field))
        }
        if values:
            out[str(panel_id)] = values
    return out


def _edge_rows(
    panels: list[dict[str, Any]],
    selected_ids: set[str],
    selected_summary: dict[str, dict[str, Any]],
    signal_by_panel: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    rows = []
    for panel in panels:
        panel_id = str(panel.get("panel_id"))
        if panel_id not in selected_ids or panel_id not in signal_by_panel:
            continue
        summary = selected_summary.get(panel_id, {})
        panel_wrong_rate = _float_or_none(summary.get("wrong_rate"))
        if panel_wrong_rate is None:
            edges = panel.get("edges", [])
            panel_wrong_rate = _mean(1 - int(edge["fm"]["correct"]) for edge in edges)
        for edge in panel.get("edges", []):
            baseline = edge.get("baseline_signal", {})
            reliability = edge.get("reliability_signal", {})
            row = {
                "panel_id": panel_id,
                "gene": str(edge.get("gene")),
                "sfm_wrong": int(not bool(edge.get("fm", {}).get("correct"))),
                "panel_wrong_rate_hidden_oracle": panel_wrong_rate,
                "reliability_signal_score": _float_or_none(reliability.get("score")),
                "baseline_abs_fm_minus_baseline": _float_or_none(baseline.get("abs_fm_minus_baseline")),
                "baseline_call_disagreement": int(bool(baseline.get("call_disagreement"))),
                "sfm_abs_log2fc": abs(float(edge.get("fm", {}).get("log2fc", 0.0))),
            }
            row.update(signal_by_panel[panel_id])
            rows.append(row)
    return sorted(rows, key=lambda row: (row["panel_id"], row["gene"]))


def _panel_mixture(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["panel_id"]].append(row)
    panels = []
    mixed = 0
    for panel_id, panel_rows in sorted(grouped.items()):
        wrong = sum(int(row["sfm_wrong"]) for row in panel_rows)
        correct = len(panel_rows) - wrong
        is_mixed = wrong > 0 and correct > 0
        mixed += int(is_mixed)
        panels.append({
            "panel_id": panel_id,
            "edges": len(panel_rows),
            "wrong_edges": wrong,
            "correct_edges": correct,
            "wrong_rate": wrong / len(panel_rows) if panel_rows else 0.0,
            "mixed_correct_and_wrong": is_mixed,
        })
    return {
        "panels": panels,
        "mixed_panel_count": mixed,
        "panel_count": len(panels),
        "mixed_panel_fraction": mixed / len(panels) if panels else 0.0,
    }


def _aucs(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    fields = ["panel_wrong_rate_hidden_oracle", *SIGNAL_FIELDS, *REFERENCE_EDGE_SCORE_FIELDS]
    out = {}
    for field in fields:
        pairs = [
            (float(row[field]), int(row["sfm_wrong"]))
            for row in rows
            if _finite(row.get(field))
        ]
        auc = _roc_auc(pairs)
        out[field] = {
            "n": len(pairs),
            "auc_higher_score_means_more_wrong": auc,
            "auc_direction_invariant": max(auc, 1 - auc) if auc is not None else None,
        }
    return out


def _decision(
    rows: list[dict[str, Any]],
    by_panel: dict[str, Any],
    aucs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    primary = {
        field: aucs.get(field, {}).get("auc_higher_score_means_more_wrong")
        for field in PRIMARY_SIGNAL_FIELDS
    }
    best_primary = _best_auc(primary)
    edge_reference = {
        field: aucs.get(field, {}).get("auc_higher_score_means_more_wrong")
        for field in REFERENCE_EDGE_SCORE_FIELDS
    }
    best_reference = _best_auc(edge_reference)
    mixed_fraction = float(by_panel.get("mixed_panel_fraction", 0.0))

    if not rows:
        scale_decision = "insufficient_edge_overlap"
        reason = "no_matched_edges"
        short_read = "No matched edge rows are available for granularity diagnostics."
    elif mixed_fraction >= 0.75 and (best_primary.get("auc") is None or best_primary["auc"] <= 0.55):
        scale_decision = "edge_level_signal_required"
        reason = "panel_constant_signal_weak_for_edge_wrongness"
        short_read = (
            "The selected panels mostly mix correct and wrong genes, while the "
            "panel-level scFoundation scores weakly predict edge wrongness."
        )
    elif mixed_fraction >= 0.75:
        scale_decision = "redesign_to_edge_level_before_scaling"
        reason = "panel_constant_signal_has_unit_mismatch"
        short_read = (
            "The panel-level signal has some edge-level association but remains "
            "too coarse for per-gene routing."
        )
    else:
        scale_decision = "granularity_not_blocking_but_controls_needed"
        reason = "few_mixed_panels"
        short_read = (
            "Panel-level granularity is less obviously blocking here, but the "
            "signal still needs placebo controls."
        )

    return {
        "scale_decision": scale_decision,
        "reason": reason,
        "mixed_panel_fraction": _round(mixed_fraction),
        "best_primary_panel_signal_auc": best_primary,
        "best_reference_edge_score_auc": best_reference,
        "short_read": short_read,
        "next_actions": [
            "do not scale the current panel-constant scFoundation cue",
            "build readout-gene-specific or task-aligned internal evidence",
            "compare that edge-level cue against baseline-disagreement and shuffled controls",
        ],
    }


def _roc_auc(pairs: list[tuple[float, int]]) -> float | None:
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


def _best_auc(scores: dict[str, float | None]) -> dict[str, Any]:
    candidates = [
        {
            "score_field": field,
            "auc": float(auc),
            "auc_direction_invariant": max(float(auc), 1 - float(auc)),
        }
        for field, auc in scores.items()
        if isinstance(auc, (int, float))
    ]
    if not candidates:
        return {"score_field": None, "auc": None, "auc_direction_invariant": None}
    best = sorted(
        candidates,
        key=lambda item: (-item["auc"], -item["auc_direction_invariant"], item["score_field"]),
    )[0]
    return _round_nested(best)


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not math.isnan(float(value))


def _float_or_none(value: Any) -> float | None:
    return float(value) if _finite(value) else None


def _mean(values) -> float:
    vals = [float(value) for value in values]
    return sum(vals) / len(vals) if vals else 0.0


def _round_nested(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _round_nested(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_round_nested(item) for item in value]
    if isinstance(value, float):
        return _round(value)
    return value


def _round(value: float | int | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)
