"""Phase 1B edge-neighbor signal packet builder.

This module turns a passed Phase 1B edge-neighbor diagnostic into leakage-safe
LLM pilot packets. It does not call an LLM and does not score routing.
"""

from __future__ import annotations

import copy
import json
import os
from collections import Counter
from typing import Any

try:
    from .cues import ACTIONS
    from .phase1b_neighbor_signals import TARGET_DIAGNOSTIC_STATUS, leakage_check
except ImportError:  # direct script/test execution from this directory
    from cues import ACTIONS
    from phase1b_neighbor_signals import TARGET_DIAGNOSTIC_STATUS, leakage_check


PHASE1B_SIGNAL_CUES = [
    "no_internal_signal",
    "scfoundation_edge_neighbor_signal_shown",
    "random_same_gene_neighbor_signal_shown",
    "shuffled_readout_gene_neighbor_signal_shown",
]

SIGNAL_FIELD_BY_CUE = {
    "scfoundation_edge_neighbor_signal_shown": "real_edge_internal_signal_summary",
    "random_same_gene_neighbor_signal_shown": "random_same_gene_edge_internal_signal_summary",
    "shuffled_readout_gene_neighbor_signal_shown": "shuffled_readout_gene_edge_internal_signal_summary",
}


def load_phase1b_edge_signals(report_path: str) -> dict[tuple[str, str], dict[str, Any]]:
    """Load full model-visible edge signals from a passed Phase 1B diagnostic."""
    with open(report_path) as handle:
        report = json.load(handle)
    status = report.get("status")
    if status != TARGET_DIAGNOSTIC_STATUS:
        raise ValueError(f"Phase 1B neighbor report is not ready: {status!r}")
    decision = report.get("decision", {}).get("decision")
    if decision != "eligible_for_small_llm_pilot":
        raise ValueError(f"Phase 1B neighbor report is not LLM-pilot eligible: {decision!r}")
    records = report.get("model_visible_edge_signals")
    if not isinstance(records, list) or not records:
        raise ValueError("Phase 1B neighbor report is missing full model_visible_edge_signals")
    out = {}
    for record in records:
        key = (str(record["panel_id"]), str(record["gene_display"]))
        out[key] = {
            "real_edge_internal_signal_summary": record["real_edge_internal_signal_summary"],
            "random_same_gene_edge_internal_signal_summary": record["random_same_gene_edge_internal_signal_summary"],
            "shuffled_readout_gene_edge_internal_signal_summary": record["shuffled_readout_gene_edge_internal_signal_summary"],
        }
    return out


def generate_phase1b_signal_packets(
    panels: list[dict[str, Any]],
    edge_signals: dict[tuple[str, str], dict[str, Any]],
    *,
    cue_conditions: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Generate Phase 1B no-signal/real/control cue packets."""
    conditions = cue_conditions or PHASE1B_SIGNAL_CUES
    unknown = sorted(set(conditions) - set(PHASE1B_SIGNAL_CUES))
    if unknown:
        raise ValueError(f"unknown Phase 1B cue condition(s): {unknown}")
    selected_ids = {panel_id for panel_id, _gene in edge_signals}
    selected_panels = [panel for panel in panels if str(panel["panel_id"]) in selected_ids]
    return [
        phase1b_signal_packet(panel, cue, edge_signals)
        for panel in selected_panels
        for cue in conditions
    ]


def phase1b_signal_packet(
    panel: dict[str, Any],
    cue_condition: str,
    edge_signals: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Create one leakage-safe Phase 1B evidence packet."""
    if cue_condition not in PHASE1B_SIGNAL_CUES:
        raise ValueError(f"unknown Phase 1B cue condition {cue_condition!r}")

    signal_field = SIGNAL_FIELD_BY_CUE.get(cue_condition)
    genes = []
    scoring_key = []
    for edge in panel.get("edges", []):
        gene_display = str(edge["gene"])
        gene_record = {
            "gene_display": gene_display,
            "sfm_call": edge["fm"]["call"],
            "sfm_log2fc": round(float(edge["fm"]["log2fc"]), 3),
        }
        if signal_field:
            signals = edge_signals.get((str(panel["panel_id"]), gene_display))
            if signals is None:
                raise KeyError(f"missing Phase 1B edge signal for {panel['panel_id']!r} / {gene_display!r}")
            gene_record["edge_internal_signal_summary"] = copy.deepcopy(signals[signal_field])
        genes.append(gene_record)
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
        "phase": "phase1b",
        "adapter": "ScFoundationAdapter",
        "internal_signal_visible": signal_field is not None,
        "internal_signal_control": _control_label(cue_condition),
        "claim_boundary": (
            "Phase 1B packet construction only; no LLM routing result, no "
            "faithful scFoundation interpretation claim, and no biological claim."
        ),
    }

    return {
        "packet_id": f"{panel['panel_id']}::{cue_condition}",
        "panel_id": panel["panel_id"],
        "cue_condition": cue_condition,
        "available_actions": ACTIONS,
        "scoring_key": scoring_key,
        "evidence_packet": evidence,
        "metadata": metadata,
    }


