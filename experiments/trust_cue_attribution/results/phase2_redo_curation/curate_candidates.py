#!/usr/bin/env python3
"""D step 1-2: pull a LARGE pool of recent post-cutoff RCSB candidates (both regimes),
fetch their sequences, and write one candidate FASTA + metadata. The low-homology
leakage filter (MMseqs2 vs pre-cutoff PDB) is applied next, so we curate for genuinely
novel folds rather than recent re-depositions of old structures."""
import json, os, sys, time, urllib.request, urllib.parse

SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
FASTA_URL = "https://www.rcsb.org/fasta/entry/{pid}"
RELEASED_AFTER = "2025-07-01"   # corrected Boltz-2 structural-cutoff margin
MAX_RES = 3.0
ROWS = 250                       # per regime candidate pool
OUT = sys.argv[1] if len(sys.argv) > 1 else "."

def query(regime, rows, start=0):
    nodes = [
        {"type":"terminal","service":"text","parameters":{"attribute":"rcsb_accession_info.initial_release_date","operator":"greater_or_equal","value":RELEASED_AFTER}},
        {"type":"terminal","service":"text","parameters":{"attribute":"rcsb_entry_info.resolution_combined","operator":"less_or_equal","value":MAX_RES}},
    ]
    if regime=="monomer":
        nodes += [{"type":"terminal","service":"text","parameters":{"attribute":"rcsb_entry_info.deposited_polymer_entity_instance_count","operator":"equals","value":1}},
                  {"type":"terminal","service":"text","parameters":{"attribute":"rcsb_entry_info.polymer_entity_count_protein","operator":"equals","value":1}}]
    else:
        nodes += [{"type":"terminal","service":"text","parameters":{"attribute":"rcsb_entry_info.polymer_entity_count_protein","operator":"greater_or_equal","value":2}},
                  {"type":"terminal","service":"text","parameters":{"attribute":"rcsb_entry_info.deposited_polymer_entity_instance_count","operator":"less_or_equal","value":6}}]
    q = {"query":{"type":"group","logical_operator":"and","nodes":nodes},"return_type":"entry",
         "request_options":{"results_content_type":["experimental"],
             "sort":[{"sort_by":"rcsb_accession_info.initial_release_date","direction":"desc"}],
             "paginate":{"start":start,"rows":rows}}}
    url = SEARCH_URL + "?json=" + urllib.parse.quote(json.dumps(q))
    d = json.load(urllib.request.urlopen(url, timeout=60))
    return [r["identifier"] for r in d.get("result_set", [])]

AA = set("ACDEFGHIKLMNPQRSTVWY")
def is_protein(seq):
    if len(seq) < 20: return False
    return sum(1 for c in seq.upper() if c in AA)/len(seq) > 0.85

def fetch_fasta(pid):
    txt = urllib.request.urlopen(FASTA_URL.format(pid=pid), timeout=60).read().decode()
    chains = []  # (header, seq)
    h, buf = None, []
    for ln in txt.splitlines():
        if ln.startswith(">"):
            if h and buf: chains.append((h, "".join(buf)))
            h, buf = ln[1:], []
        else:
            buf.append(ln.strip())
    if h and buf: chains.append((h, "".join(buf)))
    return chains

meta = {}
seqs = {}  # tid|idx -> seq
for regime in ("monomer", "complex"):
    ids = query(regime, ROWS)
    print(f"{regime}: {len(ids)} candidates", flush=True)
    for pid in ids:
        tid = pid.lower()
        try:
            ch = fetch_fasta(pid)
        except Exception as e:
            continue
        prot = [s for _, s in ch if is_protein(s)]
        # dedup identical chains (homo-oligomers)
        uniq = sorted(set(prot))
        if not uniq: continue
        if regime == "monomer" and len(uniq) != 1: continue
        if regime == "complex" and not (2 <= len(uniq) <= 6): continue
        total_len = sum(len(s) for s in uniq)
        if total_len > 1800: continue        # keep Boltz GPU cost bounded
        meta[tid] = {"pdb_id": pid, "regime": regime, "n_protein_chains": len(uniq), "total_len": total_len}
        for i, s in enumerate(uniq):
            seqs[f"{tid}|{i}|{regime}"] = s
        time.sleep(0.05)
    print(f"{regime}: kept {sum(1 for m in meta.values() if m['regime']==regime)}", flush=True)

with open(os.path.join(OUT, "candidates.fasta"), "w") as fh:
    for k, s in seqs.items():
        fh.write(f">{k}\n{s}\n")
json.dump(meta, open(os.path.join(OUT, "candidates_meta.json"), "w"), indent=2)
print(f"TOTAL candidates: {len(meta)} ({sum(1 for m in meta.values() if m['regime']=='monomer')} mono, "
      f"{sum(1 for m in meta.values() if m['regime']=='complex')} complex); {len(seqs)} chains -> candidates.fasta")
