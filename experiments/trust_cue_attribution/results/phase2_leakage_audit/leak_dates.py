#!/usr/bin/env python3
"""Phase 2 leakage audit: for each of the 80 v1 targets, find the max sequence
identity to a PRE-CUTOFF PDB homolog (date < cutoff) -- the real training-leakage
signal that a release-date filter alone cannot catch. RCSB release dates via GraphQL."""
import json, collections, urllib.request, time

tgt = [json.loads(l) for l in open("<WORK_DIR>/targets.jsonl")]
selfpdb = {t["target_id"]: t["pdb_id"].lower() for t in tgt}
regime = {t["target_id"]: t["regime"] for t in tgt}

# per-target non-self hits (pident>=30, qcov>=0.8), keep top by identity
hits = collections.defaultdict(list)
for line in open("<WORK_DIR>/results.m8"):
    q, hit, pid, aln, qcov, tcov, ev, bits = line.rstrip("\n").split("\t")
    tid = q.split("|")[0]; hitpdb = hit.split("_")[0].lower()
    pid = float(pid); qcov = float(qcov)
    if hitpdb == selfpdb.get(tid) or qcov < 0.8 or pid < 30: continue
    hits[tid].append((pid, hitpdb))

# unique hit pdb ids (cap top-25 per target by identity to bound lookups)
need = set()
for tid in hits:
    hits[tid] = sorted(set(hits[tid]), key=lambda x: -x[0])[:25]
    need.update(h[1] for h in hits[tid])
need = sorted(need)
print(f"unique homolog PDB ids to date-look-up: {len(need)}")

# batch RCSB GraphQL for initial_release_date
dates = {}
def fetch(ids):
    q = '{entries(entry_ids:[%s]){rcsb_id rcsb_accession_info{initial_release_date}}}' % ",".join('"%s"' % i.upper() for i in ids)
    req = urllib.request.Request("https://data.rcsb.org/graphql",
                                 data=json.dumps({"query": q}).encode(),
                                 headers={"Content-Type": "application/json"})
    d = json.load(urllib.request.urlopen(req, timeout=60))
    for e in d["data"]["entries"]:
        ai = e.get("rcsb_accession_info") or {}
        dates[e["rcsb_id"].lower()] = (ai.get("initial_release_date") or "")[:10]

for i in range(0, len(need), 150):
    fetch(need[i:i+150]); time.sleep(0.3)
print(f"dates resolved: {sum(1 for v in dates.values() if v)}/{len(need)}")

# per-target max identity to a pre-cutoff homolog, at several cutoffs
CUTOFFS = ["2021-09-30", "2023-01-01", "2024-01-01", "2025-01-01"]
out = {"n_targets": len(selfpdb), "cutoffs": {}, "per_target": {}}
for tid in sorted(selfpdb):
    rows = [(pid, hp, dates.get(hp, "")) for pid, hp in hits.get(tid, [])]
    out["per_target"][tid] = {"regime": regime[tid],
        "max_identity_any": round(max([r[0] for r in rows], default=0.0), 1),
        "best_precutoff": {}}
for cut in CUTOFFS:
    n30 = n50 = n90 = 0
    for tid in sorted(selfpdb):
        rows = [(pid, hp, dates.get(hp, "")) for pid, hp in hits.get(tid, [])]
        pre = [r for r in rows if r[2] and r[2] < cut]
        mx = max([r[0] for r in pre], default=0.0)
        out["per_target"][tid]["best_precutoff"][cut] = round(mx, 1)
        n30 += mx >= 30; n50 += mx >= 50; n90 += mx >= 90
    out["cutoffs"][cut] = {"targets_with_precutoff_homolog_ge30pct": n30,
                           "ge50pct": n50, "ge90pct": n90}
    print(f"cutoff {cut}:  >=30% {n30}/80   >=50% {n50}/80   >=90% {n90}/80")

json.dump(out, open("<WORK_DIR>/leakage_audit.json", "w"), indent=2)
print("\nworst pre-cutoff (cutoff 2024-01-01) examples:")
ranked = sorted(selfpdb, key=lambda t: -out["per_target"][t]["best_precutoff"]["2024-01-01"])
for t in ranked[:12]:
    pt = out["per_target"][t]
    print(f"  {t} ({pt['regime']:7s}) pre-cutoff_max={pt['best_precutoff']['2024-01-01']:.1f}%  any={pt['max_identity_any']:.1f}%")
