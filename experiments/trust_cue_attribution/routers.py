"""Model-router baselines over trajectory datasets."""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any

try:
    from .environment import summarize_trajectories
    from .features import feature_signature, observation_features
except ImportError:  # direct script/test execution from this directory
    from environment import summarize_trajectories
    from features import feature_signature, observation_features


def evaluate_model_router(
    trajectories: list[dict],
    feature_field: str = "cue_condition",
    group_field: str = "panel_id",
) -> dict:
    """Evaluate simple model-selection policies over matched packet trajectories.

    Expected input: multiple trajectories per `packet_id`, usually one per model.
    The learned router is intentionally simple: for each held-out group, choose
    the model with the best mean training reward for the packet's feature value.
    """
    packets = _matched_packets(trajectories)
    models = sorted({row["model"] for rows in packets.values() for row in rows})
    policies: dict[str, dict[str, Any]] = {}

    for model in models:
        selected = [_model_row(rows, model) for rows in packets.values()]
        selected = [row for row in selected if row is not None]
        policies[f"always::{model}"] = _policy_result(f"always::{model}", selected)

    oracle_selected = [max(rows, key=lambda row: float(row.get("reward", 0.0))) for rows in packets.values()]
    policies["oracle_packet"] = _policy_result("oracle_packet", oracle_selected)

    cue_selected, route_records = _leave_group_out_feature_router(
        packets,
        feature_field=feature_field,
        group_field=group_field,
    )
    policies[f"{feature_field}_mean_leave_{group_field}_out"] = {
        **_policy_result(f"{feature_field}_mean_leave_{group_field}_out", cue_selected),
        "route_records": route_records,
    }

    return {
        "n_input_trajectories": len(trajectories),
        "n_matched_packets": len(packets),
        "models": models,
        "feature_field": feature_field,
        "group_field": group_field,
        "policies": policies,
    }


def _matched_packets(trajectories: list[dict]) -> dict[str, list[dict]]:
    by_packet: dict[str, list[dict]] = defaultdict(list)
    for row in trajectories:
        by_packet[str(row["packet_id"])].append(row)
    return {
        packet_id: rows
        for packet_id, rows in sorted(by_packet.items())
        if len({row.get("model") for row in rows}) >= 2
    }


def _model_row(rows: list[dict], model: str) -> dict | None:
    for row in rows:
        if row.get("model") == model:
            return row
    return None


def _policy_result(name: str, selected: list[dict]) -> dict:
    return {
        "policy": name,
        "model_choice_counts": dict(sorted(Counter(row.get("model", "unknown") for row in selected).items())),
        "summary": summarize_trajectories(selected)["overall"],
    }


def _leave_group_out_feature_router(
    packets: dict[str, list[dict]],
    feature_field: str,
    group_field: str,
) -> tuple[list[dict], list[dict]]:
    groups = sorted({str(row.get(group_field, "unknown")) for rows in packets.values() for row in rows})
    selected = []
    route_records = []
    for holdout_group in groups:
        train_rows = [
            row
            for rows in packets.values()
            for row in rows
            if str(row.get(group_field, "unknown")) != holdout_group
        ]
        feature_model_mean = _mean_reward_by_feature_model(train_rows, feature_field)
        model_mean = _mean_reward_by_model(train_rows)
        holdout_packets = {
            packet_id: rows
            for packet_id, rows in packets.items()
            if any(str(row.get(group_field, "unknown")) == holdout_group for row in rows)
        }
        for packet_id, rows in holdout_packets.items():
            chosen, reason = _choose_by_feature_mean(rows, feature_model_mean, model_mean, feature_field)
            selected.append(chosen)
            route_records.append({
                "packet_id": packet_id,
                "panel_id": chosen.get("panel_id"),
                "cue_condition": chosen.get("cue_condition"),
                "heldout_group": holdout_group,
                "chosen_model": chosen.get("model"),
                "chosen_reward": chosen.get("reward"),
                "reason": reason,
                "available_models": sorted(row.get("model", "unknown") for row in rows),
            })
    return selected, route_records


def _mean_reward_by_feature_model(rows: list[dict], feature_field: str) -> dict[tuple[str, str], float]:
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for row in rows:
        buckets[(_feature_value(row, feature_field), str(row.get("model", "unknown")))].append(float(row.get("reward", 0.0)))
    return {key: mean(values) for key, values in buckets.items()}


def _mean_reward_by_model(rows: list[dict]) -> dict[str, float]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        buckets[str(row.get("model", "unknown"))].append(float(row.get("reward", 0.0)))
    return {key: mean(values) for key, values in buckets.items()}


def _choose_by_feature_mean(
    rows: list[dict],
    feature_model_mean: dict[tuple[str, str], float],
    model_mean: dict[str, float],
    feature_field: str,
) -> tuple[dict, str]:
    feature = _feature_value(rows[0], feature_field)
    ranked = []
    for row in rows:
        model = str(row.get("model", "unknown"))
        if (feature, model) in feature_model_mean:
            ranked.append((feature_model_mean[(feature, model)], model, row, "feature_mean"))
        elif model in model_mean:
            ranked.append((model_mean[model], model, row, "model_mean_fallback"))
        else:
            ranked.append((0.0, model, row, "zero_fallback"))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _, _, chosen, reason = ranked[0]
    return chosen, reason


def _feature_value(row: dict, feature_field: str) -> str:
    if feature_field == "feature_signature":
        return feature_signature(observation_features(row.get("observation", {})))
    return str(row.get(feature_field, "unknown"))
