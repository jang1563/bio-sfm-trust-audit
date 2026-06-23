"""Phase 2 protein-structure offline calibration gate.

Deterministic gate that must pass BEFORE any LLM pilot on the protein-structure
substrate (Boltz-2 / pLDDT). It checks whether the model-emitted confidence is a
genuinely calibrated wrong-risk signal, reproduces the monomer/complex
calibration gap (the routing stakes), and whether a principled risk-threshold
policy beats baselines and shuffled/inverted controls under cost-aware reward.
No LLM calls; truth fields are used only by this scorer, never model-visible.

Principled policy (no free threshold): if the confidence-derived risk is
calibrated, risk approximates P(specialist wrong), and the cost-optimal rule is
exactly "verify iff risk > lambda" (see the reward fundamentals). The gate tests
whether that rule, fed the REAL risk, beats trust-all, default-template, and
shuffled/inverted-risk controls -- and by a margin far larger than the
near-noise Phase 1C gap.

Input records JSONL, one target per line:

    {
      "target_id": "T1",
      "regime": "monomer" | "complex",
      "mean_plddt": 0..100,
      "iptm": 0..1 | null,                 # complexes
      "template_baseline_correct": bool,    # cheap template/homology model correct?
      "truth": {"correct": bool, "quality": float}   # HIDDEN: lDDT / DockQ-derived
    }
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Optional

try:
    from .phase1c_specialist_metric_check import auroc, pearson
except ImportError:  # direct script/test execution from this directory
    from phase1c_specialist_metric_check import auroc, pearson


VALIDITY_AUROC_MIN = 0.70
SHUFFLED_GAP_MIN = 0.05          # real-vs-shuffled net/target; must beat Phase 1C's ~0.003
MIN_PER_REGIME = 30              # pre-specified power floor per regime
DEFAULT_LAMBDA = 0.5


def confidence_to_risk(record: dict[str, Any]) -> float:
    """Map model-emitted confidence to an estimated wrong-risk in [0, 1].

    Monomer: risk = 1 - pLDDT/100. Complex: blend pLDDT with ipTM (interface
    confidence), since complex calibration leans on the interface.
    """
    plddt = float(record.get("mean_plddt", 0.0)) / 100.0
    if record.get("regime") == "complex" and record.get("iptm") is not None:
        risk = 1.0 - 0.5 * plddt - 0.5 * float(record["iptm"])
    else:
        risk = 1.0 - plddt
    return max(0.0, min(1.0, risk))


def _decorrelated_permutation(values: list[float]) -> list[float]:
    """Deterministic shuffle that breaks the value<->target association regardless
    of input ordering (no RNG): rotate by n//2 in value-sorted space, so
    low-ranked targets receive mid/high-ranked values and vice versa. A plain
    index rotation can leave the association intact for symmetric inputs."""
    n = len(values)
    if n < 2:
        return list(values)
    order = sorted(range(n), key=lambda i: values[i])
    k = n // 2
    shuffled = [0.0] * n
    for rank, idx in enumerate(order):
        shuffled[idx] = values[order[(rank + k) % n]]
    return shuffled


def risk_threshold_policy_net(records: list[dict[str, Any]], risks: list[float], lam: float) -> float:
    """Net reward per target for 'verify iff risk > lambda', else trust the specialist."""
    if not records:
        return 0.0
    correct = 0.0
    assays = 0.0
    for rec, risk in zip(records, risks):
        if risk > lam:
            correct += 1.0          # verify -> guaranteed correct
            assays += 1.0
        elif rec["truth"]["correct"]:
            correct += 1.0          # trust a correct specialist call
    n = len(records)
    return correct / n - lam * (assays / n)


def _regime_calibration(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Pearson(pLDDT, structure quality) within each regime; the gap is the stakes."""
    out: dict[str, Any] = {}
    for regime in ("monomer", "complex"):
        rows = [r for r in records if r.get("regime") == regime]
        plddt = [float(r["mean_plddt"]) for r in rows]
        quality = [float(r["truth"]["quality"]) for r in rows]
        out[regime] = {
            "n": len(rows),
            "pearson_plddt_vs_quality": _round(pearson(plddt, quality)) if len(rows) >= 2 else None,
        }
    mono = out["monomer"]["pearson_plddt_vs_quality"]
    comp = out["complex"]["pearson_plddt_vs_quality"]
    out["monomer_minus_complex"] = _round(mono - comp) if (mono is not None and comp is not None) else None
    return out


