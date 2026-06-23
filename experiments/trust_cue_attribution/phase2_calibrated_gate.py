"""Phase 2 calibrated gate: map raw confidence to P(wrong) before routing.

The raw gate uses risk = 1 - pLDDT/100, which is compressed near 0 (pLDDT ~ 0.9 ->
risk ~ 0.1), so the principled "verify iff risk > lambda" rule never fires and
the policy degenerates to trust-all. Here we fit a monotonic isotonic
calibration risk -> P(lDDT-wrong) on a leave-one-out basis (honest, no in-sample
overfit), so the calibrated risk lands on the P(wrong) scale and the verify rule
triggers where the specialist is actually likely wrong.

Signal-validity AUROC is monotonic-invariant, so calibration does NOT change it
(it stays whatever the raw gate found); calibration only fixes the policy.
Re-derives the wrong-label from continuous lDDT (`truth.quality`) at a
substrate-appropriate cutoff (default 0.9; lDDT>=0.7 is degenerate because
Boltz-2 is correct on ~95% of recent targets). Pure-python; unit-tested.
"""

from __future__ import annotations

import argparse
import bisect
import json
import os
from typing import Any, Callable, Optional

try:
    from .phase2_calibration_gate import _decorrelated_permutation, confidence_to_risk
    from .phase1c_specialist_metric_check import auroc
except ImportError:  # direct script/test execution
    from phase2_calibration_gate import _decorrelated_permutation, confidence_to_risk
    from phase1c_specialist_metric_check import auroc

DEFAULT_CORRECT_LDDT = 0.9
DEFAULT_LAMBDA = 0.5
VALIDITY_AUROC_MIN = 0.70
SHUFFLED_GAP_MIN = 0.05
MIN_PER_REGIME = 30


def _pava(values: list[float]) -> list[float]:
    """Pool-adjacent-violators isotonic fit (non-decreasing), values pre-sorted by x."""
    blocks: list[list[float]] = []  # [mean, size]
    for v in values:
        blocks.append([v, 1.0])
        while len(blocks) >= 2 and blocks[-2][0] > blocks[-1][0]:
            v1, s1 = blocks.pop()
            v0, s0 = blocks.pop()
            blocks.append([(v0 * s0 + v1 * s1) / (s0 + s1), s0 + s1])
    out: list[float] = []
    for mean, size in blocks:
        out.extend([mean] * int(size))
    return out


def isotonic_calibrator(x: list[float], y: list[float]) -> Callable[[float], float]:
    """Fit monotonic x -> y (isotonic); return a step predictor for new x."""
    order = sorted(range(len(x)), key=lambda i: x[i])
    xs = [x[i] for i in order]
    fitted = _pava([y[i] for i in order])

    def predict(xq: float) -> float:
        idx = bisect.bisect_right(xs, xq) - 1
        if idx < 0:
            return fitted[0]
        if idx >= len(fitted):
            return fitted[-1]
        return fitted[idx]

    return predict


def loo_calibrated_risks(raw_risks: list[float], wrong: list[int]) -> list[float]:
    """Leave-one-out isotonic calibration of raw risk -> P(wrong)."""
    n = len(raw_risks)
    out: list[float] = []
    for i in range(n):
        x = [raw_risks[j] for j in range(n) if j != i]
        y = [float(wrong[j]) for j in range(n) if j != i]
        out.append(isotonic_calibrator(x, y)(raw_risks[i]) if x else 0.0)
    return out


def _policy_net(wrong: list[int], risks: list[float], lam: float) -> float:
    """verify iff risk>lam (correct, cost lam), else trust (correct iff not wrong)."""
    if not wrong:
        return 0.0
    correct = assays = 0.0
    for w, r in zip(wrong, risks):
        if r > lam:
            correct += 1.0; assays += 1.0
        elif not w:
            correct += 1.0
    n = len(wrong)
    return correct / n - lam * (assays / n)


def _round(v: Optional[float]) -> Optional[float]:
    return None if v is None else round(float(v), 6)


