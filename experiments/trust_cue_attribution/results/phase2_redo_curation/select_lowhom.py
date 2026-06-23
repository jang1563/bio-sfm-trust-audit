#!/usr/bin/env python3
"""D step 3: select genuinely low-homology candidates. A candidate is LEAKY if it has
any non-self PDB homolog with >=30% identity over >=50% coverage that was released
before the cutoff (could be in Boltz-2 training). Keep candidates with NO such homolog."""
import json, collections, urllib.request, time, sys

WORK = sys.argv[1] if len(sys.argv) > 1 else "<WORK_DIR>"
CUTOFF = "2025-07-01"
ID_THR, QCOV_THR = 30.0, 0.5
N_PER_REGIME = 20

meta = json.load(open(WORK + "/candidates_meta.json"))
selfpdb = {tid: tid for tid in meta}  # candidate tid == its own pdb id (lowercase)

# qualifying non-self hits per candidate (cap top-20 by identity)
hits = collections.defaultdict(list)
for line in open(WORK + "/cand_results.m8"):
    q, hit, pid, aln, qcov, tcov, ev, bits = line.rstrip("\n").split("\t")
    tid = q.split("|")[0]; hitpdb = hit.split("_")[0].lower()
    pid = float(pid); qcov = float(qcov)
    if tid not in meta or hitpdb == tid or pid < ID_THR or qcov < QCOV_THR:
        continue
    hits[tid].append((pid, hitpdb))
for tid in hits:
    hits[tid] = sorted(set(hits[tid]), key=lambda x: -x[0])[:20]

need = sorted({h[1] for v in hits.values() for h in v})
print(f"candidates with any >=30%/qcov0.5 non-self hit: {len(hits)}/{len(meta)}; unique homolog ids to date-check: {len(need)}", flush=True)

dates = {}
def fetch(ids):
    q = '{entries(entry_ids:[%s]){rcsb_id rcsb_accession_info{initial_release_date}}}' % ",".join('"%s"' % i.upper() for i in ids)
    req = urllib.request.Request("https://data.rcsb.org/graphql", data=json.dumps({"query": q}).encode(),
                                 headers={"Content-Type": "application/json"})
    for e in json.load(urllib.request.urlopen(req, timeout=90))["data"]["entries"]:
        ai = e.get("rcsb_accession_info") or {}
        dates[e["rcsb_id"].lower()] = (ai.get("initial_release_date") or "")[:10]
for i in range(0, len(need), 150):
    fetch(need[i:i+150]); time.sleep(0.25)
print(f"dates resolved: {sum(1 for v in dates.values() if v)}/{len(need)}", flush=True)

# classify: leaky if a qualifying hit is pre-cutoff
rows = []
for tid, m in meta.items():
    pre = [(pid, hp, dates.get(hp, "")) for pid, hp in hits.get(tid, []) if dates.get(hp, "") and dates[hp] < CUTOFF]
    max_pre = max([p[0] for p in pre], default=0.0)
    rows.append({"target_id": tid, **m, "max_precutoff_identity": round(max_pre, 1),
                 "leaky": max_pre >= ID_THR})
clean = [r for r in rows if not r["leaky"]]
print(f"\nLOW-HOMOLOGY (clean) candidates: {len(clean)}/{len(meta)}  "
      f"({sum(1 for r in clean if r['regime']=='monomer')} mono, {sum(1 for r in clean if r['regime']=='complex')} complex)")

# select balanced, prefer lowest homology then shorter (cheaper Boltz)
sel = []
for regime in ("monomer", "complex"):
    pool = sorted([r for r in clean if r["regime"] == regime],
                  key=lambda r: (r["max_precutoff_identity"], r["total_len"]))
    sel += pool[:N_PER_REGIME]
json.dump({"cutoff": CUTOFF, "id_thr": ID_THR, "qcov_thr": QCOV_THR,
           "n_candidates": len(meta), "n_clean": len(clean), "selected": sel,
           "all_classified": rows}, open(WORK + "/lowhom_selection.json", "w"), indent=2)
print(f"\nSELECTED {len(sel)} targets ({sum(1 for r in sel if r['regime']=='monomer')} mono, "
      f"{sum(1 for r in sel if r['regime']=='complex')} complex):")
for r in sel:
    print(f"  {r['target_id']} {r['regime']:7s} chains={r['n_protein_chains']} len={r['total_len']:4d} max_precutoff_id={r['max_precutoff_identity']:.0f}%")