def phase2_calibration_gate(
    records: list[dict[str, Any]],
    *,
    lam: float = DEFAULT_LAMBDA,
    validity_auroc_min: float = VALIDITY_AUROC_MIN,
    shuffled_gap_min: float = SHUFFLED_GAP_MIN,
    min_per_regime: int = MIN_PER_REGIME,
) -> dict[str, Any]:
    """Score the deterministic calibration gate before any LLM pilot."""
    real_risks = [confidence_to_risk(r) for r in records]
    wrong_labels = [0 if r["truth"]["correct"] else 1 for r in records]
    shuffled_risks = _decorrelated_permutation(real_risks)
    inverted_risks = [1.0 - r for r in real_risks]

    validity_auroc = auroc(real_risks, wrong_labels)

    real_net = risk_threshold_policy_net(records, real_risks, lam)
    shuffled_net = risk_threshold_policy_net(records, shuffled_risks, lam)
    inverted_net = risk_threshold_policy_net(records, inverted_risks, lam)
    best_control = max(shuffled_net, inverted_net)

    n = len(records)
    trust_all = sum(1 for r in records if r["truth"]["correct"]) / n if n else 0.0
    default_template = sum(1 for r in records if r.get("template_baseline_correct")) / n if n else 0.0
    verify_all = 1.0 - lam
    oracle = 1.0 - lam * (sum(wrong_labels) / n) if n else 0.0

    regime = _regime_calibration(records)
    n_mono = regime["monomer"]["n"]
    n_comp = regime["complex"]["n"]

    checks = {
        "signal_validity_auroc_ok": bool(validity_auroc is not None and validity_auroc >= validity_auroc_min),
        "policy_beats_trust_all": real_net > trust_all,
        "policy_beats_default_template": real_net > default_template,
        "policy_beats_best_control": real_net > best_control,
        "real_vs_shuffled_gap_large": (real_net - shuffled_net) >= shuffled_gap_min,
        "power_sufficient": n_mono >= min_per_regime and n_comp >= min_per_regime,
    }
    core_ok = (
        checks["signal_validity_auroc_ok"]
        and checks["policy_beats_trust_all"]
        and checks["policy_beats_default_template"]
        and checks["policy_beats_best_control"]
        and checks["real_vs_shuffled_gap_large"]
    )
    if core_ok and checks["power_sufficient"]:
        decision = "eligible_for_phase2_interface_pilot"
    elif core_ok:
        decision = "eligible_pending_more_targets"
    elif checks["signal_validity_auroc_ok"]:
        decision = "redesign_policy_before_pilot"
    else:
        decision = "do_not_run_signal_not_calibrated"

    return {
        "phase": "phase2",
        "status": "calibration_gate_ready",
        "claim_boundary": (
            "Offline deterministic gate over a calibrated structure-confidence "
            "signal; no LLM calls, no leakage, no claim of faithful internal "
            "interpretation or general SFM generalization."
        ),
        "scope": {"n_targets": n, "n_monomer": n_mono, "n_complex": n_comp},
        "lambda": lam,
        "signal_validity": {
            "wrong_risk_auroc": _round(validity_auroc),
            "threshold": validity_auroc_min,
        },
        "regime_calibration": regime,
        "net_reward_per_target": {
            "real_risk_policy": _round(real_net),
            "shuffled_risk_control": _round(shuffled_net),
            "inverted_risk_control": _round(inverted_net),
            "trust_all": _round(trust_all),
            "default_template": _round(default_template),
            "verify_all": _round(verify_all),
            "oracle": _round(oracle),
        },
        "margins": {
            "vs_trust_all": _round(real_net - trust_all),
            "vs_default_template": _round(real_net - default_template),
            "vs_best_control": _round(real_net - best_control),
            "real_minus_shuffled": _round(real_net - shuffled_net),
        },
        "checks": checks,
        "decision": decision,
        "interpretation": _interpretation(decision),
    }


def write_phase2_calibration_gate(records: list[dict[str, Any]], out: str, **kwargs: Any) -> dict[str, Any]:
    gate = phase2_calibration_gate(records, **kwargs)
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as handle:
        json.dump(gate, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return gate


def _interpretation(decision: str) -> dict[str, str]:
    table = {
        "eligible_for_phase2_interface_pilot": (
            "The calibrated structure-confidence signal clears the gate and the "
            "risk>lambda policy beats baselines and controls by a real margin. "
            "Build the small Phase 2 interface pilot."
        ),
        "eligible_pending_more_targets": (
            "Signal and policy clear, but per-regime target counts are below the "
            "pre-specified power floor. Add post-cutoff targets before the pilot."
        ),
        "redesign_policy_before_pilot": (
            "The confidence signal is calibrated, but the deterministic policy "
            "does not beat baselines/controls cleanly. Revisit the risk transform "
            "or action mapping before any LLM call."
        ),
        "do_not_run_signal_not_calibrated": (
            "The confidence-derived risk does not predict structure wrongness "
            "above threshold. The substrate assumption failed; do not spend on a "
            "pilot."
        ),
    }
    return {"short_read": table[decision]}


def _round(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(float(value), 6)


def read_records(path: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in open(path) if line.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True, help="JSONL of per-target structure-confidence + hidden truth")
    ap.add_argument("--out", default="experiments/trust_cue_attribution/results/phase2_preflight/calibration_gate.json")
    ap.add_argument("--lam", type=float, default=DEFAULT_LAMBDA)
    args = ap.parse_args()
    gate = write_phase2_calibration_gate(read_records(args.records), args.out, lam=args.lam)
    print(f"wrote Phase 2 calibration gate to {args.out}")
    print(json.dumps({"decision": gate["decision"], "scope": gate["scope"],
                      "wrong_risk_auroc": gate["signal_validity"]["wrong_risk_auroc"],
                      "margins": gate["margins"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
