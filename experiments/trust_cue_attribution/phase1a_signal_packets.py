"""Phase 1A internal-signal cue packet builder.

Phase 1A reuses the Phase 0 perturbation decision schema, but adds controlled
scFoundation internal-signal cue conditions. This module does not run an LLM and
does not claim biological interpretation; it only builds leakage-safe packets.
"""

from __future__ import annotations

import copy
import json
import math
import os
import random
import re
from collections import Counter
from typing import Any

try:
    from .cues import ACTIONS
    from .pilot_selection import panel_summary, select_stratified_panels
except ImportError:  # direct script/test execution from this directory
    from cues import ACTIONS
    from pilot_selection import panel_summary, select_stratified_panels


PHASE1A_SIGNAL_CUES = [
    "no_internal_signal",
    "scfoundation_internal_signal_shown",
    "shuffled_internal_signal_shown",
]

TARGET_SMOKE_STATUS = "ready_for_internal_signal_summary_adapter"
TARGET_PANEL_SIGNAL_STATUS = "ready_for_phase1a_panel_specific_signal_packets"


def load_scfoundation_smoke_signal(report_path: str) -> dict[str, Any]:
    """Load a compact scFoundation smoke report as a Phase 1A signal summary."""
    with open(report_path) as handle:
        report = json.load(handle)
    status = report.get("status")
    if status != TARGET_SMOKE_STATUS:
        raise ValueError(f"scFoundation smoke report is not ready: {status!r}")
    return smoke_report_to_internal_signal(report)


def load_panel_specific_internal_signals(report_path: str) -> dict[str, dict[str, Any]]:
    """Load a Phase 1A panel-specific signal report keyed by panel id."""
    with open(report_path) as handle:
        report = json.load(handle)
    status = report.get("status")
    if status != TARGET_PANEL_SIGNAL_STATUS:
        raise ValueError(f"panel signal report is not ready: {status!r}")
    panels = report.get("panel_signals", {}).get("panels", {})
    return {
        str(panel_id): signal
        for panel_id, signal in panels.items()
        if signal.get("status") == "ready"
    }


def smoke_report_to_internal_signal(report: dict[str, Any]) -> dict[str, Any]:
    """Convert a smoke report into the model-visible internal-signal schema."""
    embedding = report.get("embedding_summary", {})
    subset = report.get("subset", {})
    process = report.get("process", {})
    embedding_shape = [int(value) for value in embedding.get("shape", [])]
    subset_shape = [int(value) for value in subset.get("subset_shape", [])]
    source_shape = [int(value) for value in subset.get("source_shape", [])]
    feature_count = _parse_feature_space_gene_count(process.get("stdout_tail", []), embedding_shape)

    return {
        "source": "scFoundation_official_embedding_smoke",
        "adapter": report.get("adapter", "ScFoundationAdapter"),
        "status": report.get("status"),
        "signal_type": "cell_embedding_summary",
        "signal_scope": "global_three_cell_smoke_subset_not_panel_specific",
        "calibration_status": "unverified_proxy_not_calibrated",
        "model_family": "single_cell_foundation_model",
        "embedding_shape": embedding_shape,
        "embedding_dim": embedding_shape[1] if len(embedding_shape) >= 2 else None,
        "embedding_dtype": embedding.get("dtype"),
        "embedding_finite_fraction": _round_or_none(embedding.get("finite_fraction"), 6),
        "embedding_mean": _round_or_none(embedding.get("mean"), 6),
        "embedding_std": _round_or_none(embedding.get("std"), 6),
        "embedding_l2_norm": _round_or_none(embedding.get("l2_norm"), 6),
        "subset_cell_count": subset_shape[0] if len(subset_shape) >= 1 else None,
        "input_gene_count": subset_shape[1] if len(subset_shape) >= 2 else None,
        "source_cell_count": source_shape[0] if len(source_shape) >= 1 else None,
        "scfoundation_feature_gene_count": feature_count,
        "limitations": [
            "three_cell_smoke_only",
            "not_panel_specific_yet",
            "not_a_calibrated_uncertainty",
            "does_not_contain_hidden_labels",
        ],
    }


def generate_phase1a_signal_packets(
    panels: list[dict[str, Any]],
    internal_signal: dict[str, Any] | None = None,
    *,
    panel_signals: dict[str, dict[str, Any]] | None = None,
    cue_conditions: list[str] | None = None,
    seed: int = 23,
) -> list[dict[str, Any]]:
    """Generate Phase 1A signal/no-signal/control cue packets."""
    conditions = cue_conditions or PHASE1A_SIGNAL_CUES
    unknown = sorted(set(conditions) - set(PHASE1A_SIGNAL_CUES))
    if unknown:
        raise ValueError(f"unknown Phase 1A cue condition(s): {unknown}")
    return [
        phase1a_signal_packet(panel, cue, internal_signal, panel_signals=panel_signals, seed=seed)
        for panel in panels
        for cue in conditions
    ]


