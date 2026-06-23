"""Thin trust-routing environment over Phase 0 cue packets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from collections import defaultdict
from typing import Any

try:
    from .episodes import make_policy_episode_records, score_episode_record
    from .scoring import summarize_scores
except ImportError:  # direct script/test execution from this directory
    from episodes import make_policy_episode_records, score_episode_record
    from scoring import summarize_scores


@dataclass
class ToolCallTrace:
    """One non-ground-truth tool call made during a trust-routing trajectory."""

    step: int
    tool_name: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ScientificTrustEnv:
    """One-panel environment for trust/verify/default/defer decisions.

    The environment starts from an already-built cue packet. Its tools expose
    deployable evidence only; held-out truth and correctness labels remain hidden
    and are used only by the scorer after an action is submitted.
    """

    def __init__(
        self,
        panel: dict,
        packet: dict,
        lam: float = 0.5,
        defer_penalty: float = 0.0,
        tool_call_cost: float = 0.0,
    ) -> None:
        if panel["panel_id"] != packet["panel_id"]:
            raise ValueError(f"panel/packet mismatch: {panel['panel_id']} != {packet['panel_id']}")
        self.panel = panel
        self.packet = packet
        self.lam = lam
        self.defer_penalty = defer_penalty
        self.tool_call_cost = tool_call_cost
        self.tool_calls: list[ToolCallTrace] = []

    def observation(self) -> dict:
        """Return the model-visible starting observation."""
        return {
            "packet_id": self.packet["packet_id"],
            "panel_id": self.packet["panel_id"],
            "cue_condition": self.packet["cue_condition"],
            "available_actions": list(self.packet.get("available_actions", [])),
            "evidence_packet": self.packet["evidence_packet"],
        }

    def call_tool(self, tool_name: str, gene: str | None = None) -> dict:
        """Call a non-ground-truth evidence tool and log the result."""
        edge = self._edge_for_gene(gene) if gene else None
        if tool_name == "get_sfm_prediction":
            outputs = self._sfm_prediction(edge)
        elif tool_name == "get_baseline_prediction":
            outputs = self._baseline_prediction(edge)
        elif tool_name == "get_reliability_signal":
            outputs = self._reliability_signal(edge)
        elif tool_name == "estimate_assay_cost":
            outputs = {"verify_assay_cost": 1.0, "lambda": self.lam}
        elif tool_name == "get_available_actions":
            outputs = {"available_actions": list(self.packet.get("available_actions", []))}
        elif tool_name == "get_current_evidence_packet":
            outputs = {"evidence_packet": self.packet["evidence_packet"]}
        else:
            raise ValueError(f"unknown tool {tool_name!r}")

        trace = ToolCallTrace(
            step=len(self.tool_calls),
            tool_name=tool_name,
            inputs={"gene": gene} if gene else {},
            outputs=outputs,
        )
        self.tool_calls.append(trace)
        return outputs

    def decide(self, actions: dict[str, Any], model: str = "unknown", metadata: dict[str, Any] | None = None) -> dict:
        """Submit a final action map and return a trajectory record."""
        episode = {
            "packet_id": self.packet["packet_id"],
            "cue_condition": self.packet["cue_condition"],
            "model": model,
            "actions": actions,
        }
        score = score_episode_record(
            self.panel,
            self.packet,
            episode,
            lam=self.lam,
            defer_penalty=self.defer_penalty,
        )
        tool_cost = self.tool_call_cost * len(self.tool_calls)
        trajectory_reward = score["net_reward"] - tool_cost
        return {
            "trajectory_id": f"{self.packet['packet_id']}::{model}",
            "packet_id": self.packet["packet_id"],
            "panel_id": self.panel["panel_id"],
            "cue_condition": self.packet["cue_condition"],
            "model": model,
            "reward_config": {
                "lambda": self.lam,
                "defer_penalty": self.defer_penalty,
                "tool_call_cost": self.tool_call_cost,
            },
            "observation": self.observation(),
            "tool_calls": [call.to_dict() for call in self.tool_calls],
            "actions": actions,
            "score": score,
            "reward": trajectory_reward,
            "reward_per_gene": trajectory_reward / score["n"] if score["n"] else 0.0,
            "metadata": metadata or {},
        }

    def _edge_for_gene(self, gene: str | None) -> dict:
        if not gene:
            raise ValueError("gene is required for this tool")
        display_to_gene = {
            row["gene_display"]: row["gene"]
            for row in self.packet.get("scoring_key", [])
        }
        true_gene = display_to_gene.get(gene, gene)
        for edge in self.panel["edges"]:
            if edge["gene"] == true_gene:
                return edge
        raise KeyError(f"gene {gene!r} not found in panel {self.panel['panel_id']!r}")

    def _display_for_gene(self, gene: str) -> str:
        gene_to_display = {
            row["gene"]: row["gene_display"]
            for row in self.packet.get("scoring_key", [])
        }
        return gene_to_display.get(gene, gene)

    def _target_edges(self, edge: dict | None) -> list[dict]:
        return [edge] if edge else list(self.panel["edges"])

    def _sfm_prediction(self, edge: dict | None) -> dict:
        return {
            "genes": [
                {
                    "gene_display": self._display_for_gene(item["gene"]),
                    "sfm_call": item["fm"]["call"],
                    "sfm_log2fc": item["fm"]["log2fc"],
                    "model_name": item["fm"]["model_name"],
                }
                for item in self._target_edges(edge)
            ]
        }

    def _baseline_prediction(self, edge: dict | None) -> dict:
        return {
            "genes": [
                {
                    "gene_display": self._display_for_gene(item["gene"]),
                    "baseline_source": item["baseline_signal"]["source"],
                    "baseline_call": item["baseline_signal"]["call"],
                    "baseline_log2fc": item["baseline_signal"]["log2fc"],
                    "abs_fm_minus_baseline": item["baseline_signal"]["abs_fm_minus_baseline"],
                    "call_disagreement": item["baseline_signal"]["call_disagreement"],
                }
                for item in self._target_edges(edge)
            ]
        }

    def _reliability_signal(self, edge: dict | None) -> dict:
        return {
            "genes": [
                {
                    "gene_display": self._display_for_gene(item["gene"]),
                    "source": item["reliability_signal"]["source"],
                    "score": item["reliability_signal"]["score"],
                    "label": item["reliability_signal"]["label"],
                }
                for item in self._target_edges(edge)
            ]
        }


def make_policy_trajectories(
    panels: list[dict],
    packets: list[dict],
    policy_name: str,
    lam: float = 0.5,
    defer_penalty: float = 0.0,
    tool_call_cost: float = 0.0,
) -> list[dict]:
    """Materialize deterministic policy decisions as environment trajectories."""
    panel_map = {panel["panel_id"]: panel for panel in panels}
    episodes = make_policy_episode_records(panels, packets, policy_name)
    trajectories = []
    if len(packets) != len(episodes):
        raise ValueError(f"packet/episode count mismatch: {len(packets)} != {len(episodes)}")
    for packet, episode in zip(packets, episodes):
        env = ScientificTrustEnv(
            panel_map[packet["panel_id"]],
            packet,
            lam=lam,
            defer_penalty=defer_penalty,
            tool_call_cost=tool_call_cost,
        )
        trajectories.append(env.decide(
            episode["actions"],
            model=episode["model"],
            metadata={"policy_name": policy_name, "source": "deterministic_policy"},
        ))
    return trajectories


def make_episode_trajectories(
    panels: list[dict],
    packets: list[dict],
    episodes: list[dict],
    lam: float = 0.5,
    defer_penalty: float = 0.0,
    tool_call_cost: float = 0.0,
    include_raw_output: bool = False,
) -> list[dict]:
    """Wrap completed LLM episodes as environment trajectories."""
    panel_map = {panel["panel_id"]: panel for panel in panels}
    packet_map = {packet["packet_id"]: packet for packet in packets}
    trajectories = []
    for idx, episode in enumerate(episodes):
        packet_id = episode["packet_id"]
        packet = packet_map[packet_id]
        env = ScientificTrustEnv(
            panel_map[packet["panel_id"]],
            packet,
            lam=lam,
            defer_penalty=defer_penalty,
            tool_call_cost=tool_call_cost,
        )
        metadata = _episode_metadata(episode, include_raw_output=include_raw_output)
        metadata["source"] = "llm_episode"
        metadata["episode_index"] = idx
        trajectory = env.decide(
            episode.get("actions", {}),
            model=episode.get("model", "unknown"),
            metadata=metadata,
        )
        trajectory["trajectory_id"] = f"{packet_id}::{trajectory['model']}::episode_{idx}"
        trajectories.append(trajectory)
    return trajectories


def _episode_metadata(episode: dict, include_raw_output: bool = False) -> dict:
    keep = (
        "provider",
        "self_reported_cues",
        "parse_error",
        "provider_error",
        "usage",
        "request_id",
        "stop_reason",
    )
    metadata = {key: episode[key] for key in keep if key in episode}
    if include_raw_output and "raw_output" in episode:
        metadata["raw_output"] = episode["raw_output"]
    return metadata


def summarize_trajectories(trajectories: list[dict]) -> dict:
    """Summarize trajectory-level reward and embedded score rows."""
    def summarize_group(rows: list[dict]) -> dict:
        scores = [row["score"] for row in rows]
        score_summary = summarize_scores(scores)
        n_genes = score_summary.get("n_genes", 0)
        trajectory_reward = sum(float(row.get("reward", 0.0)) for row in rows)
        tool_call_count = sum(len(row.get("tool_calls", [])) for row in rows)
        return {
            **score_summary,
            "n_trajectories": len(rows),
            "trajectory_reward": trajectory_reward,
            "trajectory_reward_per_gene": trajectory_reward / n_genes if n_genes else 0.0,
            "tool_call_count": tool_call_count,
            "tool_calls_per_trajectory": tool_call_count / len(rows) if rows else 0.0,
        }

    by_model: dict[str, list[dict]] = defaultdict(list)
    by_cue: dict[str, list[dict]] = defaultdict(list)
    for row in trajectories:
        by_model[str(row.get("model", "unknown"))].append(row)
        by_cue[str(row.get("cue_condition", "unknown"))].append(row)
    return {
        "overall": summarize_group(trajectories),
        "by_model": {key: summarize_group(rows) for key, rows in sorted(by_model.items())},
        "by_cue_condition": {key: summarize_group(rows) for key, rows in sorted(by_cue.items())},
    }
