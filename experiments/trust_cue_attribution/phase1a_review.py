"""Phase 1A internal-signal pilot review diagnostics."""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from typing import Any

try:
    from .analysis import gene_level_rows, paired_cue_effects
except ImportError:  # direct script/test execution from this directory
    from analysis import gene_level_rows, paired_cue_effects


REAL_SIGNAL_CUE = "scfoundation_internal_signal_shown"
PLACEBO_SIGNAL_CUE = "shuffled_internal_signal_shown"
NO_SIGNAL_CUE = "no_internal_signal"


def phase1a_review(
    panels: list[dict[str, Any]],
    packets: list[dict[str, Any]],
    episodes: list[dict[str, Any]],
    panel_signal_report: dict[str, Any],
    *,
    lam: float = 0.5,
    baseline_cue: str = NO_SIGNAL_CUE,
) -> dict[str, Any]:
    """Review whether real internal signal is specific beyond placebo."""
    rows = gene_level_rows(panels, packets, episodes, lam=lam)
    paired = paired_cue_effects(rows, baseline_cue=baseline_cue)
    cue_metrics = _cue_metrics(rows)
    panel_deltas = _panel_deltas(rows, baseline_cue=baseline_cue)
    panel_signals = _panel_signals(panel_signal_report)
    correlations = _signal_correlations(panel_signals, panel_deltas)

    real = paired.get(REAL_SIGNAL_CUE, {})
    placebo = paired.get(PLACEBO_SIGNAL_CUE, {})
    specificity = _specificity_summary(real, placebo)
    recommendation = _recommendation(specificity)

    return {
        "phase": "phase1a",
        "status": "review_ready",
        "lambda": lam,
        "baseline_cue": baseline_cue,
        "scope": {
            "episodes": len(episodes),
            "gene_rows": len(rows),
            "panels": len({row["panel_id"] for row in rows}),
            "cue_conditions": sorted({row["cue_condition"] for row in rows}),
        },
        "cue_metrics": cue_metrics,
        "paired_effects_vs_baseline": _round_nested(paired),
        "specificity": specificity,
        "panel_deltas": _round_nested(panel_deltas),
        "signal_behavior_correlations": _round_nested(correlations),
        "recommendation": recommendation,
        "interpretation": {
            "short_read": (
                "Real internal signal and shuffled placebo move routing in similar "
                "directions; treat this as cue-sensitivity evidence, not faithful "
                "scFoundation-internal interpretation evidence."
            ),
            "next_design_step": (
                "Sharpen the internal signal into decision-relevant evidence and "
                "add stronger irrelevant-signal controls before scaling."
            ),
        },
    }


