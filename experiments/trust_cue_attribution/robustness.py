"""Panel-cluster robustness summaries for Phase 0 trust-cue results."""

from __future__ import annotations

import json
import os
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from . import baselines
    from .analysis import (
        PRIMARY_DIMENSION_BY_CUE,
        _available_dimensions,
        _cue_dimensions_from_text,
        _rationale_text,
        explanation_faithfulness_gap,
        gene_level_rows,
        paired_cue_effects,
    )
    from .episodes import score_episode_records
    from .freeze import MAIN_NON_LEAKAGE_CUES, _normalize_json_floats
    from .io_utils import read_jsonl
    from .scoring import LAMBDAS, score_actions, summarize_scores
except ImportError:  # direct script/test execution from this directory
    import baselines
    from analysis import (
        PRIMARY_DIMENSION_BY_CUE,
        _available_dimensions,
        _cue_dimensions_from_text,
        _rationale_text,
        explanation_faithfulness_gap,
        gene_level_rows,
        paired_cue_effects,
    )
    from episodes import score_episode_records
    from freeze import MAIN_NON_LEAKAGE_CUES, _normalize_json_floats
    from io_utils import read_jsonl
    from scoring import LAMBDAS, score_actions, summarize_scores


BOOTSTRAP_METRICS = [
    "action_changed_rate",
    "delta_correct",
    "delta_assay",
    "delta_net",
    "delta_trust_error",
    "delta_verify_wrong",
]

POLICIES = {
    "trust_all_sfm": baselines.trust_all_sfm,
    "verify_all": baselines.verify_all,
    "random_verify_at_budget": lambda panel: baselines.random_verify_at_budget(panel, seed=0),
    "oracle_verify": baselines.oracle_verify,
    "always_additive": baselines.always_additive,
    "signal_gated_verify": baselines.signal_gated_verify,
}


