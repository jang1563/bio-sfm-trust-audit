"""Phase 4 confirmatory analysis driver (pre-registered).

Computes, per model and per lambda, the enforcement mechanisms and the registered
contrasts with paired target-bootstrap CIs and a Holm-Bonferroni-adjusted secondary
family. Parametric on data paths so the same driver runs on the N=57 exploratory set
(validation) and the N>=120 confirmatory set.

Free-form LLM episodes are expected under <episodes_dir>/<prefix>_<model>_seed*.jsonl
with cue_condition arms:
  calibrated_interface_shown            (correct calibrated card)   -> free-form / constrained / conformal source
  inverted_reliability_interface_control(inverted card)             -> manipulation (H4.2)
  corrupted_plus_raw                    (corrupted card + raw signal)-> adversarial (H4.4)
Mechanisms (gate/constrained/conformal/baselines) are post-hoc over risk + actions.
"""
from __future__ import annotations
import argparse, json, os, random
from phase4_confirmatory import (
    CUT, gate_action, constrained_action, crc_threshold, corrupt,
    net_of_action, boot_ci, holm, load_llm_actions, mean_net_llm)

PRIMARY_LAMBDA = 0.5


def load_records(path: str) -> dict:
    recs = {}
    for line in open(path):
        if line.strip():
            r = json.loads(line)
            recs[r["target_id"]] = r
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--risk", required=True, help="held-out calibrated P(wrong) per target_id")
    ap.add_argument("--cal-risk", default="", help="disjoint calibration {risk,wrong} for CRC; default = in-sample (validation only)")
    ap.add_argument("--episodes-dir", required=True)
    ap.add_argument("--prefix", default="p4s")
    ap.add_argument("--models", default="claude-sonnet-4-6,gpt-4.1,claude-opus-4-8")
    ap.add_argument("--lambdas", default="0.2,0.5,0.8")
    ap.add_argument("--crc-alpha", type=float, default=0.2)
    ap.add_argument("--corrupted-risk", default="", help="per-shape corrupted risk {shape:{tid:val}} from the runner; "
                    "enables shift/noise adversarial. Default: invert-only via corrupt().")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    recs = load_records(args.records)
    risk = json.load(open(args.risk))
    # adversarial corruption: arm name + per-target corrupted risk, per shape
    ADV = {"invert": "corrupted_invert_plus_raw", "shift": "corrupted_shift_plus_raw", "noise": "corrupted_noise_plus_raw"}
    if args.corrupted_risk:
        corrupted_risk = json.load(open(args.corrupted_risk))
    else:  # validation fallback: invert only, legacy arm name
        corrupted_risk = {"invert": {t: corrupt(v, "invert") for t, v in risk.items()}}
        ADV = {"invert": "corrupted_plus_raw"}
    tids = [t for t in recs if t in risk]
    models = args.models.split(",")
    lambdas = [float(x) for x in args.lambdas.split(",")]
    rng = random.Random(13)
    tc = {t: recs[t]["truth"]["quality"] >= CUT for t in tids}
    tmpl = {t: bool(recs[t].get("template_baseline_correct", False)) for t in tids}

    # CRC calibration pairs (risk, wrong). Disjoint set if provided, else in-sample (flagged).
    if args.cal_risk:
        cal = [(v["risk"], bool(v["wrong"])) for v in json.load(open(args.cal_risk)).values()]
        crc_insample = False
    else:
        cal = [(risk[t], not tc[t]) for t in tids]
        crc_insample = True
    tau_hat = crc_threshold(cal, args.crc_alpha)

    report = {"n": len(tids), "crc_alpha": args.crc_alpha, "crc_tau_hat": round(tau_hat, 4),
              "crc_insample_calibration": crc_insample, "by_lambda": {}}

    for lam in lambdas:
        pm = {}
        for m in models:
            A = load_llm_actions(os.path.join(args.episodes_dir, f"{args.prefix}_{m}_seed*.jsonl"))
            # per-target nets
            free = {t: mean_net_llm(A, "calibrated_interface_shown", t, tc[t], tmpl[t], lam) for t in tids}
            inv = {t: mean_net_llm(A, "inverted_reliability_interface_control", t, tc[t], tmpl[t], lam) for t in tids}
            gate = {t: net_of_action(gate_action(risk[t], lam), tc[t], tmpl[t], lam) for t in tids}
            # constrained: project each free-form action onto the gate-allowed set, then average
            con = {}
            for t in tids:
                acts = A.get((t, "calibrated_interface_shown"), ["defer"])
                con[t] = sum(net_of_action(constrained_action(a, risk[t], lam), tc[t], tmpl[t], lam) for a in acts) / len(acts)
            conf = {t: net_of_action("trust_sfm" if risk[t] <= tau_hat else "verify_assay", tc[t], tmpl[t], lam) for t in tids}
            trust_all = {t: net_of_action("trust_sfm", tc[t], tmpl[t], lam) for t in tids}
            verify_all = {t: net_of_action("verify_assay", tc[t], tmpl[t], lam) for t in tids}
            default_all = {t: net_of_action("default_baseline", tc[t], tmpl[t], lam) for t in tids}

            mean = lambda d: round(sum(d.values()) / len(tids), 4)
            realized_fa = sum(1 for t in tids if risk[t] <= tau_hat and not tc[t]) / len(tids)
            h41 = boot_ci(gate, free, tids, rng)       # gate - free  (expect >0)
            h42 = boot_ci(free, inv, tids, rng)        # free - inverted (manip drop, expect >0)
            h43 = boot_ci(con, free, tids, rng)        # constrained - free
            hconf = boot_ci(conf, free, tids, rng)     # conformal - free
            # adversarial per corruption shape: blind gate on corrupted risk vs LLM seeing corrupted card + raw signal
            adv = {}
            for shape, arm in ADV.items():
                cr = corrupted_risk[shape]
                g_c = {t: net_of_action(gate_action(cr[t], lam), tc[t], tmpl[t], lam) for t in tids}
                l_c = {t: mean_net_llm(A, arm, t, tc[t], tmpl[t], lam) for t in tids}
                ci = boot_ci(l_c, g_c, tids, rng)      # LLM_corrupted - gate_corrupted (expect <=0)
                adv[shape] = {"gate_corrupted": mean(g_c), "llm_corrupted_plus_raw": mean(l_c),
                              "d": round(mean(l_c) - mean(g_c), 4), "ci": ci[:2], "p": ci[2], "LLM_recovers": ci[0] > 0}
            pvals = {"H4.2_manip": h42[2], "H4.3_constrained": h43[2], "conformal_vs_free": hconf[2]}
            pvals.update({f"H4.4_adv_{s}": adv[s]["p"] for s in adv})
            pm[m] = {
                "net": {"free_form": mean(free), "calibrated_gate": mean(gate), "constrained": mean(con),
                        "conformal": mean(conf), "trust_all": mean(trust_all), "verify_all": mean(verify_all),
                        "default_all": mean(default_all), "inverted": mean(inv)},
                "H4.1_gate_minus_free": {"d": round(mean(gate) - mean(free), 4), "ci": h41[:2], "p": h41[2]},
                "H4.2_manip_drop": {"d": round(mean(free) - mean(inv), 4), "ci": h42[:2], "p": h42[2]},
                "H4.3_constrained_minus_free": {"d": round(mean(con) - mean(free), 4), "ci": h43[:2], "p": h43[2]},
                "conformal_minus_free": {"d": round(mean(conf) - mean(free), 4), "ci": hconf[:2], "p": hconf[2],
                                          "realized_false_accept": round(realized_fa, 4)},
                "H4.4_adversarial_by_shape": adv,
                "holm_secondary": holm(pvals),
            }
        report["by_lambda"][str(lam)] = pm

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    json.dump(report, open(args.out, "w"), indent=2)
    # console summary
    print(f"=== Phase 4 confirmatory (N={report['n']}, CRC alpha={args.crc_alpha} tau_hat={report['crc_tau_hat']}"
          f"{' IN-SAMPLE' if crc_insample else ''}) ===")
    for lam in lambdas:
        print(f"\n--- lambda={lam} ---")
        for m in models:
            d = report["by_lambda"][str(lam)][m]; n = d["net"]
            print(f"  {m}: free={n['free_form']:+.3f} gate={n['calibrated_gate']:+.3f} constr={n['constrained']:+.3f} conf={n['conformal']:+.3f}")
            print(f"    H4.1 gate-free={d['H4.1_gate_minus_free']['d']:+.3f} CI{d['H4.1_gate_minus_free']['ci']} p={d['H4.1_gate_minus_free']['p']}"
                  f" | H4.3 constr-free={d['H4.3_constrained_minus_free']['d']:+.3f} CI{d['H4.3_constrained_minus_free']['ci']}")
            print(f"    conformal-free={d['conformal_minus_free']['d']:+.3f} CI{d['conformal_minus_free']['ci']} realizedFA={d['conformal_minus_free']['realized_false_accept']}")
            for s, a in d["H4.4_adversarial_by_shape"].items():
                print(f"    H4.4 adv[{s}] LLM-gate={a['d']:+.3f} CI{a['ci']} {'RECOVERS' if a['LLM_recovers'] else 'no-recovery'}")


if __name__ == "__main__":
    main()
