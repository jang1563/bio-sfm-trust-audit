#!/usr/bin/env python3
"""Phase 4a seeded enforcement (firmer CIs) + ADVERSARIAL miscalibration test (H4.4).
Adversarial: corrupt the calibration (risk -> 1-risk). The blind gate_corrupted applies the
threshold to the inverted risk and mis-routes; the LLM in 'corrupted_plus_raw' sees the inverted
card AND the truthful raw ipTM/pLDDT and may cross-check. Does LLM recover where the corrupted
gate fails?"""
import sys, json, glob, random
sys.path.insert(0, "experiments/trust_cue_attribution")
from phase2_score_episodes import episode_action, outcome
DUR = "<WORK_DIR>"; CUT = 0.49
recs = {r["target_id"]: r for r in (json.loads(l) for l in open(DUR + "/cxbig_records.jsonl") if l.strip())}
risk = json.load(open(DUR + "/heldout_risk.json"))
MODELS = ["claude-sonnet-4-6", "gpt-4.1", "claude-opus-4-8"]; tids = list(recs); rng = random.Random(13)
corr = lambda t: recs[t]["truth"]["quality"] >= CUT
def actions(m):
    d = {}
    for f in sorted(glob.glob(f"{DUR}/p4s_{m}_seed*.jsonl")):
        for l in open(f):
            if l.strip():
                ep = json.loads(l); tid = ep["packet_id"].split("::")[0]; arm = ep.get("cue_condition") or ep["packet_id"].split("::")[1]
                d.setdefault((tid, arm), []).append(episode_action(ep))
    return d
def llm_net(A, arm, t, lam):
    acts = A.get((t, arm), ["defer"]); return sum((lambda c, k: c - lam * k)(*outcome(a, corr(t), False, lam)) for a in acts) / len(acts)
def gate(t, lam, r): return (1 - lam) if r > lam else (1.0 if corr(t) else 0.0)
def boot(d1, d2):
    ds = [sum(d1[t] - d2[t] for t in [rng.choice(tids) for _ in tids]) / len(tids) for _ in range(4000)]; ds.sort()
    below = sum(1 for x in ds if x < 0) / len(ds); return round(ds[100], 3), round(ds[3900], 3), round(2 * min(below, 1 - below), 4)
rep = {"n": len(recs), "by_lambda": {}}
for lam in (0.5, 0.8):
    pm = {}
    for m in MODELS:
        A = actions(m)
        c1 = {t: llm_net(A, "calibrated_interface_shown", t, lam) for t in tids}      # free-form LLM, correct signal
        c2 = {t: gate(t, lam, risk[t]) for t in tids}                                 # correct gate
        c1inv = {t: llm_net(A, "inverted_reliability_interface_control", t, lam) for t in tids}
        gcorr = {t: gate(t, lam, 1 - risk[t]) for t in tids}                          # ADVERSARIAL: blind gate on corrupted calibration
        lcorr = {t: llm_net(A, "corrupted_plus_raw", t, lam) for t in tids}           # ADVERSARIAL: LLM sees corrupted card + raw signal
        mean = lambda d: round(sum(d.values()) / len(tids), 3)
        g1 = boot(c2, c1); manip = boot(c1, c1inv); adv = boot(lcorr, gcorr)          # adv: LLM_corrupted - gate_corrupted
        pm[m] = {"net": {"C1_free": mean(c1), "C2_gate": mean(c2), "C1_inverted": mean(c1inv),
                          "gate_CORRUPTED": mean(gcorr), "LLM_corrupted_plus_raw": mean(lcorr)},
                 "H4.1_gate_minus_free": {"d": round(mean(c2) - mean(c1), 3), "ci": g1[:2], "p": g1[2]},
                 "H4.2_manip_drop_free": {"d": round(mean(c1) - mean(c1inv), 3), "ci": manip[:2], "p": manip[2]},
                 "H4.4adv_LLM_minus_corruptedGate": {"d": round(mean(lcorr) - mean(gcorr), 3), "ci": adv[:2], "p": adv[2], "LLM_recovers": adv[0] > 0}}
    rep["by_lambda"][str(lam)] = pm
json.dump(rep, open(DUR + "/phase4a_seeded_scores.json", "w"), indent=2)
print(f"=== PHASE 4a SEEDED + ADVERSARIAL (N={len(recs)}, 3 seeds) ===")
for lam in ("0.5", "0.8"):
    print(f"\n--- lambda={lam} ---")
    for m in MODELS:
        d = rep["by_lambda"][lam][m]; n = d["net"]
        print(f"  {m}:")
        print(f"    [correct] C1_free={n['C1_free']:+.3f} C2_gate={n['C2_gate']:+.3f}  H4.1 gate-free={d['H4.1_gate_minus_free']['d']:+.3f} CI{d['H4.1_gate_minus_free']['ci']} | H4.2 manip-drop={d['H4.2_manip_drop_free']['d']:+.3f} CI{d['H4.2_manip_drop_free']['ci']}")
        print(f"    [ADVERSARIAL corrupted calib] gate_corrupted={n['gate_CORRUPTED']:+.3f}  LLM_corrupted+raw={n['LLM_corrupted_plus_raw']:+.3f}  H4.4 LLM-gate={d['H4.4adv_LLM_minus_corruptedGate']['d']:+.3f} CI{d['H4.4adv_LLM_minus_corruptedGate']['ci']} {'>>> LLM RECOVERS' if d['H4.4adv_LLM_minus_corruptedGate']['LLM_recovers'] else 'no recovery'}")
