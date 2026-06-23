"""Phase 1A panel-level internal-signal validity diagnostics."""

from __future__ import annotations

import json
import math
import os
from typing import Any


PRIMARY_SIGNAL_FIELDS = [
    "centroid_distance_to_control",
    "mean_cell_distance_to_control",
    "std_cell_distance_to_control",
]

SIGNAL_FIELDS = [
    "centroid_distance_to_control",
    "mean_cell_distance_to_control",
    "std_cell_distance_to_control",
    "centroid_l2_norm",
    "mean_cell_l2_norm",
    "std_cell_l2_norm",
]

TARGET_FIELDS = [
    "wrong_rate",
    "additive_disagreement_rate",
    "high_risk_rate",
    "mean_reliability_score",
    "additive_coverage_rate",
]


def phase1a_signal_validity(
    selected_panels: list[dict[str, Any]],
    panel_signal_report: dict[str, Any],
) -> dict[str, Any]:
    """Check whether panel-level scFoundation proxies track GEARS wrongness."""
    signal_by_panel = _panel_signals(panel_signal_report)
    rows = _matched_rows(selected_panels, signal_by_panel)
    correlations = _correlations(rows)
    strongest = _strongest_by_target(correlations)
    decision = _decision(strongest, len(rows))

    return {
        "phase": "phase1a",
        "status": "signal_validity_ready",
        "claim_boundary": (
            "Exploratory panel-level signal-validity diagnostic only; no full "
            "Phase 1A, true-SFM trust, or biological interpretation claim."
        ),
        "primary_question": (
            "Do coarse scFoundation panel embedding distance summaries align "
            "with GEARS wrongness strongly enough to justify scaling this cue?"
        ),
        "scope": {
            "selected_panels": len(selected_panels),
            "panel_signals": len(signal_by_panel),
            "matched_panels": len(rows),
            "signal_fields": SIGNAL_FIELDS,
            "primary_signal_fields": PRIMARY_SIGNAL_FIELDS,
            "target_fields": TARGET_FIELDS,
        },
        "panel_rows": _round_nested(rows),
        "correlations": _round_nested(correlations),
        "strongest_by_target": _round_nested(strongest),
        "decision": decision,
        "interpretation": {
            "short_read": decision["short_read"],
            "method_note": (
                "Correlations use the 12 selected Phase 1A pilot panels, so they "
                "are route-selection diagnostics rather than calibrated biology."
            ),
            "next_design_step": (
                "If the current signal is weak or ambiguous, replace the coarse "
                "panel card with gene-level or task-aligned SFM evidence before "
                "running a larger LLM matrix."
            ),
        },
    }


def write_phase1a_signal_validity(
    *,
    selected_panels: list[dict[str, Any]],
    panel_signal_report: dict[str, Any],
    out: str,
) -> dict[str, Any]:
    report = phase1a_signal_validity(selected_panels, panel_signal_report)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return report


def selected_panels_from_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    panels = manifest.get("selected_panels")
    if panels is None:
        panels = manifest.get("panels")
    if not isinstance(panels, list):
        raise ValueError("manifest must contain selected_panels or panels")
    return panels


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


