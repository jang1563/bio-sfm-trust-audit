"""Reward and policy scoring for trust-cue attribution panels."""

from __future__ import annotations

from collections import defaultdict
from statistics import mean

try:
    from .actions import normalize_action
except ImportError:  # direct script/test execution from this directory
    from actions import normalize_action

LAMBDAS = (0.2, 0.5, 0.8)


def action_correct(edge: dict, action: str) -> bool:
    action = normalize_action(action)
    if action == "trust_sfm":
        return bool(edge["fm"]["correct"])
    if action == "verify_assay":
        return True
    if action == "default_baseline":
        return bool(edge["baseline_signal"]["correct"])
    if action == "defer":
        return False
    raise AssertionError(action)


def action_assay_cost(action: str) -> int:
    return 1 if normalize_action(action) == "verify_assay" else 0


def action_net_reward(edge: dict, action: str, lam: float = 0.5, defer_penalty: float = 0.0) -> float:
    action = normalize_action(action)
    return (
        int(action_correct(edge, action))
        - lam * action_assay_cost(action)
        - (defer_penalty if action == "defer" else 0.0)
    )


def score_actions(panel: dict, actions: dict[str, str], lam: float = 0.5, defer_penalty: float = 0.0) -> dict:
    correct = 0
    assays = 0
    wrong_genes = {e["gene"] for e in panel["edges"] if not e["fm"]["correct"]}
    verified = set()
    baseline_used = 0
    default_observed_additive = 0
    default_no_change = 0
    default_other = 0
    default_errors = 0
    deferred = 0
    trust_errors = 0
    for edge in panel["edges"]:
        action = normalize_action(actions.get(edge["gene"], "defer"))
        correct += int(action_correct(edge, action))
        assays += action_assay_cost(action)
        if action == "verify_assay":
            verified.add(edge["gene"])
        if action == "default_baseline":
            baseline_used += 1
            source = edge["baseline_signal"].get("source", "unknown")
            if source == "observed_additive":
                default_observed_additive += 1
            elif source == "no_change":
                default_no_change += 1
            else:
                default_other += 1
            if not edge["baseline_signal"]["correct"]:
                default_errors += 1
        if action == "defer":
            deferred += 1
        if action == "trust_sfm" and not edge["fm"]["correct"]:
            trust_errors += 1
    n = len(panel["edges"])
    verify_wrong = len(verified & wrong_genes)
    net = correct - lam * assays - defer_penalty * deferred
    covered = n - deferred
    verify_precision = len(verified & wrong_genes) / len(verified) if verified else 0.0
    verify_recall = len(verified & wrong_genes) / len(wrong_genes) if wrong_genes else 0.0
    return {
        "panel_id": panel["panel_id"],
        "n": n,
        "correct_count": correct,
        "assay_count": assays,
        "wrong_sfm_count": len(wrong_genes),
        "verify_count": len(verified),
        "verify_wrong_count": verify_wrong,
        "trust_error_count": trust_errors,
        "default_baseline_count": baseline_used,
        "default_observed_additive_count": default_observed_additive,
        "default_no_change_count": default_no_change,
        "default_other_count": default_other,
        "default_error_count": default_errors,
        "defer_count": deferred,
        "covered_count": covered,
        "accuracy": correct / n if n else 0.0,
        "assays_per_gene": assays / n if n else 0.0,
        "net_reward": net,
        "net_reward_per_gene": net / n if n else 0.0,
        "sfm_wrong_rate": len(wrong_genes) / n if n else 0.0,
        "trust_error_rate": trust_errors / n if n else 0.0,
        "verify_precision": verify_precision,
        "verify_recall": verify_recall,
        "default_baseline_rate": baseline_used / n if n else 0.0,
        "default_observed_additive_rate": default_observed_additive / n if n else 0.0,
        "default_no_change_rate": default_no_change / n if n else 0.0,
        "default_error_rate": default_errors / n if n else 0.0,
        "defer_rate": deferred / n if n else 0.0,
        "coverage_rate": covered / n if n else 0.0,
    }


def score_episode(panel: dict, episode: dict, lam: float = 0.5, defer_penalty: float = 0.0) -> dict:
    action_map = {
        gene: rec["action"] if isinstance(rec, dict) else rec
        for gene, rec in episode.get("actions", {}).items()
    }
    out = score_actions(panel, action_map, lam, defer_penalty=defer_penalty)
    out.update({
        "packet_id": episode.get("packet_id"),
        "model": episode.get("model", "unknown"),
        "cue_condition": episode.get("cue_condition"),
    })
    return out


def score_policy(panels: list[dict], policy, lam: float = 0.5, defer_penalty: float = 0.0) -> dict:
    rows = [score_actions(panel, policy(panel), lam, defer_penalty=defer_penalty) for panel in panels]
    return summarize_scores(rows)


def summarize_scores(rows: list[dict]) -> dict:
    if not rows:
        return {}
    macro_keys = [
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
    count_keys = [
        "n",
        "correct_count",
        "assay_count",
        "wrong_sfm_count",
        "verify_count",
        "verify_wrong_count",
        "trust_error_count",
        "default_baseline_count",
        "default_observed_additive_count",
        "default_no_change_count",
        "default_other_count",
        "default_error_count",
        "defer_count",
        "covered_count",
    ]
    totals = {key: sum(r.get(key, 0) for r in rows) for key in count_keys}
    total_net = sum(r["net_reward"] for r in rows)
    n = totals["n"]
    verify_count = totals["verify_count"]
    wrong_sfm_count = totals["wrong_sfm_count"]
    out = {
        "n_panels": len(rows),
        "n_genes": n,
        "total_correct": totals["correct_count"],
        "total_assays": totals["assay_count"],
        "total_net_reward": total_net,
        "accuracy": totals["correct_count"] / n if n else 0.0,
        "assays_per_gene": totals["assay_count"] / n if n else 0.0,
        "net_reward": total_net,
        "net_reward_per_gene": total_net / n if n else 0.0,
        "sfm_wrong_rate": totals["wrong_sfm_count"] / n if n else 0.0,
        "trust_error_rate": totals["trust_error_count"] / n if n else 0.0,
        "verify_precision": totals["verify_wrong_count"] / verify_count if verify_count else 0.0,
        "verify_recall": totals["verify_wrong_count"] / wrong_sfm_count if wrong_sfm_count else 0.0,
        "default_baseline_rate": totals["default_baseline_count"] / n if n else 0.0,
        "default_observed_additive_rate": totals["default_observed_additive_count"] / n if n else 0.0,
        "default_no_change_rate": totals["default_no_change_count"] / n if n else 0.0,
        "default_error_rate": totals["default_error_count"] / n if n else 0.0,
        "defer_rate": totals["defer_count"] / n if n else 0.0,
        "coverage_rate": totals["covered_count"] / n if n else 0.0,
    }
    out.update({key: value for key, value in totals.items() if key != "n"})
    out.update({
        f"macro_panel_{key}": mean(r[key] for r in rows)
        for key in macro_keys
    })
    out["macro_panel_net_reward"] = mean(r["net_reward"] for r in rows)
    return out


def cue_attribution_summary(scored_rows: list[dict]) -> dict:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in scored_rows:
        groups[str(row.get("cue_condition", "unknown"))].append(row)
    return {cue: summarize_scores(rows) for cue, rows in sorted(groups.items())}