def calibrated_gate(records: list[dict[str, Any]], *, lam: float = DEFAULT_LAMBDA,
                    correct_lddt: float = DEFAULT_CORRECT_LDDT,
                    validity_auroc_min: float = VALIDITY_AUROC_MIN,
                    shuffled_gap_min: float = SHUFFLED_GAP_MIN,
                    min_per_regime: int = MIN_PER_REGIME) -> dict[str, Any]:
    raw = [confidence_to_risk(r) for r in records]
    wrong = [0 if float(r["truth"]["quality"]) >= correct_lddt else 1 for r in records]
    cal = loo_calibrated_risks(raw, wrong)

    validity_auroc = auroc(raw, wrong)  # monotonic-invariant -> raw == calibrated
    real = _policy_net(wrong, cal, lam)
    shuffled = _policy_net(wrong, _decorrelated_permutation(cal), lam)
    inverted = _policy_net(wrong, [1.0 - c for c in cal], lam)
    best_control = max(shuffled, inverted)
    n = len(records)
    trust_all = sum(1 for w in wrong if not w) / n if n else 0.0
    oracle = 1.0 - lam * (sum(wrong) / n) if n else 0.0
    n_mono = sum(1 for r in records if r.get("regime") == "monomer")
    n_cplx = sum(1 for r in records if r.get("regime") == "complex")

    checks = {
        "signal_validity_auroc_ok": bool(validity_auroc is not None and validity_auroc >= validity_auroc_min),
        "policy_beats_trust_all": real > trust_all,
        "policy_beats_best_control": real > best_control,
        "real_vs_shuffled_gap_large": (real - shuffled) >= shuffled_gap_min,
        "power_sufficient": n_mono >= min_per_regime and n_cplx >= min_per_regime,
    }
    core = (checks["signal_validity_auroc_ok"] and checks["policy_beats_trust_all"]
            and checks["policy_beats_best_control"] and checks["real_vs_shuffled_gap_large"])
    if core and checks["power_sufficient"]:
        decision = "eligible_for_phase2_interface_pilot"
    elif core:
        decision = "eligible_pending_more_targets"
    elif checks["signal_validity_auroc_ok"]:
        decision = "redesign_policy_before_pilot"
    else:
        decision = "do_not_run_signal_not_calibrated"
    return {
        "phase": "phase2",
        "status": "calibrated_gate_ready",
        "claim_boundary": "Offline gate with LOO isotonic risk->P(wrong) calibration; no LLM calls.",
        "calibration": "leave_one_out_isotonic_raw_risk_to_p_wrong",
        "correct_lddt_cutoff": correct_lddt,
        "lambda": lam,
        "scope": {"n_targets": n, "n_monomer": n_mono, "n_complex": n_cplx, "n_wrong": sum(wrong)},
        "signal_validity": {"wrong_risk_auroc": _round(validity_auroc), "threshold": validity_auroc_min},
        "net_reward_per_target": {
            "calibrated_real_policy": _round(real),
            "calibrated_shuffled_control": _round(shuffled),
            "calibrated_inverted_control": _round(inverted),
            "trust_all": _round(trust_all),
            "oracle": _round(oracle),
        },
        "margins": {
            "vs_trust_all": _round(real - trust_all),
            "vs_best_control": _round(real - best_control),
            "real_minus_shuffled": _round(real - shuffled),
            "oracle_headroom": _round(oracle - trust_all),
        },
        "checks": checks,
        "decision": decision,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--out", default="experiments/trust_cue_attribution/results/phase2_preflight/calibrated_gate.json")
    ap.add_argument("--lam", type=float, default=DEFAULT_LAMBDA)
    ap.add_argument("--correct-lddt", type=float, default=DEFAULT_CORRECT_LDDT)
    args = ap.parse_args()
    records = [json.loads(line) for line in open(args.records) if line.strip()]
    gate = calibrated_gate(records, lam=args.lam, correct_lddt=args.correct_lddt)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(gate, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"wrote {args.out}")
    print(json.dumps({"decision": gate["decision"], "scope": gate["scope"],
                      "signal_validity": gate["signal_validity"], "margins": gate["margins"],
                      "net": gate["net_reward_per_target"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
