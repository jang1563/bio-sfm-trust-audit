"""LLM episode request/response helpers."""

from __future__ import annotations

import json
from string import Template

try:
    from .actions import parse_action_record
    from .scoring import score_actions, summarize_scores
except ImportError:  # direct script/test execution from this directory
    from actions import parse_action_record
    from scoring import score_actions, summarize_scores


def render_prompt(packet: dict, template_text: str) -> str:
    payload = json.dumps(packet["evidence_packet"], indent=2, sort_keys=True)
    return template_text.replace("{{EVIDENCE_PACKET_JSON}}", payload)


def make_request_records(packets: list[dict], template_text: str, model: str = "unset") -> list[dict]:
    """Create model-agnostic request JSONL records without calling any API."""
    records = []
    for packet in packets:
        records.append({
            "packet_id": packet["packet_id"],
            "panel_id": packet["panel_id"],
            "cue_condition": packet["cue_condition"],
            "model": model,
            "prompt": render_prompt(packet, template_text),
        })
    return records


def _display_to_gene(packet: dict) -> dict[str, str]:
    return {row["gene_display"]: row["gene"] for row in packet.get("scoring_key", [])}


def normalize_episode_actions(packet: dict, episode: dict) -> dict[str, str]:
    """Map an episode's displayed gene labels back to true genes."""
    display_map = _display_to_gene(packet)
    out = {}
    for label, value in episode.get("actions", {}).items():
        true_gene = display_map.get(label, label)
        out[true_gene] = parse_action_record(value)["action"]
    return out


def score_episode_record(panel: dict, packet: dict, episode: dict, lam: float = 0.5, defer_penalty: float = 0.0) -> dict:
    actions = normalize_episode_actions(packet, episode)
    score = score_actions(panel, actions, lam, defer_penalty=defer_penalty)
    score.update({
        "packet_id": packet["packet_id"],
        "cue_condition": packet["cue_condition"],
        "model": episode.get("model", "unknown"),
    })
    return score


def score_episode_records(
    panels: list[dict],
    packets: list[dict],
    episodes: list[dict],
    lam: float = 0.5,
    defer_penalty: float = 0.0,
) -> dict:
    panel_map = {panel["panel_id"]: panel for panel in panels}
    packet_map = {packet["packet_id"]: packet for packet in packets}
    rows = []
    for episode in episodes:
        packet = packet_map[episode["packet_id"]]
        panel = panel_map[packet["panel_id"]]
        rows.append(score_episode_record(panel, packet, episode, lam, defer_penalty=defer_penalty))
    return {"rows": rows, "summary": summarize_scores(rows)}


def make_policy_episode_records(panels: list[dict], packets: list[dict], policy_name: str) -> list[dict]:
    """Materialize deterministic baseline policy actions as episode JSONL records."""
    try:
        from . import baselines
    except ImportError:
        import baselines
    if not hasattr(baselines, policy_name):
        raise ValueError(f"unknown policy {policy_name!r}")
    policy = getattr(baselines, policy_name)
    panel_map = {panel["panel_id"]: panel for panel in panels}
    records = []
    for packet in packets:
        panel = panel_map[packet["panel_id"]]
        true_actions = policy(panel)
        display_by_gene = {row["gene"]: row["gene_display"] for row in packet.get("scoring_key", [])}
        actions = {
            display_by_gene.get(gene, gene): {"action": action, "rationale": f"synthetic policy {policy_name}"}
            for gene, action in true_actions.items()
        }
        records.append({
            "packet_id": packet["packet_id"],
            "model": f"policy::{policy_name}",
            "actions": actions,
            "self_reported_cues": [policy_name],
        })
    return records
