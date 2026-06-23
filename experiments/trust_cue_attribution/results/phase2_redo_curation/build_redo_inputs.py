#!/usr/bin/env python3
"""D step 4: build Boltz-2 inputs + reference structures for the 21 non-redundant
low-homology redo targets."""
import json, os, sys, urllib.request, time
WORK = sys.argv[1]
tgts = json.load(open(WORK + "/redo_targets.json"))["targets"]
ids = {t["target_id"] for t in tgts}
seqs = {}
h = None
for ln in open(WORK + "/candidates.fasta"):
    if ln.startswith(">"):
        p = ln[1:].strip().split("|"); h = (p[0], int(p[1]))
    elif h and h[0] in ids:
        seqs.setdefault(h[0], {})[h[1]] = ln.strip()
os.makedirs(WORK + "/fasta", exist_ok=True); os.makedirs(WORK + "/reference", exist_ok=True)
CIF = "https://files.rcsb.org/download/{pid}.cif"
man = []
for t in tgts:
    tid = t["target_id"]; chs = [seqs[tid][i] for i in sorted(seqs[tid])]
    with open(f"{WORK}/fasta/{tid}.fasta", "w") as fh:
        for i, s in enumerate(chs):
            fh.write(f">{chr(65 + i)}|protein\n{s}\n")
    try:
        data = urllib.request.urlopen(CIF.format(pid=t["pdb_id"]), timeout=90).read()
        open(f"{WORK}/reference/{tid}.cif", "wb").write(data)
        ok = True
    except Exception as e:
        print("CIF fail", tid, e); ok = False
    man.append({"target_id": tid, "pdb_id": t["pdb_id"], "regime": t["regime"],
                "n_protein_chains": t["n_protein_chains"], "total_len": t["total_len"], "ref_ok": ok})
    time.sleep(0.1)
open(WORK + "/targets.jsonl", "w").write("\n".join(json.dumps(m) for m in man) + "\n")
print(f"built {len(man)} fasta; refs ok: {sum(1 for m in man if m['ref_ok'])}/{len(man)}")
