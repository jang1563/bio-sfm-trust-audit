#!/usr/bin/env python3
"""Validate the v1 home-grown CA-lDDT (monomer truth) against OpenStructure lDDT,
on the 40 v1 monomer targets. Tests whether the report's pLDDT->lDDT 0.89 (monomers)
holds against a gold-standard lDDT, and how well the home-grown metric agrees."""
import json, subprocess, glob, os, math, statistics, tempfile

P2 = "/scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution/hpc_outputs/phase2_targets"
OST = "/scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution/hpc_outputs/envs/ost-conda/bin/ost"

recs = {r["target_id"]: r for r in (json.loads(l) for l in open(P2 + "/records.jsonl") if l.strip())}
monomers = sorted(t for t, r in recs.items() if r["regime"] == "monomer")

def ost_lddt(model, ref):
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        out = tf.name
    try:
        subprocess.run([OST, "compare-structures", "-m", model, "-r", ref, "--lddt", "-o", out],
                       capture_output=True, text=True, timeout=900)
        d = json.load(open(out))
        return d.get("lddt")
    finally:
        if os.path.exists(out): os.remove(out)

rows = []
for t in monomers:
    pred = glob.glob(f"{P2}/predictions/{t}/boltz_results_{t}/predictions/{t}/{t}_model_0.cif")
    ref = f"{P2}/reference/{t}.cif"
    if not pred or not os.path.exists(ref):
        rows.append({"target_id": t, "error": "missing"}); continue
    try:
        l = ost_lddt(pred[0], ref)
        if l is None:
            rows.append({"target_id": t, "error": "no_lddt"}); continue
        r = recs[t]
        rows.append({"target_id": t, "ost_lddt": round(float(l), 4),
                     "home_grown_ca_lddt": r["truth"]["quality"], "mean_plddt": r["mean_plddt"]})
        print(f"{t}: OST-lDDT={l:.3f}  CA-lDDT(v1)={r['truth']['quality']:.3f}  pLDDT={r['mean_plddt']:.1f}", flush=True)
    except Exception as e:
        rows.append({"target_id": t, "error": repr(e)})

json.dump(rows, open(P2 + "/ost_validation.json", "w"), indent=2)

def pear(xs, ys):
    n = len(xs)
    if n < 3: return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs)); sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (sx * sy) if sx > 0 and sy > 0 else float("nan")

ok = [r for r in rows if "ost_lddt" in r]
print(f"\n===== OST monomer lDDT validation: {len(ok)}/{len(monomers)} =====")
if len(ok) >= 3:
    ost = [r["ost_lddt"] for r in ok]; ca = [r["home_grown_ca_lddt"] for r in ok]; pl = [r["mean_plddt"] for r in ok]
    print(f"Pearson(CA-lDDT v1, OST-lDDT) = {pear(ca, ost):+.4f}   <- agreement of home-grown monomer truth with gold standard")
    print(f"Pearson(pLDDT,     OST-lDDT) = {pear(pl, ost):+.4f}   <- TRUE monomer calibration (report claimed pLDDT vs CA-lDDT = 0.89)")
    print(f"Pearson(pLDDT,     CA-lDDT)  = {pear(pl, ca):+.4f}   <- the v1 monomer number")
    print(f"mean |OST - CA-lDDT| = {statistics.mean(abs(a-b) for a,b in zip(ost,ca)):.4f}")
