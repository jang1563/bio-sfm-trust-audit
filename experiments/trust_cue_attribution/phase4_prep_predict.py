#!/usr/bin/env python3
"""Phase 4 substrate: build Boltz inputs + experimental references for the leakage-clean
targets. Reads the harvested seqs (no re-fetch) + downloads each reference CIF from RCSB.

Outputs under --out-dir:
  fasta/<tid>.fasta     Boltz input (>A|protein\\nSEQ ...)
  reference/<tid>.cif   experimental structure (DockQ truth)
  targets.jsonl         {target_id, regime: "complex", n_chains, total_len}
"""
import argparse, json, os, time, urllib.request

CHAINS = "ABCDEFGH"
CIF_URL = "https://files.rcsb.org/download/{pid}.cif"


def boltz_fasta(seqs):
    return "".join(f">{CHAINS[i]}|protein\n{s}\n" for i, s in enumerate(seqs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", required=True)        # leakage_clean_targets.txt
    ap.add_argument("--candidates", required=True)   # candidates.jsonl (has seqs)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--limit", type=int, default=0)  # 0 = all clean
    args = ap.parse_args()

    clean = [t.strip() for t in open(args.clean) if t.strip()]
    if args.limit:
        clean = clean[:args.limit]
    clean_set = set(clean)
    seqs_by = {}
    for line in open(args.candidates):
        if line.strip():
            c = json.loads(line)
            if c["target_id"] in clean_set:
                seqs_by[c["target_id"]] = c
    fdir = os.path.join(args.out_dir, "fasta"); rdir = os.path.join(args.out_dir, "reference")
    os.makedirs(fdir, exist_ok=True); os.makedirs(rdir, exist_ok=True)

    manifest, got, miss = [], 0, []
    for tid in clean:
        c = seqs_by.get(tid)
        if not c:
            miss.append(tid); continue
        cif_path = os.path.join(rdir, f"{tid}.cif")
        if not os.path.exists(cif_path):
            try:
                req = urllib.request.Request(CIF_URL.format(pid=tid), headers={"User-Agent": "phase4"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    open(cif_path, "w").write(resp.read().decode("utf-8"))
            except Exception as e:
                miss.append(f"{tid}:cif:{e}"); continue
        open(os.path.join(fdir, f"{tid}.fasta"), "w").write(boltz_fasta(c["seqs"]))
        manifest.append({"target_id": tid, "regime": "complex", "n_chains": c["n_chains"], "total_len": c["total_len"]})
        got += 1
        if got % 25 == 0:
            print(f"prepped {got}/{len(clean)}", flush=True)
        time.sleep(0.1)
    with open(os.path.join(args.out_dir, "targets.jsonl"), "w") as fh:
        for m in manifest:
            fh.write(json.dumps(m) + "\n")
    print(json.dumps({"prepped": got, "missing": len(miss), "missing_detail": miss[:10]}, indent=2))


if __name__ == "__main__":
    main()
