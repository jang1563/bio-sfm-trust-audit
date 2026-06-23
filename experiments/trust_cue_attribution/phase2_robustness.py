"""Phase 2 pilot robustness: lambda sweep + target-bootstrap CIs on key contrasts.

Re-scores the existing episodes (no new API) at several lambda, and bootstraps
over targets (resample with replacement, seed 13, 1000 draws) to put 95% CIs on
the contrasts that matter for not-overclaiming:
  calibrated_interface vs no_signal      (does the card help at all?)
  calibrated_interface vs raw_plddt       (does calibration beat raw pLDDT? -- expect marginal)
  calibrated_interface vs no_recommendation (A4: info vs directive -- expect ~0)
  inverted vs no_signal                   (does a wrong card still 'help' via over-verification?)
Per-target (correct, assays) is lambda-independent; net = correct - lambda*assays.
Pure-stdlib.
"""

from __future__ import annotations

import argparse
import json
import os
import random
from collections import defaultdict
from typing import Any

try:
    from .phase2_score_episodes import ARMS, episode_action, outcome
except ImportError:
    from phase2_score_episodes import ARMS, episode_action, outcome

LAMBDAS = (0.2, 0.5, 0.8)
CONTRASTS = [
    ("calibrated_interface_shown", "no_signal"),
    ("calibrated_risk_shown_no_recommendation", "no_signal"),
    ("raw_plddt_shown", "no_signal"),
    ("inverted_reliability_interface_control", "no_signal"),
    ("calibrated_interface_shown", "raw_plddt_shown"),
    ("calibrated_interface_shown", "calibrated_risk_shown_no_recommendation"),
]


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def build_outcome_table(episodes: list[dict[str, Any]], records: list[dict[str, Any]],
                        correct_lddt: float) -> dict[str, dict[str, tuple[int, int]]]:
    truth = {
        str(r["target_id"]): (float(r["truth"]["quality"]) >= correct_lddt,
                              bool(r.get("template_baseline_correct", False)))
        for r in records
    }
    table: dict[str, dict[str, tuple[int, int]]] = defaultdict(dict)
    for ep in episodes:
        pid = ep.get("packet_id", "")
        tid = pid.split("::")[0]
        arm = ep.get("cue_condition") or (pid.split("::")[1] if "::" in pid else "?")
        if tid not in truth:
            continue
        tc, tmpl = truth[tid]
        table[tid][arm] = outcome(episode_action(ep), tc, tmpl, 0.5)  # (correct, assays); lambda-free
    return table


def _net(ca: tuple[int, int], lam: float) -> float:
    return ca[0] - lam * ca[1]


def lambda_sweep(table: dict[str, dict[str, tuple[int, int]]], lams=LAMBDAS) -> dict[str, dict[str, float]]:
    targets = list(table)
    return {
        str(lam): {arm: round(_mean([_net(table[t][arm], lam) for t in targets if arm in table[t]]), 6)
                   for arm in ARMS}
        for lam in lams
    }


def bootstrap_contrasts(table: dict[str, dict[str, tuple[int, int]]], *, lam: float = 0.5,
                        n_boot: int = 1000, seed: int = 13) -> dict[str, Any]:
    rng = random.Random(seed)
    out: dict[str, Any] = {}
    for ax, ay in CONTRASTS:
        per_target = [(_net(table[t][ax], lam) - _net(table[t][ay], lam))
                      for t in table if ax in table[t] and ay in table[t]]
        if not per_target:
            continue
        point = _mean(per_target)
        m = len(per_target)
        means = sorted(_mean([per_target[rng.randrange(m)] for _ in range(m)]) for _ in range(n_boot))
        lo = means[int(0.025 * n_boot)]
        hi = means[int(0.975 * n_boot)]
        out[f"{ax}_vs_{ay}"] = {
            "n_pairs": m,
            "delta_net_point": round(point, 6),
            "ci95": [round(lo, 6), round(hi, 6)],
            "robust_positive": bool(lo > 0),
            "ci_crosses_zero": bool(lo <= 0 <= hi),
        }
    return out


def run(episodes: list[dict[str, Any]], records: list[dict[str, Any]], *,
        correct_lddt: float = 0.9, n_boot: int = 1000, seed: int = 13) -> dict[str, Any]:
    table = build_outcome_table(episodes, records, correct_lddt)
    return {
        "phase": "phase2", "analysis": "interface_pilot_robustness",
        "n_targets": len(table), "correct_lddt_cutoff": correct_lddt,
        "bootstrap": {"unit": "target", "n_boot": n_boot, "seed": seed, "lambda": 0.5},
        "lambda_sweep_net_per_target": lambda_sweep(table),
        "contrast_cis_lambda_0.5": bootstrap_contrasts(table, lam=0.5, n_boot=n_boot, seed=seed),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", required=True)
    ap.add_argument("--records", required=True)
    ap.add_argument("--correct-lddt", type=float, default=0.9)
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--out", default="experiments/trust_cue_attribution/results/phase2_preflight/interface_pilot_robustness.json")
    args = ap.parse_args()
    episodes = [json.loads(line) for line in open(args.episodes) if line.strip()]
    records = [json.loads(line) for line in open(args.records) if line.strip()]
    result = run(episodes, records, correct_lddt=args.correct_lddt, n_boot=args.n_boot, seed=args.seed)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
