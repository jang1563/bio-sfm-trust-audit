#!/usr/bin/env python3
"""Powered routing substrate, step 1: pull a LARGE pool of recent post-cutoff HETERO
complexes (>=2 distinct protein chains) and fetch sequences. Leakage filter applied next.
Bias toward genuine docking difficulty by allowing 2-8 chains and larger assemblies."""
import json, os, sys, time, urllib.request, urllib.parse
SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"
FASTA = "https://www.rcsb.org/fasta/entry/{pid}"
RELEASED_AFTER = "2025-07-01"; MAX_RES = 3.5; OUT = sys.argv[1]
TARGET_POOL = 1000

def query(start, rows):
    nodes = [
        {"type":"terminal","service":"text","parameters":{"attribute":"rcsb_accession_info.initial_release_date","operator":"greater_or_equal","value":RELEASED_AFTER}},
        {"type":"terminal","service":"text","parameters":{"attribute":"rcsb_entry_info.resolution_combined","operator":"less_or_equal","value":MAX_RES}},
        {"type":"terminal","service":"text","parameters":{"attribute":"rcsb_entry_info.polymer_entity_count_protein","operator":"greater_or_equal","value":2}},
        {"type":"terminal","service":"text","parameters":{"attribute":"rcsb_entry_info.deposited_polymer_entity_instance_count","operator":"less_or_equal","value":8}},
    ]
    q = {"query":{"type":"group","logical_operator":"and","nodes":nodes},"return_type":"entry",
         "request_options":{"results_content_type":["experimental"],
             "sort":[{"sort_by":"rcsb_accession_info.initial_release_date","direction":"desc"}],
             "paginate":{"start":start,"rows":rows}}}
    url = SEARCH + "?json=" + urllib.parse.quote(json.dumps(q))
    return [r["identifier"] for r in json.load(urllib.request.urlopen(url, timeout=60)).get("result_set", [])]

AA = set("ACDEFGHIKLMNPQRSTVWY")
def is_protein(s): return len(s) >= 20 and sum(1 for c in s.upper() if c in AA)/len(s) > 0.85
def fetch_fasta(pid):
    txt = urllib.request.urlopen(FASTA.format(pid=pid), timeout=60).read().decode()
    out=[]; h=None; buf=[]
    for ln in txt.splitlines():
        if ln.startswith(">"):
            if h and buf: out.append("".join(buf))
            h=ln; buf=[]
        else: buf.append(ln.strip())
    if h and buf: out.append("".join(buf))
    return out

ids=[]
for start in range(0, TARGET_POOL, 200):
    page=query(start,200); ids+=page
    if len(page)<200: break
ids=list(dict.fromkeys(ids))
print(f"complex candidate ids: {len(ids)}", flush=True)

meta={}; seqs={}
for n,pid in enumerate(ids):
    tid=pid.lower()
    try: ch=fetch_fasta(pid)
    except Exception: continue
    prot=[s for s in ch if is_protein(s)]
    uniq=sorted(set(prot))
    if not (2<=len(uniq)<=8): continue        # hetero complex (>=2 DISTINCT chains)
    total=sum(len(s) for s in uniq)
    if total>2000: continue                    # GPU cost bound
    meta[tid]={"pdb_id":pid,"regime":"complex","n_protein_chains":len(uniq),"total_len":total}
    for i,s in enumerate(uniq): seqs[f"{tid}|{i}|complex"]=s
    if n%100==0: print(f"  scanned {n}, kept {len(meta)}", flush=True)
    time.sleep(0.03)

open(os.path.join(OUT,"cx_candidates.fasta"),"w").write("".join(f">{k}\n{s}\n" for k,s in seqs.items()))
json.dump(meta,open(os.path.join(OUT,"cx_candidates_meta.json"),"w"),indent=2)
print(f"COMPLEX candidates: {len(meta)} ({len(seqs)} chains) -> cx_candidates.fasta")
