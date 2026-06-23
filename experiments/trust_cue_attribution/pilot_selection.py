"""Stratified pilot request selection for LLM episode runs."""

from __future__ import annotations

import json
import math
import random
from collections import defaultdict


DEFAULT_MAIN_CUES = [
    "no_cue",
    "model_name_shown",
    "anonymized_genes",
    "confidence_shown",
    "additive_disagreement_shown",
    "misleading_reliability_card",
]


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not math.isnan(float(value))


def panel_summary(panel: dict) -> dict:
    edges = panel.get("edges", [])
    n = len(edges)
    wrong = sum(1 for edge in edges if not edge["fm"]["correct"])
    additive = sum(1 for edge in edges if edge["baseline_signal"]["source"] == "observed_additive")
    disagreements = sum(1 for edge in edges if edge["baseline_signal"]["call_disagreement"])
    high_risk = sum(1 for edge in edges if edge["reliability_signal"]["label"] == "high_sfm_error_risk")
    reliability_scores = [
        float(edge["reliability_signal"]["score"])
        for edge in edges
        if _finite(edge["reliability_signal"].get("score"))
    ]
    return {
        "panel_id": panel["panel_id"],
        "n": n,
        "n_wrong": wrong,
        "wrong_rate": wrong / n if n else 0.0,
        "additive_coverage_rate": additive / n if n else 0.0,
        "additive_disagreement_rate": disagreements / n if n else 0.0,
        "high_risk_rate": high_risk / n if n else 0.0,
        "mean_reliability_score": sum(reliability_scores) / len(reliability_scores) if reliability_scores else 0.0,
    }


def _assign_tertiles(rows: list[dict], key: str) -> dict[str, str]:
    ordered = sorted(rows, key=lambda row: (row[key], row["panel_id"]))
    labels = {}
    n = len(ordered)
    for idx, row in enumerate(ordered):
        frac = idx / max(1, n)
        if frac < 1 / 3:
            label = "low"
        elif frac < 2 / 3:
            label = "mid"
        else:
            label = "high"
        labels[row["panel_id"]] = label
    return labels


def select_stratified_panels(panels: list[dict], n_panels: int = 12, seed: int = 19) -> tuple[list[str], list[dict]]:
    """Select panels balanced across wrong-rate bins and reliability strength."""
    summaries = [panel_summary(panel) for panel in panels]
    wrong_bins = _assign_tertiles(summaries, "wrong_rate")
    for row in summaries:
        row["wrong_rate_bin"] = wrong_bins[row["panel_id"]]

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in summaries:
        grouped[row["wrong_rate_bin"]].append(row)

    rng = random.Random(seed)
    selected: list[dict] = []
    labels = ["low", "mid", "high"]
    base = n_panels // len(labels)
    remainder = n_panels % len(labels)
    targets = {label: base + (1 if idx < remainder else 0) for idx, label in enumerate(labels)}

    for label in labels:
        rows = sorted(grouped[label], key=lambda row: (row["mean_reliability_score"], row["panel_id"]))
        # Alternate low and high reliability within each wrong-rate bin.
        order = []
        left, right = 0, len(rows) - 1
        while left <= right:
            order.append(rows[left])
            left += 1
            if left <= right:
                order.append(rows[right])
                right -= 1
        rng.shuffle(order)
        selected.extend(order[:targets[label]])

    selected = sorted(selected, key=lambda row: (row["wrong_rate_bin"], row["panel_id"]))
    return [row["panel_id"] for row in selected], selected


def filter_requests(requests: list[dict], panel_ids: list[str], cues: list[str] | None = None) -> list[dict]:
    panel_set = set(panel_ids)
    cue_set = set(cues or DEFAULT_MAIN_CUES)
    return [
        request for request in requests
        if request.get("panel_id") in panel_set and request.get("cue_condition") in cue_set
    ]


def pilot_manifest(selected_summaries: list[dict], cues: list[str], requests: list[dict]) -> dict:
    return {
        "n_panels": len(selected_summaries),
        "n_requests": len(requests),
        "cue_conditions": cues,
        "panels": selected_summaries,
    }


def write_manifest(manifest: dict, path: str) -> None:
    with open(path, "w") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")