def write_phase1a_review(
    *,
    panels: list[dict[str, Any]],
    packets: list[dict[str, Any]],
    episodes: list[dict[str, Any]],
    panel_signal_report: dict[str, Any],
    out: str,
    lam: float = 0.5,
    baseline_cue: str = NO_SIGNAL_CUE,
) -> dict[str, Any]:
    review = phase1a_review(
        panels,
        packets,
        episodes,
        panel_signal_report,
        lam=lam,
        baseline_cue=baseline_cue,
    )
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as handle:
        json.dump(review, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return review


def _cue_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_cue: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cue[str(row["cue_condition"])].append(row)
    out = {}
    for cue, cue_rows in sorted(by_cue.items()):
        n = len(cue_rows)
        out[cue] = {
            "genes": n,
            "accuracy": _mean(row["correct"] for row in cue_rows),
            "assays_per_gene": _mean(row["assay"] for row in cue_rows),
            "net_reward_per_gene": _mean(row["net"] for row in cue_rows),
            "trust_error_rate": _mean(
                int(row["action"] == "trust_sfm" and row["sfm_wrong"]) for row in cue_rows
            ),
            "verify_rate": _mean(int(row["action"] == "verify_assay") for row in cue_rows),
            "default_baseline_rate": _mean(int(row["action"] == "default_baseline") for row in cue_rows),
        }
    return _round_nested(out)


def _panel_deltas(rows: list[dict[str, Any]], *, baseline_cue: str) -> dict[str, dict[str, dict[str, Any]]]:
    by_key = {
        (row["panel_id"], row["gene"], row["cue_condition"]): row
        for row in rows
    }
    cues = sorted({row["cue_condition"] for row in rows if row["cue_condition"] != baseline_cue})
    panels = sorted({row["panel_id"] for row in rows})
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for panel in panels:
        out[panel] = {}
        genes = sorted({row["gene"] for row in rows if row["panel_id"] == panel})
        for cue in cues:
            pairs = []
            for gene in genes:
                base = by_key.get((panel, gene, baseline_cue))
                cue_row = by_key.get((panel, gene, cue))
                if base and cue_row:
                    pairs.append((base, cue_row))
            if not pairs:
                continue
            out[panel][cue] = {
                "n_pairs": len(pairs),
                "delta_net": _mean(cue_row["net"] - base["net"] for base, cue_row in pairs),
                "delta_correct": _mean(cue_row["correct"] - base["correct"] for base, cue_row in pairs),
                "delta_assay": _mean(cue_row["assay"] - base["assay"] for base, cue_row in pairs),
                "action_changed_rate": _mean(base["action"] != cue_row["action"] for base, cue_row in pairs),
            }
    return out


def _panel_signals(report: dict[str, Any]) -> dict[str, dict[str, float]]:
    panels = report.get("panel_signals", {}).get("panels", {})
    fields = [
        "centroid_distance_to_control",
        "mean_cell_distance_to_control",
        "std_cell_distance_to_control",
        "centroid_l2_norm",
        "mean_cell_l2_norm",
    ]
    out = {}
    for panel_id, signal in panels.items():
        values = {
            field: float(signal[field])
            for field in fields
            if isinstance(signal.get(field), (int, float))
        }
        if values:
            out[str(panel_id)] = values
    return out


def _signal_correlations(
    panel_signals: dict[str, dict[str, float]],
    panel_deltas: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, dict[str, dict[str, float | None]]]:
    fields = sorted({field for values in panel_signals.values() for field in values})
    cues = sorted({cue for panel in panel_deltas.values() for cue in panel})
    outcomes = ["delta_net", "delta_correct", "delta_assay", "action_changed_rate"]
    out: dict[str, dict[str, dict[str, float | None]]] = {}
    for cue in cues:
        out[cue] = {}
        for outcome in outcomes:
            out[cue][outcome] = {}
            for field in fields:
                pairs = [
                    (panel_signals[panel][field], panel_deltas[panel][cue][outcome])
                    for panel in sorted(panel_deltas)
                    if panel in panel_signals
                    and field in panel_signals[panel]
                    and cue in panel_deltas[panel]
                ]
                out[cue][outcome][field] = _pearson(pairs)
    return out


def _specificity_summary(real: dict[str, Any], placebo: dict[str, Any]) -> dict[str, Any]:
    real_delta = float(real.get("delta_net", 0.0))
    placebo_delta = float(placebo.get("delta_net", 0.0))
    real_action = float(real.get("action_changed_rate", 0.0))
    placebo_action = float(placebo.get("action_changed_rate", 0.0))
    return {
        "real_delta_net": _round(real_delta),
        "placebo_delta_net": _round(placebo_delta),
        "real_minus_placebo_delta_net": _round(real_delta - placebo_delta),
        "real_action_changed_rate": _round(real_action),
        "placebo_action_changed_rate": _round(placebo_action),
        "real_minus_placebo_action_changed_rate": _round(real_action - placebo_action),
        "placebo_fraction_of_real_delta_net": (
            _round(placebo_delta / real_delta) if abs(real_delta) > 1e-12 else None
        ),
    }


def _recommendation(specificity: dict[str, Any]) -> dict[str, Any]:
    gap = abs(float(specificity.get("real_minus_placebo_delta_net") or 0.0))
    placebo_fraction = specificity.get("placebo_fraction_of_real_delta_net")
    if placebo_fraction is not None and placebo_fraction >= 0.5 and gap < 0.01:
        decision = "do_not_scale_yet"
        reason = "placebo_effect_close_to_real_signal_effect"
    else:
        decision = "review_before_scaling"
        reason = "real_placebo_specificity_not_yet_established"
    return {
        "decision": decision,
        "reason": reason,
        "next_actions": [
            "replace coarse panel-level distance card with more decision-relevant signal features",
            "add a stronger irrelevant-signal control that preserves style but breaks panel linkage",
            "rerun a small pilot before any full Phase 1A matrix",
        ],
    }


def _mean(values) -> float:
    vals = [float(value) for value in values]
    return sum(vals) / len(vals) if vals else 0.0


def _pearson(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 3:
        return None
    xs = [float(x) for x, _ in pairs]
    ys = [float(y) for _, y in pairs]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


def _round_nested(value):
    if isinstance(value, dict):
        return {key: _round_nested(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_round_nested(item) for item in value]
    if isinstance(value, float):
        return _round(value)
    return value


def _round(value: float) -> float:
    return round(float(value), 6)