def build_phase0b_robustness(
    input_dir: str,
    out: str | None = None,
    *,
    n_boot: int = 1000,
    seed: int = 13,
    lam: float = 0.5,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Build a compact Phase 0B robustness summary from ignored HPC outputs."""
    input_path = Path(input_dir)
    panels = read_jsonl(str(input_path / "panels_full.jsonl"))
    packets = read_jsonl(str(input_path / "cue_packets_full.jsonl"))
    episodes = read_jsonl(str(input_path / "llm_claude-sonnet-4-6_phase0b_main_episodes.jsonl"))

    rows = gene_level_rows(panels, packets, episodes, lam=lam)
    point_paired = paired_cue_effects(rows, baseline_cue="no_cue")
    point_score = score_episode_records(panels, packets, episodes, lam=lam)["summary"]
    point_baselines = _baseline_score_rows(panels, lam=lam)
    point_baseline_deltas = {
        policy: point_score["net_reward_per_gene"] - summarize_scores(policy_rows)["net_reward_per_gene"]
        for policy, policy_rows in point_baselines.items()
    }
    point_faithfulness = explanation_faithfulness_gap(episodes, rows, baseline_cue="no_cue")

    rng = random.Random(seed)
    panel_ids = sorted({panel["panel_id"] for panel in panels})
    pair_rows_by_panel = _group_by_panel(_paired_delta_rows(rows, baseline_cue="no_cue"))
    faithfulness_rows_by_panel = _group_by_panel(_faithfulness_target_rows(packets, episodes))
    score_rows_by_panel = _group_by_panel(score_episode_records(panels, packets, episodes, lam=lam)["rows"])
    baseline_rows_by_policy_panel = {
        policy: _group_by_panel(policy_rows)
        for policy, policy_rows in point_baselines.items()
    }

    paired_samples: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    baseline_delta_samples: dict[str, list[float]] = defaultdict(list)
    faithfulness_samples: dict[str, list[float]] = defaultdict(list)

    for _ in range(n_boot):
        sampled_panels = [rng.choice(panel_ids) for _ in panel_ids]
        sampled_pair_rows = _expand_by_panel(pair_rows_by_panel, sampled_panels)
        sampled_faithfulness_rows = _expand_by_panel(faithfulness_rows_by_panel, sampled_panels)
        sampled_score_rows = _expand_by_panel(score_rows_by_panel, sampled_panels)
        sampled_score = summarize_scores(sampled_score_rows)

        sampled_paired = _aggregate_pair_rows(sampled_pair_rows)
        for cue, effect in sampled_paired.items():
            for metric in BOOTSTRAP_METRICS:
                if metric in effect:
                    paired_samples[cue][metric].append(effect[metric])

        for policy, by_panel in baseline_rows_by_policy_panel.items():
            policy_score = summarize_scores(_expand_by_panel(by_panel, sampled_panels))
            baseline_delta_samples[policy].append(
                sampled_score["net_reward_per_gene"] - policy_score["net_reward_per_gene"]
            )

        for key, value in _aggregate_target_rows(sampled_faithfulness_rows).items():
            faithfulness_samples[key].append(value)

    summary = {
        "phase": "phase0c",
        "source": "phase0b_full_nonleakage_sonnet",
        "status": "panel_cluster_bootstrap_robustness_summary",
        "bootstrap": {
            "unit": "biological_panel",
            "n_boot": n_boot,
            "seed": seed,
            "alpha": alpha,
            "lambda": lam,
            "panel_count": len(panel_ids),
        },
        "paired_cue_effects": _paired_ci_summary(point_paired, paired_samples, alpha),
        "baseline_delta_net_reward_per_gene": {
            policy: _estimate_ci(point_baseline_deltas[policy], values, alpha)
            for policy, values in sorted(baseline_delta_samples.items())
        },
        "explanation_faithfulness": {
            key: _estimate_ci(_faithfulness_targets(point_faithfulness).get(key, 0.0), values, alpha)
            for key, values in sorted(faithfulness_samples.items())
        },
        "claim_read": {
            "robustness_target": (
                "Check whether Phase 0B cue effects survive panel-level resampling, "
                "not whether the result generalizes to true SFMs."
            ),
            "primary_use": "support Phase 0B method-validation claims with uncertainty intervals",
        },
    }
    summary = _normalize_json_floats(summary)
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
            handle.write("\n")
    return summary


def _baseline_score_rows(panels: list[dict], lam: float) -> dict[str, list[dict]]:
    out = {}
    for name, policy in POLICIES.items():
        out[name] = [
            score_actions(panel, policy(panel), lam)
            for panel in panels
        ]
    return out


def _group_by_panel(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        out[str(row["panel_id"])].append(row)
    return dict(out)


def _paired_delta_rows(rows: list[dict], baseline_cue: str = "no_cue") -> list[dict]:
    row_by_key = {
        (row["panel_id"], row["gene"], row["cue_condition"]): row
        for row in rows
    }
    out = []
    for row in rows:
        cue = row["cue_condition"]
        if cue == baseline_cue:
            continue
        base = row_by_key.get((row["panel_id"], row["gene"], baseline_cue))
        if not base:
            continue
        out.append({
            "panel_id": row["panel_id"],
            "cue_condition": cue,
            "action_changed_rate": int(base["action"] != row["action"]),
            "delta_correct": row["correct"] - base["correct"],
            "delta_assay": row["assay"] - base["assay"],
            "delta_net": row["net"] - base["net"],
            "delta_trust_error": _trust_error(row) - _trust_error(base),
            "delta_verify_wrong": _verify_wrong(row) - _verify_wrong(base),
        })
    return out


def _aggregate_pair_rows(rows: list[dict]) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row["cue_condition"])].append(row)
    out = {}
    for cue, cue_rows in grouped.items():
        n = len(cue_rows)
        out[cue] = {"n_pairs": n}
        if not n:
            continue
        for metric in BOOTSTRAP_METRICS:
            out[cue][metric] = sum(row[metric] for row in cue_rows) / n
    return out


def _trust_error(row: dict) -> int:
    return int(row["action"] == "trust_sfm" and row["sfm_wrong"])


def _verify_wrong(row: dict) -> int:
    return int(row["action"] == "verify_assay" and row["sfm_wrong"])


def _faithfulness_target_rows(packets: list[dict], episodes: list[dict]) -> list[dict]:
    packet_to_panel = {packet["packet_id"]: packet["panel_id"] for packet in packets}
    rows = []
    for episode in episodes:
        cue = str(episode.get("cue_condition", "unknown"))
        available = _available_dimensions(cue)
        self_dims = set()
        for reported in episode.get("self_reported_cues", []):
            self_dims.update(_cue_dimensions_from_text(str(reported)))
        unavailable_self = self_dims - available

        rationale_dims = set()
        for value in (episode.get("actions") or {}).values():
            rationale_dims.update(_cue_dimensions_from_text(_rationale_text(value)))

        targets = {}
        for dimension in ("baseline", "confidence", "model_identity"):
            targets[f"{cue}.unavailable_self_reported.{dimension}"] = int(dimension in unavailable_self)

        primary_dimension = PRIMARY_DIMENSION_BY_CUE.get(cue)
        if primary_dimension:
            targets[f"{cue}.primary_explanation_rate"] = int(
                primary_dimension in self_dims or primary_dimension in rationale_dims
            )

        for key, value in targets.items():
            rows.append({
                "panel_id": packet_to_panel[episode["packet_id"]],
                "target": key,
                "value": value,
            })
    return rows


def _aggregate_target_rows(rows: list[dict]) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row["target"])].append(float(row["value"]))
    return {
        key: sum(values) / len(values)
        for key, values in grouped.items()
        if values
    }


def _expand_by_panel(by_panel: dict[str, list[dict]], sampled_panels: list[str]) -> list[dict]:
    rows = []
    for panel_id in sampled_panels:
        rows.extend(by_panel.get(panel_id, []))
    return rows


def _paired_ci_summary(
    point_paired: dict[str, dict[str, Any]],
    paired_samples: dict[str, dict[str, list[float]]],
    alpha: float,
) -> dict[str, dict[str, Any]]:
    out = {}
    for cue in sorted(cue for cue in point_paired if cue != "no_cue"):
        out[cue] = {"n_pairs": point_paired[cue].get("n_pairs", 0)}
        for metric in BOOTSTRAP_METRICS:
            if metric in point_paired[cue]:
                out[cue][metric] = _estimate_ci(
                    point_paired[cue][metric],
                    paired_samples[cue][metric],
                    alpha,
                )
    return out


def _faithfulness_targets(faithfulness: dict[str, Any]) -> dict[str, float]:
    targets = {}
    cue_summaries = faithfulness.get("cue_summaries", {})
    for cue in ("no_cue", "anonymized_genes", "model_name_shown", "confidence_shown", "misleading_reliability_card"):
        row = cue_summaries.get(cue, {})
        unavailable_self = row.get("unavailable_self_reported_episode_rates", {})
        for dimension in ("baseline", "confidence", "model_identity"):
            if dimension in unavailable_self:
                targets[f"{cue}.unavailable_self_reported.{dimension}"] = unavailable_self[dimension]
        primary = row.get("primary_explanation_rate")
        if primary is not None:
            targets[f"{cue}.primary_explanation_rate"] = primary
    return targets


def _estimate_ci(estimate: float, values: list[float], alpha: float) -> dict[str, float]:
    return {
        "estimate": estimate,
        "ci_low": _percentile(values, alpha / 2),
        "ci_high": _percentile(values, 1 - alpha / 2),
    }


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction
