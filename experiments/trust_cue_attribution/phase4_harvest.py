"""Phase 4 substrate expansion — FASTA-only harvest of post-cutoff hetero-complexes.

Leakage screening (mmseqs vs pre-cutoff PDB) is cheap on sequences alone, so we
harvest FASTA + chain manifest ONLY here (no CIF). Reference CIFs are downloaded
later, just for the leakage-clean survivors, by phase4_select_clean.py.

Pool: complexes (>=2 protein entities), released >= 2025-07-01, resolution <= 3.5
(the prior N=57 run used <=3.0; the 3.0-3.5 band supplies net-new candidates).
Excludes the 57 already-predicted target_ids.

Outputs under --out-dir:
  query.fasta        all candidate chains, header `<tid>|<CHAIN>`  (mmseqs query)
  candidates.jsonl   {target_id, n_chains, total_len, seqs:[...]}
  harvest_summary.json
"""
from __future__ import annotations
import argparse, json, os, sys, time, urllib.parse, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..",
    "LLM_SFM_interpretability", "experiments", "trust_cue_attribution"))
from phase2_curate_pdb import (  # noqa: E402
    build_search_query, protein_chains, select_for_regime, _get, SEARCH_URL, FASTA_URL)

CHAINS = "ABCDEFGH"


def search_page(released_after, max_resolution, start, rows):
    q = build_search_query(released_after=released_after, max_resolution=max_resolution,
                           regime="complex", rows=rows, start=start)
    url = SEARCH_URL + "?" + urllib.parse.urlencode({"json": json.dumps(q)})
    data = _get(url, as_json=True)
    return [h["identifier"] for h in data.get("result_set", [])], data.get("total_count", 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--released-after", default="2025-07-01")
    ap.add_argument("--max-resolution", type=float, default=3.5)
    ap.add_argument("--min-len", type=int, default=50)
    ap.add_argument("--max-total-len", type=int, default=1400)
    ap.add_argument("--max-chains", type=int, default=4)
    ap.add_argument("--max-candidates", type=int, default=2000)
    ap.add_argument("--exclude", default="")  # space/comma sep target_ids
    ap.add_argument("--out-dir", default="harvest")
    args = ap.parse_args()

    done = set(x for x in args.exclude.replace(",", " ").split() if x)
    os.makedirs(args.out_dir, exist_ok=True)
    qfa = open(os.path.join(args.out_dir, "query.fasta"), "w")
    cjs = open(os.path.join(args.out_dir, "candidates.jsonl"), "w")

    kept, seen, scanned = 0, 0, 0
    start, total = 0, None
    while kept < args.max_candidates:
        ids, total = search_page(args.released_after, args.max_resolution, start, 500)
        if not ids:
            break
        for pid in ids:
            scanned += 1
            tid = pid.lower()
            if tid in done:
                continue
            try:
                seqs = protein_chains(_get(FASTA_URL.format(pid=pid), as_json=False))
            except Exception:
                continue
            chosen = select_for_regime(seqs, regime="complex", min_len=args.min_len,
                                       max_total_len=args.max_total_len, max_chains=args.max_chains)
            if chosen is None:
                continue
            for i, s in enumerate(chosen):
                qfa.write(f">{tid}|{CHAINS[i]}\n{s}\n")
            cjs.write(json.dumps({"target_id": tid, "n_chains": len(chosen),
                                  "total_len": sum(len(s) for s in chosen), "seqs": chosen}) + "\n")
            qfa.flush(); cjs.flush()
            kept += 1
            if kept % 25 == 0:
                print(f"[{time.strftime('%H:%M:%S')}] scanned={scanned} kept={kept}/{args.max_candidates}", flush=True)
            if kept >= args.max_candidates:
                break
        start += 500
        if total and start >= total:
            break
    qfa.close(); cjs.close()
    summary = {"released_after": args.released_after, "max_resolution": args.max_resolution,
               "total_in_pool": total, "scanned": scanned, "kept_candidates": kept,
               "excluded_done": len(done)}
    json.dump(summary, open(os.path.join(args.out_dir, "harvest_summary.json"), "w"), indent=2)
    print("HARVEST_DONE", json.dumps(summary), flush=True)


if __name__ == "__main__":
    main()
