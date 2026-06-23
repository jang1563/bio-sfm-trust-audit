"""Phase 1C calibrated reliability-interface offline gate."""

from __future__ import annotations

import hashlib
import json
import os
import copy
from collections import Counter
from typing import Any

try:
    from .baselines import always_additive, signal_gated_verify, trust_all_sfm, verify_all
    from .cues import ACTIONS
    from .phase1b_neighbor_signals import leakage_check
    from .scoring import LAMBDAS, score_policy
except ImportError:  # direct script/test execution from this directory
    from baselines import always_additive, signal_gated_verify, trust_all_sfm, verify_all
    from cues import ACTIONS
    from phase1b_neighbor_signals import leakage_check
    from scoring import LAMBDAS, score_policy


EFFECT_CALL_THRESHOLD = 0.25
MARGIN_WINDOW = 0.25
ACTION_THRESHOLD = 0.5
COMBINED_WEIGHTS = {
    "additive_disagreement_risk": 0.45,
    "sfm_margin_risk": 0.35,
    "scfoundation_neighbor_disagreement_risk": 0.20,
}

REAL_SIGNAL_KEY = "real_edge_internal_signal_summary"
RANDOM_CONTROL_KEY = "random_same_gene_edge_internal_signal_summary"
SHUFFLED_CONTROL_KEY = "shuffled_readout_gene_edge_internal_signal_summary"

REFERENCE_CUES = {
    "no_signal_llm": "no_internal_signal",
    "raw_edge_neighbor_llm": "scfoundation_edge_neighbor_signal_shown",
    "random_same_gene_llm_control": "random_same_gene_neighbor_signal_shown",
    "shuffled_readout_gene_llm_control": "shuffled_readout_gene_neighbor_signal_shown",
}

PHASE1C_INTERFACE_CUES = [
    "no_internal_signal",
    "edge_neighbor_signal_shown",
    "calibrated_reliability_interface_shown",
    "inverted_reliability_interface_control",
]


def phase1c_design(
    *,
    panels_path: str,
    neighbor_report_path: str,
    phase1b_summary_path: str,
) -> dict[str, Any]:
    """Return the fixed reliability-interface design used by the offline gate."""
    return {
        "phase": "phase1c",
        "status": "design_ready",
        "goal": (
            "Test whether converting specialist/SFM evidence into an explicit "
            "calibrated reliability interface can improve routing reward before "
            "spending on another LLM pilot."
        ),
        "claim_boundary": (
            "Offline deterministic gate only; no new Claude calls, no true-SFM "
            "faithfulness claim, and no biological interpretation claim."
        ),
        "source_artifacts": {
            "panels": _artifact_record(panels_path),
            "neighbor_report": _artifact_record(neighbor_report_path),
            "phase1b_summary": _artifact_record(phase1b_summary_path),
        },
        "model_visible_interface_schema": {
            "reliability_interface": {
                "risk_bucket": "low | medium | high",
                "estimated_sfm_wrong_risk": "float in [0, 1]",
                "recommended_action": "trust_sfm | verify_assay | default_baseline",
                "evidence_basis": [
                    "sfm_log2fc_margin",
                    "additive_disagreement",
                    "scfoundation_neighbor_disagreement",
                ],
                "calibration_status": "offline_gate_not_biology_calibrated",
            }
        },
        "fixed_policy": {
            "effect_call_threshold_abs_log2fc": EFFECT_CALL_THRESHOLD,
            "margin_window_abs_log2fc": MARGIN_WINDOW,
            "action_threshold": ACTION_THRESHOLD,
            "combined_weights": COMBINED_WEIGHTS,
            "action_rule": (
                "If risk >= action_threshold, choose default_baseline when the "
                "additive baseline disagrees with the specialist model, otherwise "
                "choose verify_assay. If risk < threshold, choose trust_sfm."
            ),
            "risk_features": {
                "sfm_margin_risk": (
                    "High when abs(sfm_log2fc) is close to the effect/no-effect "
                    "call boundary; this is a specialist-output uncertainty proxy."
                ),
                "additive_disagreement_risk": (
                    "High when the additive baseline call disagrees with the "
                    "specialist model and/or the log2FC gap is large."
                ),
                "scfoundation_neighbor_disagreement_risk": (
                    "Real Phase 1B edge-neighbor SFM-call disagreement rate."
                ),
            },
        },
        "offline_gate_criteria": [
            "combined_real net_reward_per_gene at lambda 0.5 exceeds no_signal_llm",
            "combined_real net_reward_per_gene at lambda 0.5 exceeds raw_edge_neighbor_llm",
            "combined_real net_reward_per_gene at lambda 0.5 exceeds shuffled and random controls",
            "combined_real is compared against margin-only, additive-only, and neighbor-only ablations",
        ],
        "next_step_if_passes": (
            "Create a small Phase 1C LLM pilot only after this deterministic "
            "interface passes the offline gate."
        ),
    }


