"""Model-visible packet features for router baselines."""

from __future__ import annotations

from collections import Counter
from statistics import mean
from typing import Any


def observation_features(observation: dict[str, Any]) -> dict[str, Any]:
    """Extract router features from model-visible observation only."""
    evidence = observation.get("evidence_packet", {})
    genes = list(evidence.get("genes", []))
    model_card = evidence.get("model_card", {})
    n = len(genes)

    sfm_abs = [_abs_float(gene.get("sfm_log2fc")) for gene in genes if gene.get("sfm_log2fc") is not None]
    sfm_calls = [str(gene.get("sfm_call", "unknown")) for gene in genes]
    confidence = [_float(gene.get("sfm_confidence")) for gene in genes if gene.get("sfm_confidence") is not None]
    baseline_genes = [gene for gene in genes if "baseline_signal" in gene]
    reliability_genes = [gene for gene in genes if "reliability_card" in gene]
    assay_genes = [gene for gene in genes if "assay_stats" in gene]
    internal_signal = evidence.get("internal_signal_summary", {})

    baseline_abs_diff = [
        _float(gene["baseline_signal"].get("abs_fm_minus_baseline"))
        for gene in baseline_genes
        if gene["baseline_signal"].get("abs_fm_minus_baseline") is not None
    ]
    baseline_sources = [str(gene["baseline_signal"].get("source", "unknown")) for gene in baseline_genes]
    reliability_scores = [
        _float(gene["reliability_card"].get("score"))
        for gene in reliability_genes
        if gene["reliability_card"].get("score") is not None
    ]
    reliability_labels = [str(gene["reliability_card"].get("label", "unknown")) for gene in reliability_genes]
    gene_labels = [str(gene.get("gene_display", "")) for gene in genes]

    return {
        "packet_id": observation.get("packet_id"),
        "panel_id": observation.get("panel_id"),
        "cue_condition": observation.get("cue_condition", "unknown"),
        "n_genes": n,
        "model_name_visible": int(str(model_card.get("adapter", "hidden")) != "hidden"),
        "anonymized_gene_rate": _rate(gene_labels, lambda label: label.startswith("GENE_")),
        "sfm_effect_rate": _rate(sfm_calls, lambda call: call == "effect"),
        "sfm_no_effect_rate": _rate(sfm_calls, lambda call: call == "no_effect"),
        "sfm_abs_log2fc_mean": mean(sfm_abs) if sfm_abs else 0.0,
        "sfm_abs_log2fc_max": max(sfm_abs) if sfm_abs else 0.0,
        "sfm_abs_log2fc_min": min(sfm_abs) if sfm_abs else 0.0,
        "confidence_present_rate": len(confidence) / n if n else 0.0,
        "confidence_mean": mean(confidence) if confidence else 0.0,
        "confidence_min": min(confidence) if confidence else 0.0,
        "baseline_present_rate": len(baseline_genes) / n if n else 0.0,
        "baseline_call_disagreement_rate": _rate(
            baseline_genes,
            lambda gene: bool(gene["baseline_signal"].get("call_disagreement")),
        ),
        "baseline_abs_diff_mean": mean(baseline_abs_diff) if baseline_abs_diff else 0.0,
        "baseline_observed_additive_rate": _rate(baseline_sources, lambda source: source == "observed_additive"),
        "baseline_no_change_rate": _rate(baseline_sources, lambda source: source == "no_change"),
        "reliability_present_rate": len(reliability_genes) / n if n else 0.0,
        "reliability_high_risk_rate": _rate(reliability_labels, lambda label: label == "high_sfm_error_risk"),
        "reliability_score_mean": mean(reliability_scores) if reliability_scores else 0.0,
        "assay_stats_present_rate": len(assay_genes) / n if n else 0.0,
        "internal_signal_present": int(bool(internal_signal)),
        "internal_signal_embedding_dim": int(internal_signal.get("embedding_dim") or 0) if internal_signal else 0,
        "internal_signal_finite_fraction": _float(internal_signal.get("embedding_finite_fraction", 0.0)) if internal_signal else 0.0,
        "internal_signal_scope": str(internal_signal.get("signal_scope", "absent")) if internal_signal else "absent",
    }


def trajectory_feature_row(trajectory: dict[str, Any]) -> dict[str, Any]:
    """Return one feature row with reward metadata for analysis."""
    features = observation_features(trajectory.get("observation", {}))
    return {
        **features,
        "trajectory_id": trajectory.get("trajectory_id"),
        "model": trajectory.get("model", "unknown"),
        "reward": float(trajectory.get("reward", 0.0)),
        "reward_per_gene": float(trajectory.get("reward_per_gene", 0.0)),
        "score": trajectory.get("score", {}),
        "feature_signature": feature_signature(features),
    }


def trajectory_feature_rows(trajectories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [trajectory_feature_row(trajectory) for trajectory in trajectories]


def feature_signature(features: dict[str, Any]) -> str:
    """Compact binned signature for low-data router baselines."""
    parts = [
        f"cue={features.get('cue_condition', 'unknown')}",
        f"n={_bin(float(features.get('n_genes', 0)), (20, 28), ('small', 'medium', 'large'))}",
        f"sfm_effect={_bin(float(features.get('sfm_effect_rate', 0.0)), (0.33, 0.66), ('low', 'mid', 'high'))}",
        f"sfm_abs={_bin(float(features.get('sfm_abs_log2fc_mean', 0.0)), (0.25, 0.75), ('low', 'mid', 'high'))}",
        f"confidence={'yes' if float(features.get('confidence_present_rate', 0.0)) > 0 else 'no'}",
        f"baseline={_baseline_signature(features)}",
        f"reliability={_reliability_signature(features)}",
        f"anonymized={'yes' if float(features.get('anonymized_gene_rate', 0.0)) > 0.5 else 'no'}",
        f"internal_signal={'yes' if int(features.get('internal_signal_present', 0)) else 'no'}",
    ]
    return "|".join(parts)


def summarize_feature_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cue_counts = Counter(str(row.get("cue_condition", "unknown")) for row in rows)
    signature_counts = Counter(str(row.get("feature_signature", "unknown")) for row in rows)
    model_counts = Counter(str(row.get("model", "unknown")) for row in rows)
    return {
        "n_rows": len(rows),
        "n_signatures": len(signature_counts),
        "cue_counts": dict(sorted(cue_counts.items())),
        "model_counts": dict(sorted(model_counts.items())),
        "top_signatures": dict(signature_counts.most_common(12)),
    }


def _baseline_signature(features: dict[str, Any]) -> str:
    if float(features.get("baseline_present_rate", 0.0)) <= 0:
        return "absent"
    rate = float(features.get("baseline_call_disagreement_rate", 0.0))
    return _bin(rate, (0.2, 0.5), ("agreeing", "mixed", "disagreeing"))


def _reliability_signature(features: dict[str, Any]) -> str:
    if float(features.get("reliability_present_rate", 0.0)) <= 0:
        return "absent"
    rate = float(features.get("reliability_high_risk_rate", 0.0))
    return _bin(rate, (0.2, 0.5), ("mostly_low", "mixed", "mostly_high"))


def _bin(value: float, thresholds: tuple[float, float], labels: tuple[str, str, str]) -> str:
    if value < thresholds[0]:
        return labels[0]
    if value < thresholds[1]:
        return labels[1]
    return labels[2]


def _rate(values, predicate) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(1 for value in values if predicate(value)) / len(values)


def _float(value) -> float:
    return float(value)


def _abs_float(value) -> float:
    return abs(_float(value))
