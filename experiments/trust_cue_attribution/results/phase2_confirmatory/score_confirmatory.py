#!/usr/bin/env python3
"""Score the pre-registered confirmatory pilot: seed-aggregated, lambda-sweep, paired
target-bootstrap 95% CIs, Holm-Bonferroni over the secondary family, H2 (calibrated
interface vs raw) as the SINGLE confirmatory primary."""
import sys, json, glob, random
sys.path.insert(0, "experiments/trust_cue_attribution")
from phase2_score_episodes import episode_action, outcome

recs = {r["target_id"]: r for r in (json.loads(l) for l in open("<WORK_DIR>/cxredo_records.jsonl") if l.strip()) if r["truth"]["quality"] is not None}
ARMS = ["no_signal", "raw_plddt_shown", "calibrated_risk_shown_no_recommendation",
        "calibrated_interface_shown", "inverted_reliability_interface_control", "competing_cue"]
MODELS = ["claude-sonnet-4-6", "gpt-4.1", "claude-opus-4-8"]
CUT = 0.49; tids = list(recs); rng = random.Random(13)

def load(model):
    eps = {}
    for f in sorted(glob.glob(f"<WORK_DIR>/conf_{model}_seed*.jsonl")):
        for l in open(f):
            if not l.strip(): continue
            ep = json.loads(l); pid = ep["packet_id"]; tid = pid.split("::")[0]
            arm = ep.get("cue_condition") or pid.split("::")[1]
            eps.setdefault((tid, arm), []).append(episode_action(ep))
    return eps

def net_per_target(eps, arm, lam):
    """seed-averaged net per target for one arm"""
    out = {}
    for t in tids:
        acts = eps.get((t, arm), ["defer"])
        nets = [(lambda c, k: c - lam * k)(*outcome(a, recs[t]["truth"]["quality"] >= CUT, False, lam)) for a in acts]
        out[t] = sum(nets) / len(nets)
    return out

def boot_ci_p(d1, d2):
    diffs = []
    for _ in range(4000):
        s = [rng.choice(tids) for _ in tids]
        diffs.append(sum(d1[t] - d2[t] for t in s) / len(s))
    diffs.sort(); lo, hi = diffs[100], diffs[3900]
    below = sum(1 for x in diffs if x < 0) / len(diffs)
    p = 2 * min(below, 1 - below)
    return round(lo, 3), round(hi, 3), round(p, 4)

report = {"n": len(recs), "cut_dockq": CUT, "models": MODELS, "primary": "calibrated_interface_shown vs raw_plddt_shown (H2)", "by_lambda": {}}
for lam in (0.2, 0.5, 0.8):
    lamrep = {"per_model": {}}
    for m in MODELS:
        eps = load(m)
        nets = {a: net_per_target(eps, a, lam) for a in ARMS}
        meanf = lambda a: round(sum(nets[a].values()) / len(tids), 3)
        contrasts = {}
        # primary
        lo, hi, p = boot_ci_p(nets["calibrated_interface_shown"], nets["raw_plddt_shown"])
        contrasts["H2_interface_minus_raw"] = {"delta": round(meanf("calibrated_interface_shown") - meanf("raw_plddt_shown"), 3), "ci": [lo, hi], "p": p, "sig": (lo > 0 or hi < 0)}
        # secondary family
        for label, a, b in [("H1_raw_minus_no_signal", "raw_plddt_shown", "no_signal"),
                            ("A4_interface_minus_norec", "calibrated_interface_shown", "calibrated_risk_shown_no_recommendation"),
                            ("inverted_minus_calibrated", "inverted_reliability_interface_control", "calibrated_interface_shown"),
                            ("competing_minus_raw", "competing_cue", "raw_plddt_shown"),
                            ("calibrated_minus_no_signal", "calibrated_interface_shown", "no_signal")]:
            lo, hi, p = boot_ci_p(nets[a], nets[b])
            contrasts[label] = {"delta": round(meanf(a) - meanf(b), 3), "ci": [lo, hi], "p": p}
        lamrep["per_model"][m] = {"arm_net": {a: meanf(a) for a in ARMS}, "contrasts": contrasts}
    report["by_lambda"][str(lam)] = lamrep

# Holm-Bonferroni over the secondary family (pooled across models x lambda), excluding the primary
sec = []
for lam, lr in report["by_lambda"].items():
    for m, mr in lr["per_model"].items():
        for label, c in mr["contrasts"].items():
            if label == "H2_interface_minus_raw": continue
            sec.append((f"{label}|{m}|lam{lam}", c["p"]))
sec.sort(key=lambda x: x[1]); K = len(sec)
holm = {}
for i, (name, p) in enumerate(sec):
    holm[name] = {"p": p, "p_holm": round(min(1.0, p * (K - i)), 4), "sig_holm": p * (K - i) < 0.05}
report["secondary_family_holm_bonferroni"] = {"n_tests": K, "n_sig_after_holm": sum(1 for v in holm.values() if v["sig_holm"])}

json.dump(report, open("<WORK_DIR>/confirmatory_scores.json", "w"), indent=2)

# readable
print(f"=== PRE-REGISTERED CONFIRMATORY (n={len(recs)}, held-out calibration, 6 arms, seeds) ===")
for lam in ("0.5", "0.2", "0.8"):
    print(f"\n--- lambda={lam} ---")
    for m in MODELS:
        h2 = report["by_lambda"][lam]["per_model"][m]["contrasts"]["H2_interface_minus_raw"]
        h1 = report["by_lambda"][lam]["per_model"][m]["contrasts"]["H1_raw_minus_no_signal"]
        print(f"  {m:20s} H2 interface-raw={h2['delta']:+.3f} CI{h2['ci']} p={h2['p']} {'**SIG**' if h2['sig'] else 'ns'}   |  H1 raw-no_signal={h1['delta']:+.3f} CI{h1['ci']} p={h1['p']}")
print(f"\nHolm-Bonferroni secondary family: {report['secondary_family_holm_bonferroni']['n_sig_after_holm']}/{report['secondary_family_holm_bonferroni']['n_tests']} significant after correction")