def phase1c_offline_gate(
    panels: list[dict[str, Any]],
    neighbor_report: dict[str, Any],
    phase1b_summary: dict[str, Any],
    *,
    lambdas: tuple[float, ...] = LAMBDAS,
) -> dict[str, Any]:
    """Score deterministic reliability-interface policies before any LLM calls."""
    signal_map = edge_signal_map(neighbor_report)
    selected_panels = attach_signal_records(panels, signal_map)
    policy_specs = reliability_policy_specs()
    scores = {
        str(lam): {
            name: _compact_score(score_policy(selected_panels, spec["policy"], lam))
            for name, spec in policy_specs.items()
        }
        for lam in lambdas
    }
    references = phase1b_reference_scores(phase1b_summary)
    decision = _gate_decision(scores["0.5"], references)
    return {
        "phase": "phase1c",
        "status": "offline_gate_ready",
        "claim_boundary": (
            "Offline deterministic gate only; no new LLM calls and no claim that "
            "Claude uses SFM internals faithfully."
        ),
        "scope": {
            "panels": len(selected_panels),
            "edges": sum(len(panel["edges"]) for panel in selected_panels),
            "edge_signal_records": len(signal_map),
        },
        "policy_definitions": {
            name: spec["description"]
            for name, spec in policy_specs.items()
        },
        "reference_llm_scores_lambda_0.5": references,
        "policy_scores": scores,
        "decision": decision,
        "interpretation": _interpretation(decision),
    }


def write_phase1c_design(
    *,
    panels_path: str,
    neighbor_report_path: str,
    phase1b_summary_path: str,
    out: str,
) -> dict[str, Any]:
    design = phase1c_design(
        panels_path=panels_path,
        neighbor_report_path=neighbor_report_path,
        phase1b_summary_path=phase1b_summary_path,
    )
    _write_json(design, out)
    return design


def write_phase1c_offline_gate(
    *,
    panels: list[dict[str, Any]],
    neighbor_report: dict[str, Any],
    phase1b_summary: dict[str, Any],
    out: str,
) -> dict[str, Any]:
    gate = phase1c_offline_gate(panels, neighbor_report, phase1b_summary)
    _write_json(gate, out)
    return gate


