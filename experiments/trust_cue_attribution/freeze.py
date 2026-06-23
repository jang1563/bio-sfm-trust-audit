"""Phase 0 freeze utilities.

The freeze command writes compact, tracked artifacts from larger ignored HPC
outputs. It deliberately recomputes scorer-dependent summaries from episode
JSONL files so the frozen numbers match the current code.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .baselines import run_baselines
    from .analysis import cue_attribution_regression, explanation_faithfulness_gap, gene_level_rows, paired_cue_effects
    from .episodes import score_episode_records
    from .io_utils import read_jsonl
    from .scoring import LAMBDAS, cue_attribution_summary
except ImportError:  # direct script/test execution from this directory
    from baselines import run_baselines
    from analysis import cue_attribution_regression, explanation_faithfulness_gap, gene_level_rows, paired_cue_effects
    from episodes import score_episode_records
    from io_utils import read_jsonl
    from scoring import LAMBDAS, cue_attribution_summary


PHASE0A_SOURCE_FILES = {
    "panels_full": "panels_full.jsonl",
    "panels_additive": "panels_additive.jsonl",
    "cue_packets_full": "cue_packets_full.jsonl",
    "requests_full": "requests_full.jsonl",
    "requests_pilot72_main": "requests_pilot72_main.jsonl",
    "requests_pilot72_main_manifest": "requests_pilot72_main_manifest.json",
    "baselines_full": "baselines_full.json",
    "baselines_additive": "baselines_additive.json",
    "sonnet_4_6_episodes": "llm_claude-sonnet-4-6_pilot72_main_episodes.jsonl",
    "opus_4_8_episodes": "llm_claude-opus-4-8_pilot72_main_episodes.jsonl",
    "sonnet_4_6_trajectories": "llm_claude-sonnet-4-6_pilot72_main_trajectories.jsonl",
    "opus_4_8_trajectories": "llm_claude-opus-4-8_pilot72_main_trajectories.jsonl",
    "preference_summary": "llm_sonnet4_6_vs_opus4_8_pilot72_preference_summary.json",
    "cue_router_eval": "llm_sonnet4_6_vs_opus4_8_pilot72_router_eval.json",
    "feature_summary": "llm_sonnet4_6_vs_opus4_8_pilot72_feature_summary.json",
    "feature_signature_router_eval": "llm_sonnet4_6_vs_opus4_8_pilot72_feature_signature_router_eval.json",
}

PHASE0B_SOURCE_FILES = {
    "panels_full": "panels_full.jsonl",
    "panels_additive": "panels_additive.jsonl",
    "cue_packets_full": "cue_packets_full.jsonl",
    "requests_full_nonleakage": "requests_full_nonleakage.jsonl",
    "baselines_full": "baselines_full.json",
    "baselines_additive": "baselines_additive.json",
    "sonnet_4_6_phase0b_episodes": "llm_claude-sonnet-4-6_phase0b_main_episodes.jsonl",
    "sonnet_4_6_phase0b_trajectories": "llm_claude-sonnet-4-6_phase0b_main_trajectories.jsonl",
    "sonnet_4_6_phase0b_trajectory_summary": "llm_claude-sonnet-4-6_phase0b_main_trajectory_summary.json",
    "sonnet_4_6_phase0b_analysis": "llm_claude-sonnet-4-6_phase0b_main_analysis.json",
    "sonnet_4_6_phase0b_scores_lambda_0.2": "llm_claude-sonnet-4-6_phase0b_main_scores_lambda_0.2.json",
    "sonnet_4_6_phase0b_scores_lambda_0.5": "llm_claude-sonnet-4-6_phase0b_main_scores_lambda_0.5.json",
    "sonnet_4_6_phase0b_scores_lambda_0.8": "llm_claude-sonnet-4-6_phase0b_main_scores_lambda_0.8.json",
    "sonnet_4_6_phase0b_paired_effects_lambda_0.2": "llm_claude-sonnet-4-6_phase0b_main_paired_effects_lambda_0.2.json",
    "sonnet_4_6_phase0b_paired_effects_lambda_0.5": "llm_claude-sonnet-4-6_phase0b_main_paired_effects_lambda_0.5.json",
    "sonnet_4_6_phase0b_paired_effects_lambda_0.8": "llm_claude-sonnet-4-6_phase0b_main_paired_effects_lambda_0.8.json",
    "sonnet_4_6_phase0b_cue_attribution": "llm_claude-sonnet-4-6_phase0b_main_cue_attribution.json",
    "sonnet_4_6_phase0b_explanation_faithfulness": "llm_claude-sonnet-4-6_phase0b_main_explanation_faithfulness.json",
}

PHASE0A_EXPECTED_COUNTS = {
    "panels_full": 107,
    "panels_additive": 45,
    "cue_packets_full": 749,
    "requests_full": 749,
    "requests_pilot72_main": 72,
    "sonnet_4_6_episodes": 72,
    "opus_4_8_episodes": 72,
}

PHASE0B_EXPECTED_COUNTS = {
    "panels_full": 107,
    "panels_additive": 45,
    "cue_packets_full": 749,
    "requests_full_nonleakage": 642,
    "sonnet_4_6_phase0b_episodes": 642,
    "sonnet_4_6_phase0b_trajectories": 642,
}

MAIN_NON_LEAKAGE_CUES = [
    "no_cue",
    "model_name_shown",
    "anonymized_genes",
    "confidence_shown",
    "additive_disagreement_shown",
    "misleading_reliability_card",
]

KEY_CUES = [
    "confidence_shown",
    "additive_disagreement_shown",
    "misleading_reliability_card",
]

METRIC_KEYS = [
    "n_panels",
    "n_genes",
    "accuracy",
    "assays_per_gene",
    "net_reward_per_gene",
    "sfm_wrong_rate",
    "trust_error_rate",
    "verify_precision",
    "verify_recall",
    "default_baseline_rate",
    "default_observed_additive_rate",
    "default_no_change_rate",
    "default_error_rate",
    "defer_rate",
    "coverage_rate",
]

FREEZE_FLOAT_DIGITS = 12


def build_phase0a_freeze(input_dir: str, out_dir: str, strict_counts: bool = True) -> dict[str, Any]:
    """Build and write `manifest.json` and `summary.json` for Phase 0A."""
    input_path = Path(input_dir)
    output_path = Path(out_dir)
    paths = _source_paths(input_path)
    _require_sources(paths)

    panels_full = read_jsonl(str(paths["panels_full"]))
    panels_additive = read_jsonl(str(paths["panels_additive"]))
    cue_packets_full = read_jsonl(str(paths["cue_packets_full"]))
    requests_full = read_jsonl(str(paths["requests_full"]))
    requests_pilot = read_jsonl(str(paths["requests_pilot72_main"]))
    sonnet_episodes = read_jsonl(str(paths["sonnet_4_6_episodes"]))
    opus_episodes = read_jsonl(str(paths["opus_4_8_episodes"]))

    with open(paths["requests_pilot72_main_manifest"]) as handle:
        pilot_manifest = json.load(handle)
    with open(paths["baselines_full"]) as handle:
        baselines_full = json.load(handle)
    with open(paths["baselines_additive"]) as handle:
        baselines_additive = json.load(handle)
    with open(paths["preference_summary"]) as handle:
        preference_summary = json.load(handle)
    with open(paths["cue_router_eval"]) as handle:
        cue_router_eval = json.load(handle)
    with open(paths["feature_summary"]) as handle:
        feature_summary = json.load(handle)
    with open(paths["feature_signature_router_eval"]) as handle:
        feature_router_eval = json.load(handle)

    counts = {
        "panels_full": len(panels_full),
        "panels_additive": len(panels_additive),
        "cue_packets_full": len(cue_packets_full),
        "requests_full": len(requests_full),
        "requests_pilot72_main": len(requests_pilot),
        "sonnet_4_6_episodes": len(sonnet_episodes),
        "opus_4_8_episodes": len(opus_episodes),
    }
    cue_conditions = sorted({row["cue_condition"] for row in requests_pilot})
    panel_balance = _panel_balance(pilot_manifest)

    summary = {
        "phase": "phase0a",
        "status": "frozen_method_validation_pilot",
        "claim_boundary": "method-validation pilot only; no full-642, true-SFM, internal-signal, or post-training claim",
        "metric_basis": {
            "primary": "micro_gene_weighted",
            "diagnostic": "macro_panel_*",
            "lambda_values": list(LAMBDAS),
            "defer_penalty": 0.0,
        },
        "counts": counts,
        "cue_conditions": cue_conditions,
        "pilot_panel_balance": panel_balance,
        "baselines": {
            "full": _compact_baselines(baselines_full),
            "additive_coverage": _compact_baselines(baselines_additive),
        },
        "llm_pilot": {
            "sonnet_4_6": _llm_model_summary(panels_full, cue_packets_full, sonnet_episodes),
            "opus_4_8": _llm_model_summary(panels_full, cue_packets_full, opus_episodes),
        },
        "preference_summary": preference_summary,
        "router_summaries": {
            "cue_condition": _compact_router_eval(cue_router_eval),
            "feature_signature": _compact_router_eval(feature_router_eval),
            "feature_summary": feature_summary,
            "claim_guardrail": "router is infrastructure only; current pilot routers do not beat always-Sonnet under primary net reward",
        },
    }
    summary["lambda_sweep"] = _lambda_sweep(summary["llm_pilot"])
    summary["sanity_checks"] = _sanity_checks(summary)

    if strict_counts:
        _validate_counts(counts, PHASE0A_EXPECTED_COUNTS)
        _validate_cues(cue_conditions)
        _validate_panel_balance(panel_balance)
        _validate_sanity(summary["sanity_checks"])

    manifest = {
        "phase": "phase0a",
        "git_commit": _git_commit(),
        "git_commit_role": "HEAD at freeze generation; final artifact commit may differ because commit hashes cannot self-reference generated files",
        "input_dir": _display_path(input_path),
        "output_dir": _display_path(output_path),
        "source_artifacts": {
            key: _artifact_metadata(path)
            for key, path in sorted(paths.items())
        },
        "counts": counts,
        "cue_conditions": cue_conditions,
        "models": ["claude-sonnet-4-6", "claude-opus-4-8"],
        "lambda_values": list(LAMBDAS),
        "scorer_settings": {
            "primary_aggregate": "micro_gene_weighted",
            "macro_panel_prefix": "macro_panel_*",
            "defer_penalty": 0.0,
            "raw_assay_stats_shown": "positive_control_excluded_from_main_pilot",
        },
        "tracked_outputs": ["manifest.json", "summary.json"],
    }

    manifest = _normalize_json_floats(manifest)
    summary = _normalize_json_floats(summary)

    output_path.mkdir(parents=True, exist_ok=True)
    _write_json(output_path / "manifest.json", manifest)
    _write_json(output_path / "summary.json", summary)
    return {"manifest": manifest, "summary": summary}


def build_phase0b_freeze(input_dir: str, out_dir: str, strict_counts: bool = True) -> dict[str, Any]:
    """Build and write `manifest.json` and `summary.json` for Phase 0B."""
    input_path = Path(input_dir)
    output_path = Path(out_dir)
    paths = _source_paths(input_path, PHASE0B_SOURCE_FILES)
    _require_sources(paths, "Phase 0B")

    panels_full = read_jsonl(str(paths["panels_full"]))
    panels_additive = read_jsonl(str(paths["panels_additive"]))
    cue_packets_full = read_jsonl(str(paths["cue_packets_full"]))
    requests_nonleakage = read_jsonl(str(paths["requests_full_nonleakage"]))
    sonnet_episodes = read_jsonl(str(paths["sonnet_4_6_phase0b_episodes"]))
    sonnet_trajectories = read_jsonl(str(paths["sonnet_4_6_phase0b_trajectories"]))

    baselines_full = run_baselines(panels_full)
    baselines_additive = run_baselines(panels_additive)

    counts = {
        "panels_full": len(panels_full),
        "panels_additive": len(panels_additive),
        "cue_packets_full": len(cue_packets_full),
        "requests_full_nonleakage": len(requests_nonleakage),
        "sonnet_4_6_phase0b_episodes": len(sonnet_episodes),
        "sonnet_4_6_phase0b_trajectories": len(sonnet_trajectories),
    }
    cue_conditions = sorted({row["cue_condition"] for row in requests_nonleakage})
    cue_counts = dict(sorted(Counter(row["cue_condition"] for row in requests_nonleakage).items()))
    panel_count = len({row["panel_id"] for row in requests_nonleakage})
    episode_integrity = _episode_integrity(cue_packets_full, sonnet_episodes)

    full_run = _llm_model_summary(
        panels_full,
        cue_packets_full,
        sonnet_episodes,
        paired_cues=[cue for cue in MAIN_NON_LEAKAGE_CUES if cue != "no_cue"],
        attribution_cues=[cue for cue in MAIN_NON_LEAKAGE_CUES if cue != "no_cue"],
    )

    summary = {
        "phase": "phase0b",
        "status": "frozen_full_nonleakage_sonnet_run",
        "claim_boundary": "GEARS/Norman dry-run method-validation only; no true-SFM, internal-signal, or calibrated-orchestrator claim",
        "metric_basis": {
            "primary": "micro_gene_weighted",
            "diagnostic": "macro_panel_*",
            "lambda_values": list(LAMBDAS),
            "defer_penalty": 0.0,
            "baselines": "recomputed_from_current_panel_jsonl",
        },
        "counts": counts,
        "biological_panel_count": panel_count,
        "cue_conditions": cue_conditions,
        "cue_counts": cue_counts,
        "baselines": {
            "full": _compact_baselines(baselines_full),
            "additive_coverage": _compact_baselines(baselines_additive),
        },
        "llm_full_run": {
            "sonnet_4_6": full_run,
        },
        "episode_integrity": episode_integrity,
    }
    summary["baseline_comparison"] = _phase0b_baseline_comparison(summary)
    summary["cue_level_highlights"] = _phase0b_cue_level_highlights(summary)
    summary["claim_update"] = {
        "supported": [
            "Full non-leakage Sonnet routing is strongly cue-sensitive.",
            "Additive-disagreement evidence improves routing relative to no_cue.",
            "Misleading reliability framing changes behavior and hurts accuracy/net reward.",
            "Self-reported explanations frequently mention unavailable evidence.",
            "The oracle gap shows useful routing signal remains uncaptured.",
        ],
        "not_supported": [
            "The LLM is a robust calibrated SFM orchestrator.",
            "The result generalizes to true SFMs.",
            "Confidence-like cues are calibrated uncertainty.",
            "The learned/router layer is ready.",
            "Internal SFM signals are being used faithfully.",
        ],
        "best_current_claim": (
            "In a full GEARS/Norman dry run, the LLM reasoning layer is strongly "
            "cue-sensitive and only weakly calibrated as a cost-aware orchestrator. "
            "Explicit reliability signals can improve routing, but reliability-looking "
            "cues can also mislead it; explanations often report unavailable evidence."
        ),
    }
    summary["sanity_checks"] = _phase0b_sanity_checks(summary)

    if strict_counts:
        _validate_counts(counts, PHASE0B_EXPECTED_COUNTS)
        _validate_phase0b_cues(cue_conditions, cue_counts)
        _validate_phase0b_integrity(episode_integrity)
        _validate_sanity(summary["sanity_checks"])

    manifest = {
        "phase": "phase0b",
        "git_commit": _git_commit(),
        "git_commit_role": "HEAD at freeze generation; final artifact commit may differ because commit hashes cannot self-reference generated files",
        "input_dir": _display_path(input_path),
        "output_dir": _display_path(output_path),
        "source_artifacts": {
            key: _artifact_metadata(path)
            for key, path in sorted(paths.items())
        },
        "counts": counts,
        "biological_panel_count": panel_count,
        "cue_conditions": cue_conditions,
        "cue_counts": cue_counts,
        "models": ["claude-sonnet-4-6"],
        "lambda_values": list(LAMBDAS),
        "scorer_settings": {
            "primary_aggregate": "micro_gene_weighted",
            "macro_panel_prefix": "macro_panel_*",
            "defer_penalty": 0.0,
            "raw_assay_stats_shown": "excluded_from_phase0b_full_nonleakage_run",
        },
        "tracked_outputs": ["manifest.json", "summary.json"],
    }

    manifest = _normalize_json_floats(manifest)
    summary = _normalize_json_floats(summary)

    output_path.mkdir(parents=True, exist_ok=True)
    _write_json(output_path / "manifest.json", manifest)
    _write_json(output_path / "summary.json", summary)
    return {"manifest": manifest, "summary": summary}


def _source_paths(input_dir: Path, source_files: dict[str, str] | None = None) -> dict[str, Path]:
    source_files = source_files or PHASE0A_SOURCE_FILES
    return {key: input_dir / filename for key, filename in source_files.items()}


def _require_sources(paths: dict[str, Path], phase: str = "Phase 0A") -> None:
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"missing {phase} source artifacts: " + ", ".join(missing))


def _compact_baselines(baselines: dict[str, dict[str, dict]]) -> dict[str, dict[str, dict]]:
    return {
        str(lam): {
            policy: _compact_metrics(metrics)
            for policy, metrics in sorted(policy_rows.items())
        }
        for lam, policy_rows in sorted(baselines.items(), key=lambda item: float(item[0]))
    }


def _llm_model_summary(
    panels: list[dict],
    packets: list[dict],
    episodes: list[dict],
    paired_cues: list[str] | None = None,
    attribution_cues: list[str] | None = None,
) -> dict[str, Any]:
    paired_cues = paired_cues or KEY_CUES
    attribution_cues = attribution_cues or KEY_CUES
    by_lambda = {}
    paired_key_cues = {}
    for lam in LAMBDAS:
        scored = score_episode_records(panels, packets, episodes, lam=lam)
        rows = scored["rows"]
        by_lambda[str(lam)] = {
            "overall": _compact_metrics(scored["summary"]),
            "by_cue_condition": {
                cue: _compact_metrics(metrics)
                for cue, metrics in cue_attribution_summary(rows).items()
            },
        }
        paired = paired_cue_effects(gene_level_rows(panels, packets, episodes, lam=lam), baseline_cue="no_cue")
        paired_key_cues[str(lam)] = {
            cue: _compact_paired_effect(paired.get(cue, {}))
            for cue in paired_cues
        }

    rows_05 = gene_level_rows(panels, packets, episodes, lam=0.5)
    attribution = cue_attribution_regression(rows_05, baseline_cue="no_cue")
    faithfulness = explanation_faithfulness_gap(episodes, rows_05, baseline_cue="no_cue")

    return {
        "n_episodes": len(episodes),
        "model": episodes[0].get("model", "unknown") if episodes else "unknown",
        "by_lambda": by_lambda,
        "paired_key_cues": paired_key_cues,
        "cue_attribution_highlights_lambda_0.5": _compact_cue_attribution(attribution, attribution_cues),
        "explanation_faithfulness_highlights_lambda_0.5": _compact_faithfulness(faithfulness),
    }


def _compact_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        key: metrics[key]
        for key in METRIC_KEYS
        if key in metrics
    }


def _compact_paired_effect(effect: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "n_pairs",
        "action_changed_rate",
        "delta_correct",
        "delta_assay",
        "delta_net",
        "delta_trust_error",
        "delta_verify_wrong",
    ]
    return {key: effect[key] for key in keys if key in effect}


def _compact_cue_attribution(attribution: dict[str, Any], cues: list[str] | None = None) -> dict[str, Any]:
    cues = cues or KEY_CUES
    out: dict[str, Any] = {}
    for cue in cues:
        out[cue] = {}
        for action in ("verify_assay", "trust_sfm", "default_baseline"):
            coef = attribution["models"][action]["coefficients"].get(cue, {})
            out[cue][action] = {
                key: coef[key]
                for key in ("log_odds_delta_vs_baseline", "rate_delta_vs_baseline", "rate", "baseline_rate")
                if key in coef
            }
    return out


def _phase0b_baseline_comparison(summary: dict[str, Any]) -> dict[str, Any]:
    out = {"metric_basis": "micro_gene_weighted", "delta_net_reward_per_gene": {}, "break_even_lambda": {}}
    sonnet_overall = summary["llm_full_run"]["sonnet_4_6"]["by_lambda"]
    for lam, values in sonnet_overall.items():
        sonnet_metrics = values["overall"]
        sonnet_net = sonnet_metrics["net_reward_per_gene"]
        out["delta_net_reward_per_gene"][lam] = {
            policy: sonnet_net - metrics["net_reward_per_gene"]
            for policy, metrics in summary["baselines"]["full"][lam].items()
        }

    sonnet_05 = sonnet_overall["0.5"]["overall"]
    for policy, metrics in summary["baselines"]["full"]["0.5"].items():
        delta_assay = sonnet_05["assays_per_gene"] - metrics["assays_per_gene"]
        if delta_assay == 0:
            out["break_even_lambda"][policy] = None
        else:
            out["break_even_lambda"][policy] = (sonnet_05["accuracy"] - metrics["accuracy"]) / delta_assay
    return out


def _phase0b_cue_level_highlights(summary: dict[str, Any]) -> dict[str, Any]:
    by_cue = summary["llm_full_run"]["sonnet_4_6"]["by_lambda"]["0.5"]["by_cue_condition"]
    paired = summary["llm_full_run"]["sonnet_4_6"]["paired_key_cues"]["0.5"]
    ranked_net = sorted(
        (
            {
                "cue_condition": cue,
                "net_reward_per_gene": metrics["net_reward_per_gene"],
                "accuracy": metrics["accuracy"],
                "assays_per_gene": metrics["assays_per_gene"],
                "trust_error_rate": metrics["trust_error_rate"],
                "default_baseline_rate": metrics["default_baseline_rate"],
            }
            for cue, metrics in by_cue.items()
        ),
        key=lambda row: row["net_reward_per_gene"],
        reverse=True,
    )
    return {
        "lambda": 0.5,
        "cue_ranked_by_net_reward_per_gene": ranked_net,
        "paired_effects_vs_no_cue": paired,
    }


def _compact_faithfulness(faithfulness: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for cue, row in sorted(faithfulness.get("cue_summaries", {}).items()):
        out[cue] = {
            "primary_dimension": row.get("primary_dimension"),
            "primary_explanation_rate": row.get("primary_explanation_rate"),
            "behavior_minus_explanation": row.get("behavior_minus_explanation"),
            "behavior": row.get("behavior", {}),
            "unavailable_self_reported_episode_rates": row.get("unavailable_self_reported_episode_rates", {}),
            "unavailable_rationale_episode_rates": row.get("unavailable_rationale_episode_rates", {}),
        }
    return out


def _compact_router_eval(router_eval: dict[str, Any]) -> dict[str, Any]:
    policies = {}
    for policy, row in sorted(router_eval.get("policies", {}).items()):
        policies[policy] = {
            "model_choice_counts": row.get("model_choice_counts", {}),
            "summary": _compact_metrics(row.get("summary", {})),
        }
    return {
        "n_input_trajectories": router_eval.get("n_input_trajectories"),
        "n_matched_packets": router_eval.get("n_matched_packets"),
        "feature_field": router_eval.get("feature_field"),
        "group_field": router_eval.get("group_field"),
        "models": router_eval.get("models", []),
        "policies": policies,
    }


def _lambda_sweep(llm_pilot: dict[str, Any]) -> dict[str, Any]:
    overall = {
        model: {
            lam: values["overall"]
            for lam, values in model_summary["by_lambda"].items()
        }
        for model, model_summary in llm_pilot.items()
    }
    sonnet = overall["sonnet_4_6"]["0.5"]
    opus = overall["opus_4_8"]["0.5"]
    break_even = break_even_lambda(
        sonnet_accuracy=sonnet["accuracy"],
        sonnet_assays_per_gene=sonnet["assays_per_gene"],
        opus_accuracy=opus["accuracy"],
        opus_assays_per_gene=opus["assays_per_gene"],
    )
    return {
        "metric_basis": "micro_gene_weighted",
        "overall": overall,
        "break_even_lambda_opus_vs_sonnet": break_even,
    }


def break_even_lambda(
    *,
    sonnet_accuracy: float,
    sonnet_assays_per_gene: float,
    opus_accuracy: float,
    opus_assays_per_gene: float,
) -> float | None:
    """Return lambda where Opus and Sonnet have equal net reward."""
    delta_assay = opus_assays_per_gene - sonnet_assays_per_gene
    if delta_assay == 0:
        return None
    return (opus_accuracy - sonnet_accuracy) / delta_assay


def _panel_balance(pilot_manifest: dict[str, Any]) -> dict[str, int]:
    return dict(sorted(Counter(panel.get("wrong_rate_bin", "unknown") for panel in pilot_manifest.get("panels", [])).items()))


def _sanity_checks(summary: dict[str, Any]) -> dict[str, Any]:
    full_05 = summary["baselines"]["full"]["0.5"]
    additive_05 = summary["baselines"]["additive_coverage"]["0.5"]
    router = summary["router_summaries"]["feature_signature"]["policies"]
    always_sonnet = router["always::claude-sonnet-4-6"]["summary"]["net_reward_per_gene"]
    feature_router = router["feature_signature_mean_leave_panel_id_out"]["summary"]["net_reward_per_gene"]
    oracle_router = router["oracle_packet"]["summary"]["net_reward_per_gene"]
    break_even = summary["lambda_sweep"]["break_even_lambda_opus_vs_sonnet"]
    return {
        "oracle_beats_random_full_lambda_0.5": full_05["oracle_verify"]["net_reward_per_gene"] > full_05["random_verify_at_budget"]["net_reward_per_gene"],
        "always_additive_beats_trust_all_on_additive_subset_lambda_0.5": additive_05["always_additive"]["net_reward_per_gene"] > additive_05["trust_all_sfm"]["net_reward_per_gene"],
        "opus_sonnet_break_even_lambda_near_0.234": break_even is not None and abs(break_even - 0.234) <= 0.03,
        "feature_router_does_not_beat_always_sonnet_lambda_0.5": feature_router <= always_sonnet,
        "packet_oracle_beats_always_sonnet_lambda_0.5": oracle_router > always_sonnet,
    }


def _validate_counts(counts: dict[str, int], expected: dict[str, int]) -> None:
    mismatches = {
        key: {"expected": value, "observed": counts.get(key)}
        for key, value in expected.items()
        if counts.get(key) != value
    }
    if mismatches:
        raise ValueError(f"Phase 0A count check failed: {mismatches}")


def _validate_cues(cue_conditions: list[str]) -> None:
    if cue_conditions != sorted(MAIN_NON_LEAKAGE_CUES):
        raise ValueError(f"Phase 0A cue check failed: {cue_conditions}")
    if "raw_assay_stats_shown" in cue_conditions:
        raise ValueError("Phase 0A main pilot must exclude raw_assay_stats_shown")


def _validate_phase0b_cues(cue_conditions: list[str], cue_counts: dict[str, int]) -> None:
    if cue_conditions != sorted(MAIN_NON_LEAKAGE_CUES):
        raise ValueError(f"Phase 0B cue check failed: {cue_conditions}")
    if "raw_assay_stats_shown" in cue_conditions:
        raise ValueError("Phase 0B main run must exclude raw_assay_stats_shown")
    expected_counts = {cue: 107 for cue in MAIN_NON_LEAKAGE_CUES}
    if cue_counts != expected_counts:
        raise ValueError(f"Phase 0B cue balance check failed: {cue_counts}")


def _validate_panel_balance(panel_balance: dict[str, int]) -> None:
    expected = {"high": 4, "low": 4, "mid": 4}
    if panel_balance != expected:
        raise ValueError(f"Phase 0A panel balance check failed: {panel_balance}")


def _validate_phase0b_integrity(episode_integrity: dict[str, Any]) -> None:
    if episode_integrity["parse_errors"] != 0:
        raise ValueError(f"Phase 0B parse errors found: {episode_integrity['parse_errors']}")
    if episode_integrity["provider_errors"] != 0:
        raise ValueError(f"Phase 0B provider errors found: {episode_integrity['provider_errors']}")
    if episode_integrity["episodes_missing_actions"] != 0:
        raise ValueError(
            f"Phase 0B episodes missing actions: {episode_integrity['episodes_missing_actions']}"
        )


def _validate_sanity(sanity_checks: dict[str, bool]) -> None:
    failed = [key for key, value in sanity_checks.items() if not value]
    if failed:
        raise ValueError(f"Phase 0A sanity checks failed: {failed}")


def _episode_integrity(packets: list[dict], episodes: list[dict]) -> dict[str, Any]:
    packet_map = {packet["packet_id"]: packet for packet in packets}
    cue_counts = Counter()
    action_counts = Counter()
    parse_errors = 0
    provider_errors = 0
    missing_actions = 0
    total_expected_genes = 0
    total_action_keys = 0
    mismatched_episodes = []

    for episode in episodes:
        cue_counts[str(episode.get("cue_condition", "unknown"))] += 1
        if "parse_error" in episode:
            parse_errors += 1
        if "provider_error" in episode:
            provider_errors += 1

        packet = packet_map[episode["packet_id"]]
        expected = {
            row["gene_display"]
            for row in packet.get("evidence_packet", {}).get("genes", [])
        }
        observed = set((episode.get("actions") or {}).keys())
        total_expected_genes += len(expected)
        total_action_keys += len(observed)
        if not observed:
            missing_actions += 1

        for value in (episode.get("actions") or {}).values():
            if isinstance(value, dict):
                action_counts[str(value.get("action", "missing"))] += 1
            else:
                action_counts[str(value)] += 1

        missing_expected = sorted(expected - observed)
        extra_action_keys = sorted(observed - expected)
        if missing_expected or extra_action_keys:
            mismatched_episodes.append({
                "packet_id": episode["packet_id"],
                "cue_condition": episode.get("cue_condition"),
                "missing_expected_genes": missing_expected,
                "extra_action_genes": extra_action_keys,
            })

    return {
        "episodes": len(episodes),
        "cue_counts": dict(sorted(cue_counts.items())),
        "total_expected_genes": total_expected_genes,
        "total_action_keys": total_action_keys,
        "action_counts": dict(sorted(action_counts.items())),
        "parse_errors": parse_errors,
        "provider_errors": provider_errors,
        "episodes_missing_actions": missing_actions,
        "gene_key_mismatch_episode_count": len(mismatched_episodes),
        "gene_key_mismatch_missing_expected_gene_count": sum(
            len(row["missing_expected_genes"]) for row in mismatched_episodes
        ),
        "gene_key_mismatch_extra_action_gene_count": sum(
            len(row["extra_action_genes"]) for row in mismatched_episodes
        ),
        "gene_key_mismatch_examples": mismatched_episodes[:5],
    }


def _phase0b_sanity_checks(summary: dict[str, Any]) -> dict[str, bool]:
    baselines_05 = summary["baselines"]["full"]["0.5"]
    deltas = summary["baseline_comparison"]["delta_net_reward_per_gene"]
    paired_05 = summary["llm_full_run"]["sonnet_4_6"]["paired_key_cues"]["0.5"]
    cue_rank = summary["cue_level_highlights"]["cue_ranked_by_net_reward_per_gene"]
    integrity = summary["episode_integrity"]
    return {
        "oracle_beats_random_full_lambda_0.5": (
            baselines_05["oracle_verify"]["net_reward_per_gene"]
            > baselines_05["random_verify_at_budget"]["net_reward_per_gene"]
        ),
        "additive_subset_preserves_additive_baseline_signal_lambda_0.5": (
            summary["baselines"]["additive_coverage"]["0.5"]["always_additive"]["net_reward_per_gene"]
            > summary["baselines"]["additive_coverage"]["0.5"]["trust_all_sfm"]["net_reward_per_gene"]
        ),
        "sonnet_full_near_ties_trust_all_lambda_0.5": abs(deltas["0.5"]["trust_all_sfm"]) < 0.01,
        "sonnet_full_loses_to_trust_all_lambda_0.8": deltas["0.8"]["trust_all_sfm"] < 0.0,
        "additive_disagreement_improves_net_vs_no_cue_lambda_0.5": (
            paired_05["additive_disagreement_shown"]["delta_net"] > 0.0
        ),
        "misleading_reliability_card_hurts_net_vs_no_cue_lambda_0.5": (
            paired_05["misleading_reliability_card"]["delta_net"] < 0.0
        ),
        "confidence_shown_is_top_net_cue_lambda_0.5": cue_rank[0]["cue_condition"] == "confidence_shown",
        "phase0b_outputs_have_no_parse_or_provider_errors": (
            integrity["parse_errors"] == 0 and integrity["provider_errors"] == 0
        ),
    }


def _artifact_metadata(path: Path) -> dict[str, Any]:
    meta = {
        "path": _display_path(path),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }
    if path.suffix == ".jsonl":
        meta["records"] = _jsonl_record_count(path)
    elif path.suffix == ".json":
        with open(path) as handle:
            payload = json.load(handle)
        meta["json_type"] = type(payload).__name__
        if isinstance(payload, dict):
            meta["top_level_keys"] = sorted(payload.keys())
    return meta


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _jsonl_record_count(path: Path) -> int:
    with open(path) as handle:
        return sum(1 for line in handle if line.strip())


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip()


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(resolved)


def _normalize_json_floats(value: Any) -> Any:
    if isinstance(value, float):
        rounded = round(value, FREEZE_FLOAT_DIGITS)
        return 0.0 if rounded == 0 else rounded
    if isinstance(value, list):
        return [_normalize_json_floats(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _normalize_json_floats(item)
            for key, item in value.items()
        }
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    os.makedirs(path.parent, exist_ok=True)
    with open(path, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
