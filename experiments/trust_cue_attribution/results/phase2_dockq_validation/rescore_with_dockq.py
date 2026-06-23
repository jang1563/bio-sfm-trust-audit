#!/usr/bin/env python3
"""Re-score the v1 Phase-2 LLM routing episodes with DockQ-validated COMPLEX truth
(monomers unchanged) to test whether the headline contrasts survive the corrected
metric. Same model decisions; only the reward truth for complexes changes."""
import json, sys, math
sys.path.insert(0, "experiments/trust_cue_attribution")
from phase2_score_episodes import episode_action, outcome, ARMS

REC = "<EPISODES_DIR>/records.jsonl"
DOCKQ = "experiments/trust_cue_attribution/results/phase2_dockq_validation/dockq_validation.json"
EPS = {"Sonnet 4.6": "<EPISODES_DIR>/episodes_sonnet.jsonl", "Opus 4.8": "<EPISODES_DIR>/episodes_opus.jsonl"}

recs = {r["target_id"]: r for r in (json.loads(l) for l in open(REC) if l.strip())}
dq = {o["target_id"]: o["dockq"] for o in json.load(open(DOCKQ)) if "dockq" in o}
LAM, MONO = 0.5, 0.9

def correct(tid, mode, dthr):
    r = recs[tid]
    if r["regime"] == "monomer":
        return r["truth"]["quality"] >= MONO
    if mode == "orig":
        return r["truth"]["quality"] >= MONO          # v1: all-chain CA-lDDT
    return dq.get(tid, 0.0) >= dthr                    # corrected: DockQ

def score(path, mode, dthr):
    arm_net = {a: [] for a in ARMS}
    for ep in (json.loads(l) for l in open(path) if l.strip()):
        pid = ep.get("packet_id", ""); tid = pid.split("::")[0]
        arm = ep.get("cue_condition") or (pid.split("::")[1] if "::" in pid else "?")
        if tid not in recs or arm not in arm_net: continue
        c, a = outcome(episode_action(ep), correct(tid, mode, dthr),
                       bool(recs[tid].get("template_baseline_correct", False)), LAM)
        arm_net[arm].append(c - LAM * a)
    return {a: (round(sum(v) / len(v), 3) if v else None) for a, v in arm_net.items()}

for thr in (0.23, 0.49):
    print(f"\n############ DockQ 'correct' threshold = {thr} ############")
    for model, path in EPS.items():
        o = score(path, "orig", thr); d = score(path, "dockq", thr)
        print(f"\n=== {model}: net/target per arm   (orig CA-lDDT  ->  DockQ-corrected) ===")
        for a in ARMS:
            print(f"  {a:42s} {o[a]:+.3f} -> {d[a]:+.3f}")
        ci_raw_o = o["calibrated_interface_shown"] - o["raw_plddt_shown"]
        ci_raw_d = d["calibrated_interface_shown"] - d["raw_plddt_shown"]
        print(f"  >>> interface - raw_plddt:   orig {ci_raw_o:+.3f}   ->   DockQ {ci_raw_d:+.3f}")