def generate_phase1c_interface_packets(
    panels: list[dict[str, Any]],
    neighbor_report: dict[str, Any],
    offline_gate: dict[str, Any],
    *,
    cue_conditions: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Generate the small Phase 1C LLM pilot packets after the offline gate."""
    _assert_offline_gate_allows_pilot(offline_gate)
    conditions = cue_conditions or PHASE1C_INTERFACE_CUES
    unknown = sorted(set(conditions) - set(PHASE1C_INTERFACE_CUES))
    if unknown:
        raise ValueError(f"unknown Phase 1C cue condition(s): {unknown}")
    signal_map = edge_signal_map(neighbor_report)
    selected_panels = attach_signal_records(panels, signal_map)
    return [
        phase1c_interface_packet(panel, cue)
        for panel in selected_panels
        for cue in conditions
    ]


def phase1c_interface_packet(panel: dict[str, Any], cue_condition: str) -> dict[str, Any]:
    """Create one Phase 1C model-visible packet for reliability-interface testing."""
    if cue_condition not in PHASE1C_INTERFACE_CUES:
        raise ValueError(f"unknown Phase 1C cue condition {cue_condition!r}")

    genes = []
    scoring_key = []
    for edge in panel.get("edges", []):
        gene_display = str(edge["gene"])
        gene_record = {
            "gene_display": gene_display,
            "sfm_call": edge["fm"]["call"],
            "sfm_log2fc": _round(edge["fm"]["log2fc"]),
        }
        if cue_condition == "edge_neighbor_signal_shown":
            gene_record["edge_internal_signal_summary"] = copy.deepcopy(
                edge["_phase1c_signal_record"][REAL_SIGNAL_KEY]
            )
        elif cue_condition == "calibrated_reliability_interface_shown":
            gene_record["reliability_interface"] = reliability_card(
                panel_id=str(panel["panel_id"]),
                edge=edge,
                weights=COMBINED_WEIGHTS,
                signal_key=REAL_SIGNAL_KEY,
            )
        elif cue_condition == "inverted_reliability_interface_control":
            gene_record["reliability_interface"] = reliability_card(
                panel_id=str(panel["panel_id"]),
                edge=edge,
                weights=COMBINED_WEIGHTS,
                signal_key=REAL_SIGNAL_KEY,
                invert=True,
            )
            gene_record["reliability_interface"]["control_note"] = (
                "inverted reliability-control card; use only to test cue sensitivity"
            )

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
        "phase": "phase1c",
        "adapter": "ScFoundationAdapter",
        "cue_family": "reliability_interface",
        "claim_boundary": (
            "Small request-generation checkpoint only; no LLM routing result, "
            "no true-SFM faithfulness claim, and no biological interpretation claim."
        ),
        "offline_gate_status": "eligible_for_small_phase1c_interface_pilot",
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


def phase1c_interface_manifest(
    *,
    packets: list[dict[str, Any]],
    requests: list[dict[str, Any]],
    neighbor_report: str,
    offline_gate: str,
    packet_out: str,
    request_out: str,
) -> dict[str, Any]:
    """Build a compact tracked manifest for the Phase 1C request JSONL."""
    cue_counts = Counter(packet["cue_condition"] for packet in packets)
    panels = sorted({str(packet["panel_id"]) for packet in packets})
    gene_counts = {
        packet["packet_id"]: len(packet["evidence_packet"]["genes"])
        for packet in packets
    }
    leakage = leakage_check([packet["evidence_packet"] for packet in packets])
    return {
        "phase": "phase1c",
        "status": "interface_request_pilot_ready" if leakage["passed"] else "blocked_packet_leakage",
        "claim_boundary": (
            "Request-generation checkpoint only; no new Claude call, no LLM "
            "routing result, no true-SFM faithfulness claim, and no biological claim."
        ),
        "source_artifacts": {
            "neighbor_report": _artifact_record(neighbor_report),
            "offline_gate": _artifact_record(offline_gate),
        },
        "packet_out": packet_out,
        "request_out": request_out,
        "n_panels": len(panels),
        "panel_ids": panels,
        "n_packets": len(packets),
        "n_requests": len(requests),
        "cue_conditions": PHASE1C_INTERFACE_CUES,
        "cue_counts": dict(sorted(cue_counts.items())),
        "gene_count_min": min(gene_counts.values()) if gene_counts else 0,
        "gene_count_max": max(gene_counts.values()) if gene_counts else 0,
        "model_visible_leakage_check": leakage,
        "pilot_design": {
            "primary_comparison": (
                "calibrated_reliability_interface_shown vs no_internal_signal "
                "and edge_neighbor_signal_shown"
            ),
            "negative_control": "inverted_reliability_interface_control",
            "expected_request_count": len(panels) * len(PHASE1C_INTERFACE_CUES),
        },
        "next_step": (
            "Run a small Sonnet-only Phase 1C interface pilot, then score paired "
            "cue effects against no_internal_signal. Do not scale to a large "
            "matrix unless the calibrated interface improves reward and the "
            "inverted control does not dominate behavior."
        ),
    }


def edge_signal_map(neighbor_report: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    """Map `(panel_id, gene)` to Phase 1B edge-neighbor signal record."""
    return {
        (str(record["panel_id"]), str(record["gene_display"])): record
        for record in neighbor_report.get("model_visible_edge_signals", [])
    }


def select_signal_matched_panels(
    panels: list[dict[str, Any]],
    signal_map: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Filter panels to the Phase 1B edge set with available signal records."""
    selected = []
    for panel in panels:
        edges = [
            edge
            for edge in panel.get("edges", [])
            if (str(panel["panel_id"]), str(edge["gene"])) in signal_map
        ]
        if edges:
            copied = dict(panel)
            copied["edges"] = edges
            selected.append(copied)
    return selected


def reliability_policy_specs() -> dict[str, dict[str, Any]]:
    """Return fixed deterministic policy variants for the offline gate."""
    return {
        "trust_all_sfm": {
            "description": "Always trust the specialist model.",
            "policy": trust_all_sfm,
        },
        "verify_all": {
            "description": "Verify every edge; upper-cost reference.",
            "policy": verify_all,
        },
        "always_additive": {
            "description": "Always default to the additive baseline.",
            "policy": always_additive,
        },
        "phase0_signal_gated_verify": {
            "description": "Existing Phase 0 reliability_signal top-budget gate.",
            "policy": lambda panel: signal_gated_verify(panel, budget=0.20),
        },
        "sfm_margin_only_interface": {
            "description": "Use only the specialist log2FC margin risk.",
            "policy": reliability_policy({"sfm_margin_risk": 1.0}),
        },
        "additive_only_interface": {
            "description": "Use only additive-disagreement risk.",
            "policy": reliability_policy({"additive_disagreement_risk": 1.0}),
        },
        "neighbor_only_real_interface": {
            "description": "Use only real scFoundation edge-neighbor disagreement risk.",
            "policy": reliability_policy({"scfoundation_neighbor_disagreement_risk": 1.0}),
        },
        "combined_real_reliability_interface": {
            "description": "Use additive, specialist-margin, and real scFoundation neighbor risk.",
            "policy": reliability_policy(COMBINED_WEIGHTS),
        },
        "combined_random_same_gene_control": {
            "description": "Same combined policy, but neighbor risk comes from random same-gene control.",
            "policy": reliability_policy(COMBINED_WEIGHTS, signal_key=RANDOM_CONTROL_KEY),
        },
        "combined_shuffled_readout_control": {
            "description": "Same combined policy, but neighbor risk comes from shuffled readout-gene control.",
            "policy": reliability_policy(COMBINED_WEIGHTS, signal_key=SHUFFLED_CONTROL_KEY),
        },
        "combined_inverted_control": {
            "description": "Same combined policy, but risk is inverted before action selection.",
            "policy": reliability_policy(COMBINED_WEIGHTS, invert=True),
        },
    }


def reliability_policy(
    weights: dict[str, float],
    *,
    signal_key: str = REAL_SIGNAL_KEY,
    invert: bool = False,
    action_threshold: float = ACTION_THRESHOLD,
):
    """Build a deterministic action policy from reliability-risk weights."""

    def policy(panel: dict[str, Any]) -> dict[str, str]:
        actions = {}
        for edge in panel["edges"]:
            card = reliability_card(
                panel_id=str(panel["panel_id"]),
                edge=edge,
                weights=weights,
                signal_key=signal_key,
                invert=invert,
                action_threshold=action_threshold,
            )
            actions[str(edge["gene"])] = card["recommended_action"]
        return actions

    return policy


def reliability_card(
    *,
    panel_id: str,
    edge: dict[str, Any],
    weights: dict[str, float],
    signal_key: str = REAL_SIGNAL_KEY,
    invert: bool = False,
    action_threshold: float = ACTION_THRESHOLD,
) -> dict[str, Any]:
    """Build the model-visible reliability card for one edge."""
    risks = {
        "additive_disagreement_risk": additive_disagreement_risk(edge),
        "sfm_margin_risk": sfm_margin_risk(edge),
        "scfoundation_neighbor_disagreement_risk": scfoundation_neighbor_disagreement_risk(
            panel_id,
            edge,
            signal_key=signal_key,
        ),
    }
    risk = sum(float(weights.get(name, 0.0)) * value for name, value in risks.items())
    risk = max(0.0, min(1.0, risk))
    if invert:
        risk = 1.0 - risk
    if risk >= action_threshold:
        action = "default_baseline" if edge["baseline_signal"].get("call_disagreement") else "verify_assay"
    else:
        action = "trust_sfm"
    return {
        "risk_bucket": risk_bucket(risk),
        "estimated_sfm_wrong_risk": _round(risk),
        "recommended_action": action,
        "evidence_basis": [
            name
            for name, weight in sorted(weights.items())
            if weight > 0
        ],
        "component_risks": {name: _round(value) for name, value in sorted(risks.items())},
        "calibration_status": "offline_gate_not_biology_calibrated",
    }


def additive_disagreement_risk(edge: dict[str, Any]) -> float:
    baseline = edge.get("baseline_signal", {})
    disagreement = 1.0 if baseline.get("call_disagreement") else 0.0
    gap = min(float(baseline.get("abs_fm_minus_baseline", 0.0)), 1.0)
    return max(0.0, min(1.0, 0.5 * disagreement + 0.5 * gap))


def sfm_margin_risk(edge: dict[str, Any]) -> float:
    """Risk is high near the absolute log2FC effect/no-effect call threshold."""
    abs_log2fc = abs(float(edge.get("fm", {}).get("log2fc", 0.0)))
    distance = abs(abs_log2fc - EFFECT_CALL_THRESHOLD)
    return max(0.0, min(1.0, 1.0 - distance / MARGIN_WINDOW))


def scfoundation_neighbor_disagreement_risk(
    panel_id: str,
    edge: dict[str, Any],
    *,
    signal_key: str = REAL_SIGNAL_KEY,
) -> float:
    signal_record = edge.get("_phase1c_signal_record")
    if signal_record is None:
        return 0.0
    signal = signal_record.get(signal_key, {})
    value = signal.get("neighbor_sfm_call_disagreement_rate")
    return float(value) if isinstance(value, (int, float)) else 0.0


def attach_signal_records(
    panels: list[dict[str, Any]],
    signal_map: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Copy selected panels and attach hidden signal records for policies."""
    out = []
    for panel in select_signal_matched_panels(panels, signal_map):
        copied_panel = dict(panel)
        copied_edges = []
        for edge in panel["edges"]:
            copied_edge = dict(edge)
            copied_edge["_phase1c_signal_record"] = signal_map[(str(panel["panel_id"]), str(edge["gene"]))]
            copied_edges.append(copied_edge)
        copied_panel["edges"] = copied_edges
        out.append(copied_panel)
    return out


def phase1b_reference_scores(phase1b_summary: dict[str, Any]) -> dict[str, dict[str, float]]:
    by_cue = phase1b_summary["by_cue_condition_lambda_0.5"]
    references = {}
    for label, cue in REFERENCE_CUES.items():
        row = by_cue[cue]
        references[label] = {
            "cue_condition": cue,
            "net_reward_per_gene": _round(row["net_reward_per_gene_lambda_0.5"]),
            "accuracy": _round(row["accuracy"]),
            "assays_per_gene": _round(row["assays_per_gene"]),
            "trust_error_rate": _round(row["trust_error_rate"]),
        }
    return references


def _gate_decision(
    lambda_05_scores: dict[str, dict[str, float]],
    references: dict[str, dict[str, float]],
) -> dict[str, Any]:
    real = lambda_05_scores["combined_real_reliability_interface"]["net_reward_per_gene"]
    no_signal = references["no_signal_llm"]["net_reward_per_gene"]
    raw = references["raw_edge_neighbor_llm"]["net_reward_per_gene"]
    random_control = lambda_05_scores["combined_random_same_gene_control"]["net_reward_per_gene"]
    shuffled_control = lambda_05_scores["combined_shuffled_readout_control"]["net_reward_per_gene"]
    inverted_control = lambda_05_scores["combined_inverted_control"]["net_reward_per_gene"]
    best_control = max(random_control, shuffled_control, inverted_control)
    margin_only = lambda_05_scores["sfm_margin_only_interface"]["net_reward_per_gene"]
    additive_only = lambda_05_scores["additive_only_interface"]["net_reward_per_gene"]
    neighbor_only = lambda_05_scores["neighbor_only_real_interface"]["net_reward_per_gene"]

    checks = {
        "beats_no_signal_llm": real > no_signal,
        "beats_raw_edge_neighbor_llm": real > raw,
        "beats_best_control": real > best_control,
        "beats_margin_only_ablation": real > margin_only,
        "beats_additive_only_ablation": real > additive_only,
        "beats_neighbor_only_ablation": real > neighbor_only,
    }
    if all(checks.values()):
        decision = "eligible_for_small_phase1c_interface_pilot"
    elif checks["beats_no_signal_llm"] and checks["beats_raw_edge_neighbor_llm"]:
        decision = "partial_pass_redesign_before_llm"
    else:
        decision = "do_not_run_phase1c_llm_pilot"
    return {
        "decision": decision,
        "checks": checks,
        "lambda_0.5_net_reward_per_gene": {
            "combined_real_reliability_interface": _round(real),
            "no_signal_llm": _round(no_signal),
            "raw_edge_neighbor_llm": _round(raw),
            "combined_random_same_gene_control": _round(random_control),
            "combined_shuffled_readout_control": _round(shuffled_control),
            "combined_inverted_control": _round(inverted_control),
            "sfm_margin_only_interface": _round(margin_only),
            "additive_only_interface": _round(additive_only),
            "neighbor_only_real_interface": _round(neighbor_only),
        },
        "margins": {
            "vs_no_signal_llm": _round(real - no_signal),
            "vs_raw_edge_neighbor_llm": _round(real - raw),
            "vs_best_control": _round(real - best_control),
            "vs_margin_only": _round(real - margin_only),
        },
    }


def _interpretation(decision: dict[str, Any]) -> dict[str, str]:
    if decision["decision"] == "eligible_for_small_phase1c_interface_pilot":
        short = (
            "The fixed reliability interface clears the offline gate, but any LLM "
            "pilot should remain small because the control margin is still modest."
        )
        next_step = "Build Phase 1C request JSONL for a small interface pilot."
    elif decision["decision"] == "partial_pass_redesign_before_llm":
        short = (
            "The reliability interface beats no-signal/raw LLM references, but "
            "does not clearly beat all controls or ablations."
        )
        next_step = "Redesign the interface before any new Claude call."
    else:
        short = (
            "The reliability interface does not clear the offline gate; do not "
            "spend on a Phase 1C LLM pilot."
        )
        next_step = "Redesign deterministic reliability features first."
    return {
        "short_read": short,
        "next_step": next_step,
    }


def _assert_offline_gate_allows_pilot(offline_gate: dict[str, Any]) -> None:
    decision = offline_gate.get("decision", {}).get("decision")
    if decision != "eligible_for_small_phase1c_interface_pilot":
        raise ValueError(f"Phase 1C offline gate does not allow an LLM pilot: {decision!r}")


def _compact_score(score: dict[str, Any]) -> dict[str, float]:
    keys = [
        "n_panels",
        "n_genes",
        "accuracy",
        "net_reward",
        "net_reward_per_gene",
        "assays_per_gene",
        "trust_error_rate",
        "verify_precision",
        "verify_recall",
        "default_baseline_rate",
        "default_error_rate",
        "defer_rate",
    ]
    return {key: _round(score[key]) if isinstance(score.get(key), float) else score[key] for key in keys}


def risk_bucket(risk: float) -> str:
    if risk >= 0.67:
        return "high"
    if risk >= 0.34:
        return "medium"
    return "low"


def _artifact_record(path: str) -> dict[str, Any]:
    return {
        "path": path,
        "sha256": _sha256(path) if os.path.exists(path) else None,
    }


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(payload: dict[str, Any], out: str) -> None:
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _round(value: float) -> float:
    return round(float(value), 6)
