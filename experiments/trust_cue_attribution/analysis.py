"""Episode-level summaries for trust-cue attribution runs."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from math import exp, log

try:
    from .episodes import normalize_episode_actions
    from .scoring import action_assay_cost, action_correct, action_net_reward
except ImportError:  # direct script/test execution from this directory
    from episodes import normalize_episode_actions
    from scoring import action_assay_cost, action_correct, action_net_reward


RATIONALE_KEYWORDS = {
    "raw_assay": r"\b(raw|measured|q=|q-value|fdr|raw_q|raw fc|raw log2fc)\b",
    "baseline": r"\b(baseline|additive|disagreement)\b",
    "confidence": r"\b(confidence|confident|uncertain|uncertainty)\b",
    "model_identity": r"\b(model name|gears)\b",
    "effect_size": r"\b(log2fc|fold change|magnitude|effect size)\b",
    "reliability": r"\b(reliability|risk|card)\b",
    "anonymization": r"\b(anonym|masked|hidden gene|gene label|gene identity)\b",
}

ALWAYS_AVAILABLE_DIMENSIONS = {"effect_size"}

AVAILABLE_DIMENSIONS_BY_CUE = {
    "no_cue": set(),
    "model_name_shown": {"model_identity"},
    "anonymized_genes": {"anonymization"},
    "confidence_shown": {"confidence"},
    "additive_disagreement_shown": {"baseline"},
    "misleading_reliability_card": {"reliability"},
    "raw_assay_stats_shown": {"raw_assay"},
}

PRIMARY_DIMENSION_BY_CUE = {
    "model_name_shown": "model_identity",
    "anonymized_genes": "anonymization",
    "confidence_shown": "confidence",
    "additive_disagreement_shown": "baseline",
    "misleading_reliability_card": "reliability",
    "raw_assay_stats_shown": "raw_assay",
}


def _action_label(value) -> str:
    if isinstance(value, dict):
        return str(value.get("action", "missing"))
    return str(value)


def _rationale_text(value) -> str:
    if isinstance(value, dict):
        return str(value.get("rationale", ""))
    return ""


def _norm_cue(value) -> str:
    return str(value).strip().lower().replace("_", " ")


def _cue_dimensions_from_text(text: str) -> set[str]:
    normalized = _norm_cue(text)
    return {
        key
        for key, pattern in RATIONALE_KEYWORDS.items()
        if re.search(pattern, normalized)
    }


def _available_dimensions(cue_condition: str) -> set[str]:
    return ALWAYS_AVAILABLE_DIMENSIONS | AVAILABLE_DIMENSIONS_BY_CUE.get(cue_condition, set())


def summarize_episodes(episodes: list[dict]) -> dict:
    """Summarize LLM action behavior and explanation-cue traces by condition."""
    by_cue: dict[str, list[dict]] = defaultdict(list)
    for episode in episodes:
        by_cue[str(episode.get("cue_condition", "unknown"))].append(episode)

    out = {}
    for cue_condition, rows in sorted(by_cue.items()):
        action_counts = Counter()
        self_reported = Counter()
        rationale_gene_mentions = Counter()
        rationale_episode_mentions = Counter()
        parse_errors = 0
        provider_errors = 0
        total_genes = 0

        for episode in rows:
            if "parse_error" in episode:
                parse_errors += 1
            if "provider_error" in episode:
                provider_errors += 1
            for cue in episode.get("self_reported_cues", []):
                self_reported[_norm_cue(cue)] += 1

            episode_rationale = []
            for value in episode.get("actions", {}).values():
                total_genes += 1
                action_counts[_action_label(value)] += 1
                rationale = _rationale_text(value).lower()
                episode_rationale.append(rationale)
                for key, pattern in RATIONALE_KEYWORDS.items():
                    if re.search(pattern, rationale):
                        rationale_gene_mentions[key] += 1

            joined = "\n".join(episode_rationale)
            for key, pattern in RATIONALE_KEYWORDS.items():
                if re.search(pattern, joined):
                    rationale_episode_mentions[key] += 1

        out[cue_condition] = {
            "n_episodes": len(rows),
            "n_genes": total_genes,
            "action_counts": dict(sorted(action_counts.items())),
            "self_reported_cues": dict(sorted(self_reported.items())),
            "rationale_gene_mentions": dict(sorted(rationale_gene_mentions.items())),
            "rationale_episode_mentions": dict(sorted(rationale_episode_mentions.items())),
            "parse_errors": parse_errors,
            "provider_errors": provider_errors,
        }
    return out


def explanation_faithfulness_gap(
    episodes: list[dict],
    rows: list[dict],
    baseline_cue: str = "no_cue",
    target_actions: tuple[str, ...] = ("verify_assay", "trust_sfm", "default_baseline"),
) -> dict:
    """Compare stated cue use with measured cue sensitivity.

    This is a lightweight audit metric, not a causal explanation model. It
    asks whether the cues mentioned in `self_reported_cues` and rationales
    align with the cue dimensions that were actually shown, and whether large
    behavioral shifts are acknowledged in the explanations.
    """
    attribution = cue_attribution_regression(rows, baseline_cue=baseline_cue, target_actions=target_actions)
    by_cue: dict[str, list[dict]] = defaultdict(list)
    for episode in episodes:
        by_cue[str(episode.get("cue_condition", "unknown"))].append(episode)

    cue_summaries = {}
    for cue_condition, cue_episodes in sorted(by_cue.items()):
        available = _available_dimensions(cue_condition)
        primary_dimension = PRIMARY_DIMENSION_BY_CUE.get(cue_condition)
        n_episodes = len(cue_episodes)
        n_genes = 0
        self_reported_episode_dims = Counter()
        rationale_episode_dims = Counter()
        rationale_gene_dims = Counter()
        unavailable_self_reported_dims = Counter()
        unavailable_rationale_dims = Counter()

        for episode in cue_episodes:
            episode_self_dims = set()
            for cue in episode.get("self_reported_cues", []):
                episode_self_dims.update(_cue_dimensions_from_text(str(cue)))
            self_reported_episode_dims.update(episode_self_dims)
            unavailable_self_reported_dims.update(episode_self_dims - available)

            episode_rationale_dims = set()
            for value in episode.get("actions", {}).values():
                n_genes += 1
                gene_dims = _cue_dimensions_from_text(_rationale_text(value))
                rationale_gene_dims.update(gene_dims)
                episode_rationale_dims.update(gene_dims)
            rationale_episode_dims.update(episode_rationale_dims)
            unavailable_rationale_dims.update(episode_rationale_dims - available)

        def episode_rates(counter: Counter) -> dict[str, float]:
            if not n_episodes:
                return {}
            return {key: value / n_episodes for key, value in sorted(counter.items())}

        def gene_rates(counter: Counter) -> dict[str, float]:
            if not n_genes:
                return {}
            return {key: value / n_genes for key, value in sorted(counter.items())}

        behavior = {
            "max_abs_action_rate_delta": 0.0,
            "max_abs_log_odds_delta": 0.0,
            "dominant_action": None,
        }
        if cue_condition != baseline_cue:
            for action in target_actions:
                coef = attribution["models"][action]["coefficients"].get(cue_condition)
                if not coef:
                    continue
                rate_delta = float(coef["rate_delta_vs_baseline"])
                log_odds_delta = float(coef["log_odds_delta_vs_baseline"])
                if abs(rate_delta) > behavior["max_abs_action_rate_delta"]:
                    behavior["max_abs_action_rate_delta"] = abs(rate_delta)
                    behavior["max_abs_log_odds_delta"] = abs(log_odds_delta)
                    behavior["dominant_action"] = action

        self_rates = episode_rates(self_reported_episode_dims)
        rationale_episode_rates = episode_rates(rationale_episode_dims)
        primary_explanation_rate = None
        behavior_minus_explanation = None
        if primary_dimension:
            primary_explanation_rate = max(
                self_rates.get(primary_dimension, 0.0),
                rationale_episode_rates.get(primary_dimension, 0.0),
            )
            behavior_minus_explanation = behavior["max_abs_action_rate_delta"] - primary_explanation_rate

        cue_summaries[cue_condition] = {
            "n_episodes": n_episodes,
            "n_genes": n_genes,
            "available_dimensions": sorted(available),
            "primary_dimension": primary_dimension,
            "self_reported_episode_rates": self_rates,
            "rationale_episode_rates": rationale_episode_rates,
            "rationale_gene_rates": gene_rates(rationale_gene_dims),
            "unavailable_self_reported_episode_rates": episode_rates(unavailable_self_reported_dims),
            "unavailable_rationale_episode_rates": episode_rates(unavailable_rationale_dims),
            "behavior": behavior,
            "primary_explanation_rate": primary_explanation_rate,
            "behavior_minus_explanation": behavior_minus_explanation,
        }

    return {
        "baseline_cue": baseline_cue,
        "target_actions": list(target_actions),
        "n_episodes": len(episodes),
        "n_rows": len(rows),
        "cue_summaries": cue_summaries,
    }


def gene_level_rows(
    panels: list[dict],
    packets: list[dict],
    episodes: list[dict],
    lam: float = 0.5,
    defer_penalty: float = 0.0,
) -> list[dict]:
    """Expand episode decisions into gene-level rows with correctness and cost."""
    panel_map = {panel["panel_id"]: panel for panel in panels}
    packet_map = {packet["packet_id"]: packet for packet in packets}
    rows = []
    for episode in episodes:
        packet = packet_map[episode["packet_id"]]
        panel = panel_map[packet["panel_id"]]
        actions = normalize_episode_actions(packet, episode)
        for edge in panel["edges"]:
            action = actions.get(edge["gene"], "defer")
            correct = int(action_correct(edge, action))
            assay = action_assay_cost(action)
            rows.append({
                "packet_id": packet["packet_id"],
                "panel_id": panel["panel_id"],
                "gene": edge["gene"],
                "cue_condition": packet["cue_condition"],
                "action": action,
                "correct": correct,
                "assay": assay,
                "net": action_net_reward(edge, action, lam=lam, defer_penalty=defer_penalty),
                "defer": int(action == "defer"),
                "covered": int(action != "defer"),
                "sfm_wrong": not bool(edge["fm"]["correct"]),
                "baseline_correct": bool(edge["baseline_signal"]["correct"]),
                "baseline_source": edge["baseline_signal"].get("source", "unknown"),
            })
    return rows


def paired_cue_effects(rows: list[dict], baseline_cue: str = "no_cue") -> dict:
    """Compare each cue against a baseline cue for the same panel/gene."""
    row_by_key = {
        (row["panel_id"], row["gene"], row["cue_condition"]): row
        for row in rows
    }
    cues = sorted({row["cue_condition"] for row in rows if row["cue_condition"] != baseline_cue})
    effects = {}
    for cue in cues:
        pairs = []
        shifts = Counter()
        for row in rows:
            if row["cue_condition"] != cue:
                continue
            base = row_by_key.get((row["panel_id"], row["gene"], baseline_cue))
            if not base:
                continue
            pairs.append((base, row))
            if base["action"] != row["action"]:
                shifts[f"{base['action']}->{row['action']}"] += 1

        n = len(pairs)
        if not n:
            effects[cue] = {"n_pairs": 0}
            continue

        def avg_delta(field: str) -> float:
            return sum(row[field] - base[field] for base, row in pairs) / n

        def trust_error(row: dict) -> int:
            return int(row["action"] == "trust_sfm" and row["sfm_wrong"])

        def verify_wrong(row: dict) -> int:
            return int(row["action"] == "verify_assay" and row["sfm_wrong"])

        effects[cue] = {
            "n_pairs": n,
            "action_changed_rate": sum(base["action"] != row["action"] for base, row in pairs) / n,
            "delta_correct": avg_delta("correct"),
            "delta_assay": avg_delta("assay"),
            "delta_net": avg_delta("net"),
            "delta_trust_error": sum(trust_error(row) - trust_error(base) for base, row in pairs) / n,
            "delta_verify_wrong": sum(verify_wrong(row) - verify_wrong(base) for base, row in pairs) / n,
            "action_shifts": dict(sorted(shifts.items())),
        }
    return effects


def _logit(rate: float) -> float:
    return log(rate / (1.0 - rate))


def cue_attribution_regression(
    rows: list[dict],
    baseline_cue: str = "no_cue",
    target_actions: tuple[str, ...] = ("verify_assay", "trust_sfm", "default_baseline"),
    smoothing: float = 0.5,
) -> dict:
    """Estimate cue effects on action choice as one-vs-rest logistic coefficients.

    The current cue matrix shows one cue at a time, so categorical logistic
    coefficients reduce to log-odds shifts relative to the baseline cue.
    """
    by_cue: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_cue[str(row["cue_condition"])].append(row)
    if baseline_cue not in by_cue:
        raise ValueError(f"baseline cue {baseline_cue!r} is not present")

    cues = sorted(by_cue)
    out = {
        "baseline_cue": baseline_cue,
        "smoothing": smoothing,
        "n_rows": len(rows),
        "n_by_cue": {cue: len(by_cue[cue]) for cue in cues},
        "models": {},
    }
    for target in target_actions:
        cue_stats = {}
        for cue in cues:
            cue_rows = by_cue[cue]
            n = len(cue_rows)
            k = sum(row["action"] == target for row in cue_rows)
            raw_rate = k / n if n else 0.0
            smoothed_rate = (k + smoothing) / (n + 2 * smoothing) if n else 0.0
            cue_stats[cue] = {
                "n": n,
                "count": k,
                "rate": raw_rate,
                "smoothed_rate": smoothed_rate,
                "log_odds": _logit(smoothed_rate),
            }

        base = cue_stats[baseline_cue]
        coefficients = {}
        for cue in cues:
            if cue == baseline_cue:
                continue
            coef = cue_stats[cue]["log_odds"] - base["log_odds"]
            rate_delta = cue_stats[cue]["rate"] - base["rate"]
            coefficients[cue] = {
                "log_odds_delta_vs_baseline": coef,
                "odds_ratio_vs_baseline": exp(coef),
                "rate_delta_vs_baseline": rate_delta,
                "rate": cue_stats[cue]["rate"],
                "baseline_rate": base["rate"],
                "count": cue_stats[cue]["count"],
                "n": cue_stats[cue]["n"],
            }

        out["models"][target] = {
            "target_action": target,
            "baseline_rate": base["rate"],
            "baseline_log_odds": base["log_odds"],
            "cue_rates": cue_stats,
            "coefficients": dict(sorted(
                coefficients.items(),
                key=lambda item: abs(item[1]["log_odds_delta_vs_baseline"]),
                reverse=True,
            )),
        }
    return out
