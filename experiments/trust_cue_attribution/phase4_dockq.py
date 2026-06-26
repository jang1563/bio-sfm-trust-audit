#!/usr/bin/env python3
"""Phase 4 DockQ truth + record assembly for the confirmatory substrate.

Runs gold-standard DockQ (same parser as the v1 dockq-validation) on each Boltz
prediction vs its experimental reference, then writes the truth table and assembles
records via the shared phase2_records protocol.

default_baseline / template_baseline_correct (task 4, realistic): a homology-template
model is only buildable from a PRE-CUTOFF structure (what is knowable at the specialist's
training time). On the leakage-clean substrate, no target has a usable pre-cutoff template
(>= IDENT_TMPL_PRECUT identity, by the leakage-clean construction), so default_baseline is
a real, selectable action that scores correct for ~0 targets -- the honest consequence that
a homology fallback cannot rescue routing on genuinely novel complexes.
"""
import argparse, glob, json, os, re, subprocess, sys

CUT = 0.49
IDENT_TMPL_PRECUT = 50.0   # a pre-cutoff homolog this strong would give a usable template


def parse_dockq(txt):
    m = re.search(r"Total DockQ over \d+ native interfaces:\s*([0-9.]+)", txt)
    if m:
        dq = float(m.group(1))
    else:
        m1 = re.search(r"^DockQ ([0-9.]+)", txt, re.M)
        if not m1:
            return None
        dq = float(m1.group(1))
    irs = [float(x) for x in re.findall(r"iRMSD ([0-9.]+)", txt)]
    fns = [float(x) for x in re.findall(r"fnat ([0-9.]+)", txt)]
    return {"dockq": dq, "irmsd": round(sum(irs) / len(irs), 4) if irs else None,
            "fnat": round(sum(fns) / len(fns), 4) if fns else None, "n_interfaces": len(irs)}


def find_pred_cif(pred_dir, tid):
    hits = glob.glob(os.path.join(pred_dir, tid, "**", f"{tid}_model_0.cif"), recursive=True)
    return sorted(hits)[0] if hits else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set-dir", required=True)         # predict_set (has predictions/, reference/, targets.jsonl)
    ap.add_argument("--leakage", required=True)         # leakage_result.jsonl (for template_baseline_correct)
    ap.add_argument("--dockq-bin", default=os.path.expanduser("~/.conda/envs/boltz/bin/DockQ"))
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    pred_dir = os.path.join(args.set_dir, "predictions")
    ref_dir = os.path.join(args.set_dir, "reference")
    targets = [json.loads(l) for l in open(os.path.join(args.set_dir, "targets.jsonl")) if l.strip()]
    leak = {r["target_id"]: r for r in (json.loads(l) for l in open(args.leakage))}

    detail, truth, skipped = [], [], []
    for t in targets:
        tid = t["target_id"]
        pred = find_pred_cif(pred_dir, tid)
        ref = os.path.join(ref_dir, f"{tid}.cif")
        if not pred or not os.path.exists(ref):
            skipped.append(f"{tid}: missing_structure (pred={bool(pred)})"); continue
        try:
            res = subprocess.run([args.dockq_bin, pred, ref, "--short"],
                                 capture_output=True, text=True, timeout=1200)
            p = parse_dockq(res.stdout)
        except Exception as e:
            skipped.append(f"{tid}: dockq_error {e}"); continue
        if p is None:
            skipped.append(f"{tid}: dockq_parse_failed :: {res.stderr[-160:]}"); continue
        lk = leak.get(tid, {})
        tmpl_ok = float(lk.get("max_precutoff_ident", 0.0)) >= IDENT_TMPL_PRECUT  # ~all False on clean set
        detail.append({"target_id": tid, **p})
        truth.append({"target_id": tid, "correct": p["dockq"] >= CUT, "quality": round(p["dockq"], 6),
                      "template_baseline_correct": tmpl_ok})
        print(f"{tid}: DockQ={p['dockq']:.3f} ({'OK' if p['dockq']>=CUT else 'fail'}) interfaces={p['n_interfaces']}", flush=True)

    json.dump(detail, open(os.path.join(args.out_dir, "dockq_detail.json"), "w"), indent=2)
    with open(os.path.join(args.out_dir, "truth.jsonl"), "w") as fh:
        for r in truth:
            fh.write(json.dumps(r) + "\n")
    dq = [d["dockq"] for d in detail]
    summary = {"scored": len(detail), "skipped": len(skipped),
               "base_rate_ge_0.23": f"{sum(1 for x in dq if x>=0.23)}/{len(dq)}",
               "base_rate_ge_0.49": f"{sum(1 for x in dq if x>=0.49)}/{len(dq)}",
               "base_rate_ge_0.80": f"{sum(1 for x in dq if x>=0.80)}/{len(dq)}",
               "template_correct_count": sum(1 for r in truth if r["template_baseline_correct"]),
               "dockq_range": [round(min(dq), 3), round(max(dq), 3)] if dq else None}
    json.dump(summary, open(os.path.join(args.out_dir, "dockq_summary.json"), "w"), indent=2)
    print(json.dumps(summary, indent=2))
    if skipped:
        print(f"skipped {len(skipped)}:")
        for s in skipped[:20]:
            print("  -", s)


if __name__ == "__main__":
    main()
