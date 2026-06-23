#!/usr/bin/env python3
"""Validate the v1 home-grown all-chain CA-lDDT (complex truth) against gold-standard
DockQ, on the 40 v1 complex targets. Tests the hyper-review's #1 finding: is the
pLDDT->complex "calibration collapse" (Pearson 0.16) real, or a CA-lDDT artifact?"""
import json, subprocess, glob, os, re, math

P2 = "/scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution/hpc_outputs/phase2_targets"
DOCKQ = "/scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution/hpc_outputs/envs/dockq-conda/bin/DockQ"

recs = {r["target_id"]: r for r in (json.loads(l) for l in open(P2 + "/records.jsonl") if l.strip())}
complexes = sorted(t for t, r in recs.items() if r["regime"] == "complex")

def parse(txt):
    m = re.search(r"Total DockQ over \d+ native interfaces:\s*([0-9.]+)", txt)
    if m:
        dq = float(m.group(1))
    else:
        m1 = re.search(r"^DockQ ([0-9.]+)", txt, re.M)
        if not m1:
            return None
        dq = float(m1.group(1))
    irs = [float(x) for x in re.findall(r"iRMSD ([0-9.]+)", txt)]
    lrs = [float(x) for x in re.findall(r"LRMSD ([0-9.]+)", txt)]
    fns = [float(x) for x in re.findall(r"fnat ([0-9.]+)", txt)]
    avg = lambda v: round(sum(v) / len(v), 4) if v else None
    return {"dockq": dq, "irmsd": avg(irs), "lrmsd": avg(lrs), "fnat": avg(fns), "n_interfaces": len(irs)}

out = []
for t in complexes:
    pred = glob.glob(f"{P2}/predictions/{t}/boltz_results_{t}/predictions/{t}/{t}_model_0.cif")
    ref = f"{P2}/reference/{t}.cif"
    if not pred or not os.path.exists(ref):
        out.append({"target_id": t, "error": "missing_structure"}); continue
    try:
        res = subprocess.run([DOCKQ, pred[0], ref, "--short"], capture_output=True, text=True, timeout=900)
        p = parse(res.stdout)
        if p is None:
            out.append({"target_id": t, "error": "parse_failed", "stderr": res.stderr[-200:]}); continue
        r = recs[t]
        out.append({"target_id": t, **p, "mean_plddt": r["mean_plddt"], "iptm": r.get("iptm"),
                    "home_grown_ca_lddt": r["truth"]["quality"]})
        print(f"{t}: DockQ={p['dockq']:.3f}  pLDDT={r['mean_plddt']:.1f}  ipTM={r.get('iptm')}  CA-lDDT(v1)={r['truth']['quality']:.3f}", flush=True)
    except Exception as e:
        out.append({"target_id": t, "error": repr(e)})

json.dump(out, open(P2 + "/dockq_validation.json", "w"), indent=2)

def pearson(xs, ys):
    n = len(xs)
    if n < 3: return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs)); sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (sx * sy) if sx > 0 and sy > 0 else float("nan")

ok = [o for o in out if "dockq" in o]
print("\n===== DockQ VALIDATION (v1 complexes) =====")
print(f"scored {len(ok)}/{len(complexes)} complexes; errors {len(out) - len(ok)}")
if len(ok) >= 3:
    dq = [o["dockq"] for o in ok]; pl = [o["mean_plddt"] for o in ok]; ca = [o["home_grown_ca_lddt"] for o in ok]
    iptm_rows = [o for o in ok if o["iptm"] is not None]
    print(f"Pearson(pLDDT,     DockQ)        = {pearson(pl, dq):+.4f}   <- report claimed pLDDT vs complex-CA-lDDT = 0.16")
    print(f"Pearson(CA-lDDT v1, DockQ)       = {pearson(ca, dq):+.4f}   <- agreement of the home-grown truth with gold-standard")
    print(f"Pearson(pLDDT,     CA-lDDT v1)   = {pearson(pl, ca):+.4f}   <- the v1 complex 'calibration gap' number")
    if iptm_rows:
        print(f"Pearson(ipTM,      DockQ)        = {pearson([o['iptm'] for o in iptm_rows], [o['dockq'] for o in iptm_rows]):+.4f}   (n={len(iptm_rows)})  <- proper interface confidence")
    import statistics
    print(f"DockQ distribution: median={statistics.median(dq):.3f} min={min(dq):.3f} max={max(dq):.3f}")
    print(f"DockQ>=0.23 'acceptable': {sum(1 for x in dq if x>=0.23)}/{len(dq)};  >=0.49 'medium': {sum(1 for x in dq if x>=0.49)}/{len(dq)}")
