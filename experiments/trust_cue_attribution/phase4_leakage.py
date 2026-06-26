"""Phase 4 leakage screen + clean selection (runs on Cayuga; needs RCSB GraphQL net).

Given mmseqs easy-search hits of the candidate chains vs the full PDB (pdb_seqres),
classify each candidate target as leakage-CLEAN iff it has NO pre-cutoff PDB homolog
at >= IDENT_LEAK identity and >= QCOV_LEAK coverage. Pre-cutoff = homolog's RCSB
initial_release_date < CUTOFF (Boltz-2 structure cutoff ~2023-06-01).

Also computes, per target, template_baseline_correct = a homology-template model is
available = best homolog (ANY date) with identity >= IDENT_TMPL and coverage >= QCOV_TMPL.
This makes default_baseline a real action: on genuinely novel complexes no template
exists (mostly False); where a decent template exists it is True.

Outputs:
  leakage_result.jsonl  {target_id, clean, max_precutoff_ident, best_tmpl_ident, template_baseline_correct}
  clean_targets.txt     one clean target_id per line
"""
from __future__ import annotations
import argparse, collections, json, time, urllib.request

IDENT_LEAK, QCOV_LEAK = 30.0, 0.8      # a pre-cutoff hit at/above this == leakage
IDENT_TMPL, QCOV_TMPL = 40.0, 0.6      # a usable homology template (any date)


def parse_m8(path, self_pdb):
    """{tid: [(pident, qcov, homolog_pdb)]} for non-self hits passing the looser template gate."""
    hits = collections.defaultdict(list)
    for line in open(path):
        q, hit, pid, aln, qcov, tcov, ev, bits = line.rstrip("\n").split("\t")
        tid = q.split("|")[0]
        hpdb = hit.split("_")[0].lower()
        pid, qcov = float(pid), float(qcov)
        if hpdb == self_pdb.get(tid) or qcov < QCOV_TMPL or pid < IDENT_TMPL - 10:
            continue  # keep anything that could matter for either gate
        hits[tid].append((pid, qcov, hpdb))
    return hits


def fetch_dates(ids):
    dates = {}
    def batch(chunk):
        q = '{entries(entry_ids:[%s]){rcsb_id rcsb_accession_info{initial_release_date}}}' % \
            ",".join('"%s"' % i.upper() for i in chunk)
        req = urllib.request.Request("https://data.rcsb.org/graphql",
                                     data=json.dumps({"query": q}).encode(),
                                     headers={"Content-Type": "application/json"})
        d = json.load(urllib.request.urlopen(req, timeout=60))
        for e in d["data"]["entries"]:
            ai = e.get("rcsb_accession_info") or {}
            dates[e["rcsb_id"].lower()] = (ai.get("initial_release_date") or "")[:10]
    ids = sorted(ids)
    for i in range(0, len(ids), 150):
        for attempt in range(3):
            try:
                batch(ids[i:i + 150]); break
            except Exception:
                time.sleep(2 * (attempt + 1))
        time.sleep(0.3)
    return dates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--m8", required=True)
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--cutoff", default="2023-06-01")
    ap.add_argument("--out-prefix", default="leakage")
    args = ap.parse_args()

    cands = [json.loads(l) for l in open(args.candidates) if l.strip()]
    self_pdb = {c["target_id"]: c["target_id"] for c in cands}  # target_id IS its pdb id
    hits = parse_m8(args.m8, self_pdb)

    need = {h[2] for hs in hits.values() for h in hs}
    print(f"unique homolog PDB ids to date-look-up: {len(need)}", flush=True)
    dates = fetch_dates(need)
    print(f"dates resolved: {sum(1 for v in dates.values() if v)}/{len(need)}", flush=True)

    results, clean = [], []
    for c in cands:
        tid = c["target_id"]
        hs = hits.get(tid, [])
        precut = [h for h in hs if dates.get(h[2], "9999") < args.cutoff]
        leak = [h for h in precut if h[0] >= IDENT_LEAK and h[1] >= QCOV_LEAK]
        tmpl = [h for h in hs if h[0] >= IDENT_TMPL and h[1] >= QCOV_TMPL]
        max_pre = max((h[0] for h in leak), default=0.0)
        best_tmpl = max((h[0] for h in tmpl), default=0.0)
        is_clean = len(leak) == 0
        rec = {"target_id": tid, "clean": is_clean, "max_precutoff_ident": round(max_pre, 1),
               "best_tmpl_ident": round(best_tmpl, 1), "template_baseline_correct": len(tmpl) > 0,
               "n_chains": c["n_chains"], "total_len": c["total_len"]}
        results.append(rec)
        if is_clean:
            clean.append(tid)
    with open(f"{args.out_prefix}_result.jsonl", "w") as fh:
        for r in results:
            fh.write(json.dumps(r) + "\n")
    with open(f"{args.out_prefix}_clean_targets.txt", "w") as fh:
        fh.write("\n".join(clean) + "\n")
    n_tmpl_clean = sum(1 for r in results if r["clean"] and r["template_baseline_correct"])
    print(json.dumps({"candidates": len(cands), "clean": len(clean),
                      "clean_pct": round(100 * len(clean) / max(1, len(cands)), 1),
                      "clean_with_template": n_tmpl_clean, "cutoff": args.cutoff}, indent=2))


if __name__ == "__main__":
    main()
