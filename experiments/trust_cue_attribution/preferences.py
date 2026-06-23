"""Preference-pair utilities for trajectory datasets."""

from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from statistics import mean


def make_preference_pairs(
    trajectories: list[dict],
    min_reward_delta: float = 0.0,
    include_ties: bool = False,
) -> list[dict]:
    """Create chosen/rejected pairs from trajectories for the same packet."""
    by_packet: dict[str, list[dict]] = defaultdict(list)
    for trajectory in trajectories:
        by_packet[str(trajectory["packet_id"])].append(trajectory)

    pairs = []
    for packet_id, rows in sorted(by_packet.items()):
        if len(rows) < 2:
            continue
        rows = sorted(rows, key=lambda row: str(row.get("trajectory_id", "")))
        for left, right in combinations(rows, 2):
            left_reward = float(left.get("reward", 0.0))
            right_reward = float(right.get("reward", 0.0))
            delta = left_reward - right_reward
            abs_delta = abs(delta)
            if abs_delta < min_reward_delta:
                continue
            if delta == 0.0 and not include_ties:
                continue
            if delta >= 0.0:
                chosen, rejected = left, right
                reward_delta = delta
            else:
                chosen, rejected = right, left
                reward_delta = -delta
            pair_index = len(pairs)
            pairs.append({
                "pair_id": f"{packet_id}::{chosen.get('model', 'unknown')}>>{rejected.get('model', 'unknown')}::{pair_index}",
                "packet_id": packet_id,
                "panel_id": chosen.get("panel_id"),
                "cue_condition": chosen.get("cue_condition"),
                "preference_source": "trajectory_reward",
                "reward_delta": reward_delta,
                "absolute_reward_delta": abs_delta,
                "is_tie": delta == 0.0,
                "same_observation": chosen.get("observation") == rejected.get("observation"),
                "reward_config": chosen.get("reward_config", {}),
                "observation": chosen.get("observation", {}),
                "chosen": _compact_trajectory(chosen),
                "rejected": _compact_trajectory(rejected),
            })
    return pairs


def summarize_preference_pairs(pairs: list[dict]) -> dict:
    """Summarize preference-pair counts and reward margins."""
    chosen_models = Counter(pair["chosen"].get("model", "unknown") for pair in pairs)
    rejected_models = Counter(pair["rejected"].get("model", "unknown") for pair in pairs)
    by_cue: dict[str, list[dict]] = defaultdict(list)
    for pair in pairs:
        by_cue[str(pair.get("cue_condition", "unknown"))].append(pair)

    def cue_summary(rows: list[dict]) -> dict:
        deltas = [float(row["reward_delta"]) for row in rows]
        return {
            "n_pairs": len(rows),
            "mean_reward_delta": mean(deltas) if deltas else 0.0,
            "max_reward_delta": max(deltas) if deltas else 0.0,
            "chosen_models": dict(sorted(Counter(row["chosen"].get("model", "unknown") for row in rows).items())),
            "rejected_models": dict(sorted(Counter(row["rejected"].get("model", "unknown") for row in rows).items())),
        }

    deltas = [float(pair["reward_delta"]) for pair in pairs]
    return {
        "n_pairs": len(pairs),
        "n_ties": sum(1 for pair in pairs if pair.get("is_tie")),
        "mean_reward_delta": mean(deltas) if deltas else 0.0,
        "max_reward_delta": max(deltas) if deltas else 0.0,
        "chosen_models": dict(sorted(chosen_models.items())),
        "rejected_models": dict(sorted(rejected_models.items())),
        "by_cue_condition": {cue: cue_summary(rows) for cue, rows in sorted(by_cue.items())},
    }


def _compact_trajectory(trajectory: dict) -> dict:
    return {
        "trajectory_id": trajectory.get("trajectory_id"),
        "model": trajectory.get("model"),
        "actions": trajectory.get("actions", {}),
        "reward": trajectory.get("reward"),
        "reward_per_gene": trajectory.get("reward_per_gene"),
        "score": trajectory.get("score", {}),
        "metadata": trajectory.get("metadata", {}),
    }