def phase1a_signal_packet(
    panel: dict[str, Any],
    cue_condition: str,
    internal_signal: dict[str, Any] | None = None,
    *,
    panel_signals: dict[str, dict[str, Any]] | None = None,
    seed: int = 23,
) -> dict[str, Any]:
    """Create one leakage-safe Phase 1A evidence packet."""
    if cue_condition not in PHASE1A_SIGNAL_CUES:
        raise ValueError(f"unknown Phase 1A cue condition {cue_condition!r}")

    genes = []
    scoring_key = []
    for edge in panel.get("edges", []):
        gene_display = str(edge["gene"])
        genes.append({
            "gene_display": gene_display,
            "sfm_call": edge["fm"]["call"],
            "sfm_log2fc": round(float(edge["fm"]["log2fc"]), 3),
        })
        scoring_key.append({
            "gene_display": gene_display,
            "gene": edge["gene"],
            "edge_id": edge["edge_id"],
        })

    evidence = {
        "model_card": {
            "display_name": "specialist model A",
            "adapter": "hidden",
        },
        "perturbation": panel["perturbation"],
        "genes": genes,
    }
    metadata = {
        "phase": "phase1a",
        "adapter": "ScFoundationAdapter",
        "internal_signal_visible": False,
        "internal_signal_control": "absent",
        "claim_boundary": (
            "Phase 1A packet construction only; no LLM routing, true-SFM "
            "trust, or scientific interpretation claim"
        ),
    }

    if cue_condition == "scfoundation_internal_signal_shown":
        evidence["internal_signal_summary"] = copy.deepcopy(_signal_for_panel(panel["panel_id"], internal_signal, panel_signals))
        metadata["internal_signal_visible"] = True
        metadata["internal_signal_control"] = "real_panel_specific_summary" if panel_signals else "real_smoke_summary"
    elif cue_condition == "shuffled_internal_signal_shown":
        signal = (
            _shuffled_source_signal_for_panel(panel["panel_id"], panel_signals, seed=seed)
            if panel_signals
            else _signal_for_panel(panel["panel_id"], internal_signal, panel_signals)
        )
        evidence["internal_signal_summary"] = shuffled_internal_signal(
            signal,
            panel_id=panel["panel_id"],
            seed=seed,
        )
        metadata["internal_signal_visible"] = True
        metadata["internal_signal_control"] = "deterministic_shuffled_control"

    return {
        "packet_id": f"{panel['panel_id']}::{cue_condition}",
        "panel_id": panel["panel_id"],
        "cue_condition": cue_condition,
        "available_actions": ACTIONS,
        "scoring_key": scoring_key,
        "evidence_packet": evidence,
        "metadata": metadata,
    }


def shuffled_internal_signal(internal_signal: dict[str, Any], *, panel_id: str, seed: int = 23) -> dict[str, Any]:
    """Create a deterministic placebo/control internal-signal summary.

    The control preserves shape, dtype, finite fraction, and source wording while
    perturbing aggregate values. The cue label remains outside the prompt.
    """
    rng = random.Random(f"{seed}:{panel_id}:scfoundation-control")
    out = copy.deepcopy(internal_signal)
    if "panel_id" in out:
        out["panel_id"] = panel_id
    mean = _float_or_none(out.get("embedding_mean"))
    std = _float_or_none(out.get("embedding_std"))
    norm = _float_or_none(out.get("embedding_l2_norm"))
    if mean is not None:
        out["embedding_mean"] = round(-mean + rng.uniform(-0.01, 0.01), 6)
    if std is not None:
        out["embedding_std"] = round(std * rng.uniform(0.65, 1.35), 6)
    if norm is not None:
        out["embedding_l2_norm"] = round(norm * rng.uniform(0.55, 1.45), 6)
    for key in [
        "centroid_distance_to_control",
        "centroid_l2_norm",
        "mean_cell_distance_to_control",
        "mean_cell_l2_norm",
        "std_cell_distance_to_control",
        "std_cell_l2_norm",
    ]:
        value = _float_or_none(out.get(key))
        if value is not None:
            out[key] = round(value * rng.uniform(0.55, 1.45), 6)
    out["calibration_status"] = "unverified_proxy_not_calibrated"
    return out


