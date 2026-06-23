"""Phase 1B edge-neighbor signal pilot review diagnostics."""

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


NO_SIGNAL_CUE = "no_internal_signal"
REAL_SIGNAL_CUE = "scfoundation_edge_neighbor_signal_shown"
RANDOM_CONTROL_CUE = "random_same_gene_neighbor_signal_shown"
SHUFFLED_CONTROL_CUE = "shuffled_readout_gene_neighbor_signal_shown"

SIGNAL_KEY_BY_CUE = {
    REAL_SIGNAL_CUE: "real_edge_internal_signal_summary",
    RANDOM_CONTROL_CUE: "random_same_gene_edge_internal_signal_summary",
    SHUFFLED_CONTROL_CUE: "shuffled_readout_gene_edge_internal_signal_summary",
}


def phase1b_review(
    panels: list[dict[str, Any]],
    packets: list[dict[str, Any]],
    episodes: list[dict[str, Any]],
    neighbor_report: dict[str, Any],
    *,
    lam: float = 0.5,
    baseline_cue: str = NO_SIGNAL_CUE,
) -> dict[str, Any]:
    """Review whether edge-neighbor signal improves routing beyond controls."""
    rows = gene_level_rows(panels, packets, episodes, lam=lam)
    paired = paired_cue_effects(rows, baseline_cue=baseline_cue)
    cue_metrics = _cue_metrics(rows)
    panel_deltas = _panel_deltas(rows, baseline_cue=baseline_cue)
    edge_signals = _edge_signals(neighbor_report)
    signal_behavior = _signal_behavior_correlations(rows, edge_signals, baseline_cue=baseline_cue)

    specificity = _specificity_summary(paired)
    recommendation = _recommendation(specificity)

    return {
        "phase": "phase1b",
        "status": "review_ready",
        "lambda": lam,
        "baseline_cue": baseline_cue,
        "scope": {
            "episodes": len(episodes),
            "gene_rows": len(rows),
            "panels": len({row["panel_id"] for row in rows}),
            "cue_conditions": sorted({row["cue_condition"] for row in rows}),
            "edge_signal_records": len(edge_signals),
        },
        "cue_metrics": cue_metrics,
        "paired_effects_vs_baseline": _round_nested(paired),
        "specificity": specificity,
        "panel_deltas": _round_nested(panel_deltas),
        "signal_behavior_correlations": _round_nested(signal_behavior),
        "recommendation": recommendation,
        "interpretation": {
            "short_read": (
                "The edge-neighbor cue changes routing, but the real signal does "
                "not improve net reward beyond no-signal or placebo/control cues."
            ),
            "claim_boundary": (
                "Small Phase 1B LLM pilot only; no claim that Claude faithfully "
                "uses true scFoundation internals or biological mechanisms."
            ),
            "next_design_step": (
                "Before any larger LLM matrix, redesign the evidence packet so "
                "the LLM receives an explicit calibrated risk policy or a clearer "
                "edge-level reliability target, then retest with controls."
            ),
        },
    }


