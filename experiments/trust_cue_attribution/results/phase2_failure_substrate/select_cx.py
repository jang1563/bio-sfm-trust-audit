import json, collections, urllib.request, time
W="<WORK_DIR>"; CUT="2025-07-01"; IDT,QC=30.0,0.5
meta=json.load(open(W+"/cx_candidates_meta.json"))
hits=collections.defaultdict(list)
for line in open(W+"/cx_results.m8"):
    q,hit,pid,aln,qc,tc,ev,bits=line.rstrip("\n").split("\t")
    tid=q.split("|")[0]; hp=hit.split("_")[0].lower(); pid=float(pid); qc=float(qc)
    if tid not in meta or hp==tid or pid<IDT or qc<QC: continue
    hits[tid].append((pid,hp))
for tid in hits: hits[tid]=sorted(set(hits[tid]),key=lambda x:-x[0])[:25]
need=sorted({h[1] for v in hits.values() for h in v})
print(f"candidates with >=30% non-self hit: {len(hits)}/{len(meta)}; unique homologs to date-check: {len(need)}",flush=True)
dates={}
def fetch(ids):
    q='{entries(entry_ids:[%s]){rcsb_id rcsb_accession_info{initial_release_date}}}'%",".join('"%s"'%i.upper() for i in ids)
    r=urllib.request.Request("https://data.rcsb.org/graphql",data=json.dumps({"query":q}).encode(),headers={"Content-Type":"application/json"})
    for e in json.load(urllib.request.urlopen(r,timeout=90))["data"]["entries"]:
        ai=e.get("rcsb_accession_info") or {}; dates[e["rcsb_id"].lower()]=(ai.get("initial_release_date") or "")[:10]
for i in range(0,len(need),150): fetch(need[i:i+150]); time.sleep(0.2)
print(f"dates resolved {sum(1 for v in dates.values() if v)}/{len(need)}",flush=True)
clean=[]
for tid,m in meta.items():
    pre=[p for p,hp in hits.get(tid,[]) if dates.get(hp,"") and dates[hp]<CUT]
    if max(pre,default=0.0)<IDT: clean.append(tid)
json.dump({"clean":clean,"meta":{t:meta[t] for t in clean}},open(W+"/cx_clean.json","w"),indent=2)
print(f"\nLEAKAGE-CLEAN complexes: {len(clean)}/{len(meta)}")