def _shuffled_source_signal_for_panel(
    panel_id: str,
    panel_signals: dict[str, dict[str, Any]] | None,
    *,
    seed: int,
) -> dict[str, Any]:
    if not panel_signals:
        raise ValueError("panel_signals are required for panel-specific shuffled controls")
    candidates = sorted(candidate for candidate in panel_signals if candidate != panel_id)
    if not candidates:
        return panel_signals[panel_id]
    rng = random.Random(f"{seed}:{panel_id}:panel-signal-source")
    return panel_signals[rng.choice(candidates)]


def _signal_for_panel(
    panel_id: str,
    internal_signal: dict[str, Any] | None,
    panel_signals: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    if panel_signals is not None:
        try:
            return panel_signals[panel_id]
        except KeyError as exc:
            raise KeyError(f"missing panel-specific internal signal for {panel_id!r}") from exc
    if internal_signal is None:
        raise ValueError("internal_signal is required when panel_signals is not provided")
    return internal_signal


def select_phase1a_panels(
    panels: list[dict[str, Any]],
    *,
    n_panels: int = 12,
    seed: int = 23,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Select a small balanced Phase 1A pilot subset."""
    if n_panels <= 0 or n_panels >= len(panels):
        selected_summaries = [panel_summary(panel) for panel in panels]
        return list(panels), selected_summaries
    panel_ids, selected_summaries = select_stratified_panels(panels, n_panels=n_panels, seed=seed)
    panel_set = set(panel_ids)
    return [panel for panel in panels if panel["panel_id"] in panel_set], selected_summaries


def phase1a_manifest(
    *,
    panels: list[dict[str, Any]],
    selected_summaries: list[dict[str, Any]],
    packets: list[dict[str, Any]],
    smoke_report: str,
    panel_signal_report: str | None,
    out: str,
    seed: int,
) -> dict[str, Any]:
    """Build a compact manifest for generated Phase 1A signal packets."""
    cue_counts = Counter(packet["cue_condition"] for packet in packets)
    return {
        "phase": "phase1a",
        "status": "signal_packet_pilot_ready",
        "claim_boundary": (
            "Packet-generation checkpoint only; no LLM routing result, no "
            "true-SFM trust claim, and no biological interpretation claim"
        ),
        "source_smoke_report": smoke_report,
        "source_panel_signal_report": panel_signal_report,
        "signal_scope": "panel_specific" if panel_signal_report else "global_smoke_summary",
        "packet_out": out,
        "seed": seed,
        "n_panels": len(panels),
        "n_packets": len(packets),
        "cue_conditions": PHASE1A_SIGNAL_CUES,
        "cue_counts": dict(sorted(cue_counts.items())),
        "selected_panels": selected_summaries,
        "next_decision_gate": (
            "Run a small Sonnet-only Phase 1A pilot only after checking that "
            "the internal_signal_summary is scientifically meaningful enough "
            "for a routing-behavior test."
        ),
    }


def write_phase1a_signal_packets(
    *,
    panels: list[dict[str, Any]],
    smoke_report: str,
    panel_signal_report: str | None = None,
    out: str,
    manifest_out: str | None = None,
    n_panels: int = 12,
    seed: int = 23,
) -> dict[str, Any]:
    """Write Phase 1A signal packets and an optional compact manifest."""
    internal_signal = None if panel_signal_report else load_scfoundation_smoke_signal(smoke_report)
    panel_signals = load_panel_specific_internal_signals(panel_signal_report) if panel_signal_report else None
    selected_panels, selected_summaries = select_phase1a_panels(panels, n_panels=n_panels, seed=seed)
    packets = generate_phase1a_signal_packets(
        selected_panels,
        internal_signal,
        panel_signals=panel_signals,
        seed=seed,
    )
    _write_jsonl(packets, out)
    manifest = phase1a_manifest(
        panels=selected_panels,
        selected_summaries=selected_summaries,
        packets=packets,
        smoke_report=smoke_report,
        panel_signal_report=panel_signal_report,
        out=out,
        seed=seed,
    )
    if manifest_out:
        os.makedirs(os.path.dirname(manifest_out) or ".", exist_ok=True)
        with open(manifest_out, "w") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return manifest


def _parse_feature_space_gene_count(stdout_tail: list[str], embedding_shape: list[int]) -> int | None:
    for line in stdout_tail:
        match = re.fullmatch(r"\((\d+),\s*(\d+)\)", str(line).strip())
        if not match:
            continue
        second = int(match.group(2))
        if len(embedding_shape) >= 2 and second == embedding_shape[1]:
            continue
        if second > 1000:
            return second
    return None


def _write_jsonl(records: list[dict[str, Any]], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _round_or_none(value: Any, digits: int) -> float | None:
    value = _float_or_none(value)
    if value is None:
        return None
    return round(value, digits)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(out) else out
