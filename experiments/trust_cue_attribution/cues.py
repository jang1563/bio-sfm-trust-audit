"""Cue-condition evidence packet generation."""

from __future__ import annotations

import hashlib
import math

ACTIONS = ["trust_sfm", "verify_assay", "default_baseline", "defer"]
CUE_CONDITIONS = [
    "no_cue",
    "model_name_shown",
    "anonymized_genes",
    "confidence_shown",
    "additive_disagreement_shown",
    "misleading_reliability_card",
    "raw_assay_stats_shown",
]


def _anon_gene(panel_id: str, gene: str) -> str:
    digest = hashlib.sha1(f"{panel_id}:{gene}".encode()).hexdigest()[:6].upper()
    return f"GENE_{digest}"


def _confidence(edge: dict) -> float:
    # Presentation cue only: magnitude-derived pseudo-confidence, not calibrated truth.
    return round(min(0.99, 0.50 + min(abs(edge["fm"]["log2fc"]), 1.0) * 0.45), 3)


def _clean_number(value, digits: int | None = 3):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return round(float(value), digits) if digits is not None else int(value)


def _reliability_card(edge: dict, misleading: bool = False) -> dict:
    score = float(edge["reliability_signal"]["score"])
    label = edge["reliability_signal"]["label"]
    if misleading:
        label = "low_sfm_error_risk" if label == "high_sfm_error_risk" else "high_sfm_error_risk"
        score = max(0.0, 1.0 - min(score, 1.0))
    return {"source": edge["reliability_signal"]["source"], "score": round(score, 3), "label": label}


def evidence_packet(panel: dict, cue_condition: str) -> dict:
    if cue_condition not in CUE_CONDITIONS:
        raise ValueError(f"unknown cue condition {cue_condition!r}")
    show_name = cue_condition == "model_name_shown"
    anonymize = cue_condition == "anonymized_genes"
    show_conf = cue_condition == "confidence_shown"
    show_add = cue_condition == "additive_disagreement_shown"
    misleading = cue_condition == "misleading_reliability_card"
    show_assay = cue_condition == "raw_assay_stats_shown"
    genes = []
    scoring_key = []
    for edge in panel["edges"]:
        gene_display = _anon_gene(panel["panel_id"], edge["gene"]) if anonymize else edge["gene"]
        rec = {
            "gene_display": gene_display,
            "sfm_call": edge["fm"]["call"],
            "sfm_log2fc": round(float(edge["fm"]["log2fc"]), 3),
        }
        scoring_key.append({"gene_display": gene_display, "gene": edge["gene"], "edge_id": edge["edge_id"]})
        if show_conf:
            rec["sfm_confidence"] = _confidence(edge)
            rec["sfm_confidence_source"] = "magnitude_proxy_not_calibrated"
        if show_add:
            rec["baseline_signal"] = {
                "source": edge["baseline_signal"]["source"],
                "baseline_call": edge["baseline_signal"]["call"],
                "baseline_log2fc": round(float(edge["baseline_signal"]["log2fc"]), 3),
                "abs_fm_minus_baseline": round(float(edge["baseline_signal"]["abs_fm_minus_baseline"]), 3),
                "call_disagreement": bool(edge["baseline_signal"]["call_disagreement"]),
            }
        if misleading:
            rec["reliability_card"] = _reliability_card(edge, misleading=True)
        if show_assay:
            raw = edge.get("raw", {})
            rec["assay_stats"] = {
                "source": "heldout_measured_de_positive_control",
                "raw_log2FC": _clean_number(raw.get("raw_log2FC")),
                "raw_se": _clean_number(raw.get("raw_se")),
                "raw_q": _clean_number(raw.get("raw_q"), digits=6),
                "n_trt": _clean_number(raw.get("n_trt"), digits=None),
                "n_cntrl": _clean_number(raw.get("n_cntrl"), digits=None),
                "leakage_note": "measured assay statistics; positive-control cue only",
            }
        genes.append(rec)
    display_name = panel["edges"][0]["fm"]["model_name"] if show_name and panel["edges"] else "specialist model A"
    return {
        "packet_id": f"{panel['panel_id']}::{cue_condition}",
        "panel_id": panel["panel_id"],
        "cue_condition": cue_condition,
        "available_actions": ACTIONS,
        "scoring_key": scoring_key,
        "evidence_packet": {
            "model_card": {
                "display_name": display_name,
                "adapter": panel["adapter"] if show_name else "hidden",
            },
            "perturbation": panel["perturbation"],
            "genes": genes,
        },
    }


def generate_cue_packets(panels: list[dict], cue_conditions: list[str] | None = None) -> list[dict]:
    conditions = cue_conditions or CUE_CONDITIONS
    return [evidence_packet(panel, cue) for panel in panels for cue in conditions]
