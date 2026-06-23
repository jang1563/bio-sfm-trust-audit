"""Score the Phase 2 LLM interface pilot: actions vs lDDT-truth under cost.

Each packet is one structure-prediction trust decision (`<target_id>::<arm>`).
Reward per target = correct - lambda * assays:
  trust_sfm        correct iff the prediction is good (lDDT >= cutoff); 0 assays
  verify_assay     always correct; 1 assay (cost lambda)
  default_baseline correct iff the template baseline is good; 0 assays
  defer / missing  not correct; 0 assays
Reports per-arm metrics, paired cue effects vs no_signal, and a monomer/complex
split. Truth comes from the hidden records (lDDT quality); pure-stdlib.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from typing import Any, Optional

ARMS = [
    "no_signal", "raw_plddt_shown", "calibrated_risk_shown_no_recommendation",
    "calibrated_interface_shown", "inverted_reliability_interface_control",
]
DEFAULT_CORRECT_LDDT = 0.9
DEFAULT_LAMBDA = 0.5


def episode_action(ep: dict[str, Any]) -> str:
    act = ep.get("actions", {})
    if isinstance(act, dict):
        tgt = act.get("target")
        if isinstance(tgt, dict) and isinstance(tgt.get("action"), str):
            return tgt["action"]
    return "defer"  # missing / parse_error / provider_error -> defer (visible non-answer)


def outcome(action: str, target_correct: bool, template_correct: bool, lam: float) -> tuple[int, int]:
    """Return (correct, assays)."""
    if action == "verify_assay":
        return 1, 1
    if action == "trust_sfm":
        return (1 if target_correct else 0), 0
    if action == "default_baseline":
        return (1 if template_correct else 0), 0
    return 0, 0  # defer


def _summary(rows: list[dict[str, Any]], lam: float) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {"n": 0}
    correct = sum(r["correct"] for r in rows)
    assays = sum(r["assays"] for r in rows)
    acts = [r["action"] for r in rows]
    trust_err = sum(1 for r in rows if r["action"] == "trust_sfm" and not r["target_correct"])
    return {
        "n": n,
        "accuracy": round(correct / n, 6),
        "assays_per_target": round(assays / n, 6),
        "net_reward_per_target": round((correct - lam * assays) / n, 6),
        "trust_error_rate": round(trust_err / n, 6),
        "trust_rate": round(acts.count("trust_sfm") / n, 6),
        "verify_rate": round(acts.count("verify_assay") / n, 6),
        "default_rate": round(acts.count("default_baseline") / n, 6),
        "defer_rate": round(acts.count("defer") / n, 6),
    }


def score_episodes(episodes: list[dict[str, Any]], records: list[dict[str, Any]], *,
                   lam: float = DEFAULT_LAMBDA, correct_lddt: float = DEFAULT_CORRECT_LDDT) -> dict[str, Any]:
    truth = {
        str(r["target_id"]): {
            "regime": r.get("regime"),
            "target_correct": float(r["truth"]["quality"]) >= correct_lddt,
            "template_correct": bool(r.get("template_baseline_correct", False)),
        }
        for r in records
    }
    by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_arm_regime: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    action_by_target_arm: dict[tuple[str, str], dict[str, Any]] = {}
    for ep in episodes:
        pid = ep.get("packet_id", "")
        target_id = pid.split("::")[0]
        arm = ep.get("cue_condition") or (pid.split("::")[1] if "::" in pid else "?")
        t = truth.get(target_id)
        if t is None:
            continue
        action = episode_action(ep)
        c, a = outcome(action, t["target_correct"], t["template_correct"], lam)
        row = {"target_id": target_id, "arm": arm, "action": action, "correct": c,
               "assays": a, "target_correct": t["target_correct"], "regime": t["regime"]}
        by_arm[arm].append(row)
        by_arm_regime[(arm, t["regime"])].append(row)
        action_by_target_arm[(target_id, arm)] = row

    per_arm = {arm: _summary(by_arm.get(arm, []), lam) for arm in ARMS}
    per_arm_regime = {
        f"{arm}::{regime}": _summary(by_arm_regime.get((arm, regime), []), lam)
        for arm in ARMS for regime in ("monomer", "complex")
    }

    # paired cue effects vs no_signal (same targets)
    paired: dict[str, Any] = {}
    base_targets = {r["target_id"] for r in by_arm.get("no_signal", [])}
    for arm in ARMS:
        if arm == "no_signal":
            continue
        dn = dacc = dassay = changed = npair = 0.0
        for tid in base_targets:
            b = action_by_target_arm.get((tid, "no_signal"))
            x = action_by_target_arm.get((tid, arm))
            if b is None or x is None:
                continue
            npair += 1
            dn += (x["correct"] - lam * x["assays"]) - (b["correct"] - lam * b["assays"])
            dacc += x["correct"] - b["correct"]
            dassay += x["assays"] - b["assays"]
            changed += 1 if x["action"] != b["action"] else 0
        if npair:
            paired[arm] = {
                "n_pairs": int(npair),
                "delta_net_per_target": round(dn / npair, 6),
                "delta_accuracy": round(dacc / npair, 6),
                "delta_assays": round(dassay / npair, 6),
                "action_changed_rate": round(changed / npair, 6),
            }
    return {
        "phase": "phase2", "lambda": lam, "correct_lddt_cutoff": correct_lddt,
        "n_episodes": len(episodes),
        "parse_errors": sum(1 for e in episodes if "parse_error" in e),
        "provider_errors": sum(1 for e in episodes if "provider_error" in e),
        "per_arm": per_arm,
        "per_arm_by_regime": per_arm_regime,
        "paired_cue_effects_vs_no_signal": paired,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", required=True)
    ap.add_argument("--records", required=True)
    ap.add_argument("--lam", type=float, default=DEFAULT_LAMBDA)
    ap.add_argument("--correct-lddt", type=float, default=DEFAULT_CORRECT_LDDT)
    ap.add_argument("--out", default="experiments/trust_cue_attribution/results/phase2_preflight/interface_pilot_score.json")
    args = ap.parse_args()
    episodes = [json.loads(line) for line in open(args.episodes) if line.strip()]
    records = [json.loads(line) for line in open(args.records) if line.strip()]
    result = score_episodes(episodes, records, lam=args.lam, correct_lddt=args.correct_lddt)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(json.dumps({"per_arm_net": {a: result["per_arm"][a].get("net_reward_per_target") for a in ARMS},
                      "paired": {a: v.get("delta_net_per_target") for a, v in result["paired_cue_effects_vs_no_signal"].items()},
                      "parse_errors": result["parse_errors"], "provider_errors": result["provider_errors"]},
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