def _matched_rows(
    selected_panels: list[dict[str, Any]],
    signal_by_panel: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    rows = []
    for panel in selected_panels:
        panel_id = str(panel.get("panel_id", ""))
        signal = signal_by_panel.get(panel_id)
        if not signal:
            continue
        row = {
            "panel_id": panel_id,
            "wrong_rate_bin": panel.get("wrong_rate_bin"),
        }
        for field in TARGET_FIELDS:
            if _finite(panel.get(field)):
                row[field] = float(panel[field])
        for field in SIGNAL_FIELDS:
            if field in signal:
                row[field] = signal[field]
        rows.append(row)
    return sorted(rows, key=lambda row: row["panel_id"])


def _correlations(rows: list[dict[str, Any]]) -> dict[str, dict[str, dict[str, float | int | None]]]:
    out: dict[str, dict[str, dict[str, float | int | None]]] = {}
    for target in TARGET_FIELDS:
        out[target] = {}
        for signal in SIGNAL_FIELDS:
            pairs = [
                (float(row[signal]), float(row[target]))
                for row in rows
                if _finite(row.get(signal)) and _finite(row.get(target))
            ]
            out[target][signal] = {
                "n": len(pairs),
                "pearson": _pearson(pairs),
                "spearman": _spearman(pairs),
            }
    return out


def _strongest_by_target(
    correlations: dict[str, dict[str, dict[str, float | int | None]]],
) -> dict[str, dict[str, Any]]:
    out = {}
    for target, by_signal in correlations.items():
        candidates = []
        for field, stats in by_signal.items():
            for method in ("spearman", "pearson"):
                value = stats.get(method)
                if isinstance(value, (int, float)):
                    candidates.append(
                        {
                            "signal_field": field,
                            "method": method,
                            "correlation": float(value),
                            "abs_correlation": abs(float(value)),
                            "n": int(stats.get("n", 0)),
                        }
                    )
        primary_candidates = [
            item for item in candidates if item["signal_field"] in PRIMARY_SIGNAL_FIELDS
        ]
        out[target] = {
            "strongest_any_signal": _max_abs(candidates),
            "strongest_primary_signal": _max_abs(primary_candidates),
        }
    return out


def _decision(strongest: dict[str, dict[str, Any]], n_panels: int) -> dict[str, Any]:
    wrong_primary = strongest.get("wrong_rate", {}).get("strongest_primary_signal") or {}
    corr = wrong_primary.get("correlation")
    abs_corr = wrong_primary.get("abs_correlation")
    field = wrong_primary.get("signal_field")
    method = wrong_primary.get("method")

    if n_panels < 8 or abs_corr is None:
        scale_decision = "insufficient_panel_overlap"
        reason = "too_few_matched_panels"
        short_read = "Too few matched panels to evaluate this signal."
    elif abs_corr < 0.3:
        scale_decision = "do_not_scale_with_current_panel_signal"
        reason = "weak_relation_to_gears_wrongness"
        short_read = (
            "The coarse scFoundation panel-distance signal is not yet a useful "
            "reliability signal for GEARS wrongness."
        )
    elif corr is not None and corr < 0:
        scale_decision = "redesign_before_scaling"
        reason = "primary_signal_points_opposite_expected_direction"
        short_read = (
            "The strongest primary signal is associated with lower wrongness, "
            "so it should not be used as a naive high-risk cue."
        )
    else:
        scale_decision = "promising_but_small_n"
        reason = "primary_signal_tracks_wrongness_exploratorily"
        short_read = (
            "The coarse panel signal has an exploratory relation to wrongness, "
            "but needs stronger controls before scaling."
        )

    return {
        "scale_decision": scale_decision,
        "reason": reason,
        "wrong_rate_primary_signal": {
            "signal_field": field,
            "method": method,
            "correlation": _round(corr) if isinstance(corr, (int, float)) else None,
            "abs_correlation": _round(abs_corr) if isinstance(abs_corr, (int, float)) else None,
            "n_panels": n_panels,
        },
        "short_read": short_read,
        "next_actions": [
            "do not run a larger Phase 1A LLM matrix solely on this coarse panel card",
            "build a gene-level or task-aligned internal-signal cue",
            "keep the shuffled-signal placebo control in the next pilot",
        ],
    }


def _max_abs(items: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not items:
        return None
    return sorted(
        items,
        key=lambda item: (
            -float(item["abs_correlation"]),
            str(item["signal_field"]),
            str(item["method"]),
        ),
    )[0]


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


def _spearman(pairs: list[tuple[float, float]]) -> float | None:
    if len(pairs) < 3:
        return None
    xs = [x for x, _ in pairs]
    ys = [y for _, y in pairs]
    return _pearson(list(zip(_ranks(xs), _ranks(ys))))


def _ranks(values: list[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    idx = 0
    while idx < len(ordered):
        end = idx + 1
        while end < len(ordered) and ordered[end][1] == ordered[idx][1]:
            end += 1
        avg_rank = (idx + 1 + end) / 2
        for original_idx, _ in ordered[idx:end]:
            ranks[original_idx] = avg_rank
        idx = end
    return ranks


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not math.isnan(float(value))


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