def write_phase1b_review(
    *,
    panels: list[dict[str, Any]],
    packets: list[dict[str, Any]],
    episodes: list[dict[str, Any]],
    neighbor_report: dict[str, Any],
    out: str,
    lam: float = 0.5,
    baseline_cue: str = NO_SIGNAL_CUE,
) -> dict[str, Any]:
    review = phase1b_review(
        panels,
        packets,
        episodes,
        neighbor_report,
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


def _edge_signals(neighbor_report: dict[str, Any]) -> dict[tuple[str, str], dict[str, dict[str, float]]]:
    out: dict[tuple[str, str], dict[str, dict[str, float]]] = {}
    for record in neighbor_report.get("model_visible_edge_signals", []):
        key = (str(record.get("panel_id")), str(record.get("gene_display")))
        out[key] = {}
        for cue, signal_key in SIGNAL_KEY_BY_CUE.items():
            signal = record.get(signal_key, {})
            out[key][cue] = _flatten_signal_values(signal)
    return out


def _flatten_signal_values(signal: dict[str, Any]) -> dict[str, float]:
    fields = [
        "neighbor_count",
        "same_readout_gene_neighbor_count",
        "neighbor_baseline_disagreement_rate",
        "neighbor_sfm_call_agreement_rate",
        "neighbor_sfm_call_disagreement_rate",
    ]
    out = {
        field: float(signal[field])
        for field in fields
        if isinstance(signal.get(field), (int, float))
    }
    distance = signal.get("neighbor_embedding_distance", {})
    if isinstance(distance, dict):
        for key in ["min", "mean", "max"]:
            if isinstance(distance.get(key), (int, float)):
                out[f"neighbor_embedding_distance_{key}"] = float(distance[key])
    return out


def _signal_behavior_correlations(
    rows: list[dict[str, Any]],
    edge_signals: dict[tuple[str, str], dict[str, dict[str, float]]],
    *,
    baseline_cue: str,
) -> dict[str, dict[str, dict[str, float | None]]]:
    by_key = {
        (row["panel_id"], row["gene"], row["cue_condition"]): row
        for row in rows
    }
    samples: dict[str, list[tuple[dict[str, float], dict[str, float]]]] = defaultdict(list)
    for row in rows:
        cue = str(row["cue_condition"])
        if cue == baseline_cue:
            continue
        base = by_key.get((row["panel_id"], row["gene"], baseline_cue))
        signal = edge_signals.get((row["panel_id"], row["gene"]), {}).get(cue)
        if not base or not signal:
            continue
        outcomes = {
            "action_changed": float(base["action"] != row["action"]),
            "delta_net": float(row["net"] - base["net"]),
            "delta_correct": float(row["correct"] - base["correct"]),
            "delta_assay": float(row["assay"] - base["assay"]),
            "delta_trust_error": float(
                int(row["action"] == "trust_sfm" and row["sfm_wrong"])
                - int(base["action"] == "trust_sfm" and base["sfm_wrong"])
            ),
        }
        samples[cue].append((signal, outcomes))

    out: dict[str, dict[str, dict[str, float | None]]] = {}
    for cue, cue_samples in sorted(samples.items()):
        fields = sorted({field for signal, _ in cue_samples for field in signal})
        outcomes = sorted({field for _, outcome in cue_samples for field in outcome})
        out[cue] = {}
        for outcome in outcomes:
            out[cue][outcome] = {}
            for field in fields:
                pairs = [
                    (signal[field], outcome_values[outcome])
                    for signal, outcome_values in cue_samples
                    if field in signal and outcome in outcome_values
                ]
                out[cue][outcome][field] = _pearson(pairs)
    return out


def _specificity_summary(paired: dict[str, dict[str, Any]]) -> dict[str, Any]:
    real = paired.get(REAL_SIGNAL_CUE, {})
    random_control = paired.get(RANDOM_CONTROL_CUE, {})
    shuffled_control = paired.get(SHUFFLED_CONTROL_CUE, {})
    controls = [random_control, shuffled_control]

    real_delta = float(real.get("delta_net", 0.0))
    control_deltas = [float(control.get("delta_net", 0.0)) for control in controls]
    best_control_delta = max(control_deltas) if control_deltas else 0.0
    real_action = float(real.get("action_changed_rate", 0.0))
    control_actions = [float(control.get("action_changed_rate", 0.0)) for control in controls]
    max_control_action = max(control_actions) if control_actions else 0.0
    real_trust_delta = float(real.get("delta_trust_error", 0.0))
    control_trust_deltas = [float(control.get("delta_trust_error", 0.0)) for control in controls]
    strongest_control_trust_delta = min(control_trust_deltas) if control_trust_deltas else 0.0

    return {
        "real_delta_net": _round(real_delta),
        "random_control_delta_net": _round(float(random_control.get("delta_net", 0.0))),
        "shuffled_control_delta_net": _round(float(shuffled_control.get("delta_net", 0.0))),
        "best_control_delta_net": _round(best_control_delta),
        "real_minus_best_control_delta_net": _round(real_delta - best_control_delta),
        "real_action_changed_rate": _round(real_action),
        "max_control_action_changed_rate": _round(max_control_action),
        "real_minus_max_control_action_changed_rate": _round(real_action - max_control_action),
        "real_delta_trust_error": _round(real_trust_delta),
        "strongest_control_delta_trust_error": _round(strongest_control_trust_delta),
        "real_minus_strongest_control_delta_trust_error": _round(
            real_trust_delta - strongest_control_trust_delta
        ),
    }


def _recommendation(specificity: dict[str, Any]) -> dict[str, Any]:
    real_delta = float(specificity["real_delta_net"])
    real_minus_best = float(specificity["real_minus_best_control_delta_net"])
    real_minus_action = float(specificity["real_minus_max_control_action_changed_rate"])
    trust_specificity = float(specificity["real_minus_strongest_control_delta_trust_error"])

    if real_delta <= 0:
        decision = "do_not_scale_larger_llm_matrix"
        reason = "real_signal_reduced_net_reward_vs_no_signal"
    elif real_minus_best <= 0.01:
        decision = "do_not_scale_larger_llm_matrix"
        reason = "control_delta_net_close_to_or_better_than_real_signal"
    elif real_minus_action <= 0:
        decision = "review_before_scaling"
        reason = "control_action_shift_not_lower_than_real_signal"
    elif trust_specificity > 0:
        decision = "review_before_scaling"
        reason = "control_reduced_trust_error_more_than_real_signal"
    else:
        decision = "small_redesign_then_retest"
        reason = "directional_specificity_but_still_unvalidated"

    return {
        "decision": decision,
        "reason": reason,
        "next_actions": [
            "do not run a larger Phase 1B LLM matrix from this packet unchanged",
            "turn the neighbor signal into an explicit calibrated risk feature or thresholded policy",
            "add an irrelevant-style-matched control and an inverted-risk control",
            "rerun a small pilot only after the deterministic signal-gated policy beats controls",
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
