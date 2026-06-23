"""Deterministic baseline policies for the extended action set."""

from __future__ import annotations

import random

try:
    from .scoring import LAMBDAS, score_policy
except ImportError:  # direct script/test execution from this directory
    from scoring import LAMBDAS, score_policy


def trust_all_sfm(panel: dict) -> dict[str, str]:
    return {edge["gene"]: "trust_sfm" for edge in panel["edges"]}


def verify_all(panel: dict) -> dict[str, str]:
    return {edge["gene"]: "verify_assay" for edge in panel["edges"]}


def always_additive(panel: dict) -> dict[str, str]:
    return {edge["gene"]: "default_baseline" for edge in panel["edges"]}


def oracle_verify(panel: dict) -> dict[str, str]:
    return {
        edge["gene"]: ("verify_assay" if not edge["fm"]["correct"] else "trust_sfm")
        for edge in panel["edges"]
    }


def random_verify_at_budget(panel: dict, budget: float = 0.30, seed: int = 0) -> dict[str, str]:
    rng = random.Random(f"{seed}:{panel['panel_id']}")
    genes = [edge["gene"] for edge in panel["edges"]]
    k = max(1, round(len(genes) * budget)) if genes else 0
    verify = set(rng.sample(genes, k))
    return {gene: ("verify_assay" if gene in verify else "trust_sfm") for gene in genes}


def signal_gated_verify(panel: dict, budget: float = 0.20) -> dict[str, str]:
    edges = sorted(panel["edges"], key=lambda e: e["reliability_signal"]["score"], reverse=True)
    k = max(1, round(len(edges) * budget)) if edges else 0
    verify = {edge["gene"] for edge in edges[:k]}
    return {
        edge["gene"]: ("verify_assay" if edge["gene"] in verify else "default_baseline")
        for edge in panel["edges"]
    }


def run_baselines(panels: list[dict], lambdas: tuple[float, ...] = LAMBDAS, seed: int = 0) -> dict:
    policies = {
        "trust_all_sfm": trust_all_sfm,
        "verify_all": verify_all,
        "always_additive": always_additive,
        "oracle_verify": oracle_verify,
        "random_verify_at_budget": lambda p: random_verify_at_budget(p, seed=seed),
        "signal_gated_verify": signal_gated_verify,
    }
    return {
        str(lam): {name: score_policy(panels, policy, lam) for name, policy in policies.items()}
        for lam in lambdas
    }