def phase1b_packet_manifest(
    *,
    packets: list[dict[str, Any]],
    neighbor_report: str,
    out: str,
) -> dict[str, Any]:
    """Build a compact manifest for generated Phase 1B signal packets."""
    cue_counts = Counter(packet["cue_condition"] for packet in packets)
    leakage = leakage_check([packet["evidence_packet"] for packet in packets])
    panels = sorted({packet["panel_id"] for packet in packets})
    gene_counts = {
        packet["packet_id"]: len(packet["evidence_packet"]["genes"])
        for packet in packets
    }
    return {
        "phase": "phase1b",
        "status": "signal_packet_pilot_ready" if leakage["passed"] else "blocked_packet_leakage",
        "claim_boundary": (
            "Packet-generation checkpoint only; no LLM routing result, no "
            "true-SFM trust claim, and no biological interpretation claim."
        ),
        "source_neighbor_report": neighbor_report,
        "packet_out": out,
        "n_panels": len(panels),
        "panel_ids": panels,
        "n_packets": len(packets),
        "cue_conditions": PHASE1B_SIGNAL_CUES,
        "cue_counts": dict(sorted(cue_counts.items())),
        "gene_count_min": min(gene_counts.values()) if gene_counts else 0,
        "gene_count_max": max(gene_counts.values()) if gene_counts else 0,
        "model_visible_leakage_check": leakage,
        "next_decision_gate": (
            "Create request JSONL and run a small Sonnet-only Phase 1B pilot "
            "only after confirming cue balance and prompt leakage checks."
        ),
    }


def write_phase1b_signal_packets(
    *,
    panels: list[dict[str, Any]],
    neighbor_report: str,
    out: str,
    manifest_out: str | None = None,
    cue_conditions: list[str] | None = None,
) -> dict[str, Any]:
    """Write Phase 1B signal packets and an optional compact manifest."""
    edge_signals = load_phase1b_edge_signals(neighbor_report)
    packets = generate_phase1b_signal_packets(
        panels,
        edge_signals,
        cue_conditions=cue_conditions,
    )
    _write_jsonl(packets, out)
    manifest = phase1b_packet_manifest(
        packets=packets,
        neighbor_report=neighbor_report,
        out=out,
    )
    if manifest_out:
        os.makedirs(os.path.dirname(manifest_out) or ".", exist_ok=True)
        with open(manifest_out, "w") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return manifest


def _control_label(cue_condition: str) -> str:
    if cue_condition == "no_internal_signal":
        return "absent"
    if cue_condition == "scfoundation_edge_neighbor_signal_shown":
        return "real_edge_neighbor_summary"
    if cue_condition == "random_same_gene_neighbor_signal_shown":
        return "random_same_readout_gene_neighbor_control"
    if cue_condition == "shuffled_readout_gene_neighbor_signal_shown":
        return "shuffled_readout_gene_control"
    return "unknown"


def _write_jsonl(records: list[dict[str, Any]], path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
