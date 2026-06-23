"""Curate a leakage-safe Phase 2 target set from the RCSB PDB Search API.

CAMEO's accessible archive is frozen at early-2025 (38 targets, inside Boltz-2's
ligand-cutoff window), so we curate recent experimental structures directly from
RCSB. Boltz-2 training cutoff is 2023-06-01 with ligand complexes through early
2025; default released-after is 2025-07-01 for a safe margin.

Produces, under --out-dir:
  fasta/<target_id>.fasta        Boltz input (one `>CHAIN|protein` record per chain)
  reference/<target_id>.cif      experimental reference (for lDDT/DockQ truth)
  targets.jsonl                  manifest: {target_id, regime, pdb_id, n_protein_chains, total_len}

regime: monomer = exactly 1 protein chain; complex = 2..max_chains protein chains.
Network I/O via stdlib urllib (no extra deps). Pure helpers are unit-tested;
the live query is verified by a small Cayuga run.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from typing import Any, Optional

SEARCH_URL = "https://search.rcsb.org/rcsbsearch/v2/query"
FASTA_URL = "https://www.rcsb.org/fasta/entry/{pid}"
CIF_URL = "https://files.rcsb.org/download/{pid}.cif"

AA = set("ACDEFGHIKLMNPQRSTVWYUOBZXacdefghiklmnpqrstvwy")


def build_search_query(
    *, released_after: str, max_resolution: float, regime: str, rows: int, start: int = 0
) -> dict[str, Any]:
    """RCSB Search API query for recent protein entries of the given regime."""
    nodes = [
        {"type": "terminal", "service": "text", "parameters": {
            "attribute": "rcsb_accession_info.initial_release_date",
            "operator": "greater_or_equal", "value": released_after}},
        {"type": "terminal", "service": "text", "parameters": {
            "attribute": "rcsb_entry_info.resolution_combined",
            "operator": "less_or_equal", "value": max_resolution}},
    ]
    if regime == "monomer":
        nodes.append({"type": "terminal", "service": "text", "parameters": {
            "attribute": "rcsb_entry_info.deposited_polymer_entity_instance_count",
            "operator": "equals", "value": 1}})
        nodes.append({"type": "terminal", "service": "text", "parameters": {
            "attribute": "rcsb_entry_info.polymer_entity_count_protein",
            "operator": "equals", "value": 1}})
    elif regime == "complex":
        nodes.append({"type": "terminal", "service": "text", "parameters": {
            "attribute": "rcsb_entry_info.polymer_entity_count_protein",
            "operator": "greater_or_equal", "value": 2}})
    else:
        raise ValueError(f"regime must be monomer|complex, got {regime!r}")
    return {
        "query": {"type": "group", "logical_operator": "and", "nodes": nodes},
        "return_type": "entry",
        "request_options": {
            "results_content_type": ["experimental"],
            "sort": [{"sort_by": "rcsb_accession_info.initial_release_date", "direction": "desc"}],
            "paginate": {"start": start, "rows": rows},
        },
    }


def is_protein_sequence(seq: str) -> bool:
    if len(seq) < 20:
        return False
    aa_like = sum(1 for c in seq if c in AA) / len(seq)
    nt_like = sum(1 for c in seq.upper() if c in "ACGTU") / len(seq)
    return aa_like > 0.95 and nt_like < 0.9  # exclude pure nucleotide chains


def parse_rcsb_fasta(text: str) -> list[tuple[str, str]]:
    """Return [(header, sequence)] records from an RCSB multi-entity FASTA."""
    records: list[tuple[str, str]] = []
    header: Optional[str] = None
    seq: list[str] = []
    for line in text.splitlines():
        if line.startswith(">"):
            if header is not None:
                records.append((header, "".join(seq)))
            header, seq = line[1:].strip(), []
        elif line.strip():
            seq.append(line.strip())
    if header is not None:
        records.append((header, "".join(seq)))
    return records


def protein_chains(fasta_text: str) -> list[str]:
    """Distinct protein chain sequences from an entry FASTA (one per polymer entity)."""
    return [seq for _, seq in parse_rcsb_fasta(fasta_text) if is_protein_sequence(seq)]


def select_for_regime(
    seqs: list[str], *, regime: str, min_len: int, max_total_len: int, max_chains: int
) -> Optional[list[str]]:
    """Apply regime + length gates; return the chains to fold, or None to skip."""
    seqs = [s for s in seqs if len(s) >= min_len]
    if regime == "monomer":
        if len(seqs) != 1:
            return None
    else:  # complex
        if not (2 <= len(seqs) <= max_chains):
            return None
    if sum(len(s) for s in seqs) > max_total_len:
        return None
    return seqs


def to_boltz_fasta(seqs: list[str]) -> str:
    chains = "ABCDEFGH"
    return "".join(f">{chains[i]}|protein\n{seq}\n" for i, seq in enumerate(seqs))


# ---- network ----

def _get(url: str, *, as_json: bool, timeout: int = 60, retries: int = 3) -> Any:
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "bio-sfm-trust-audit/phase2"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw) if as_json else raw
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} tries: {url}: {last}")


def search_entries(query: dict[str, Any]) -> list[str]:
    url = SEARCH_URL + "?" + urllib.parse.urlencode({"json": json.dumps(query)})
    data = _get(url, as_json=True)
    return [hit["identifier"] for hit in data.get("result_set", [])]


def curate(
    *, released_after: str, max_resolution: float, n_monomer: int, n_complex: int,
    out_dir: str, min_len: int, max_total_len: int, max_chains: int, overfetch: int,
) -> dict[str, Any]:
    fasta_dir = os.path.join(out_dir, "fasta")
    ref_dir = os.path.join(out_dir, "reference")
    os.makedirs(fasta_dir, exist_ok=True)
    os.makedirs(ref_dir, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    for regime, want in (("monomer", n_monomer), ("complex", n_complex)):
        ids = search_entries(build_search_query(
            released_after=released_after, max_resolution=max_resolution,
            regime=regime, rows=want * overfetch))
        kept = 0
        for pid in ids:
            if kept >= want:
                break
            try:
                seqs = protein_chains(_get(FASTA_URL.format(pid=pid), as_json=False))
            except Exception:  # noqa: BLE001
                continue
            chosen = select_for_regime(
                seqs, regime=regime, min_len=min_len,
                max_total_len=max_total_len, max_chains=max_chains)
            if chosen is None:
                continue
            tid = pid.lower()
            try:
                cif = _get(CIF_URL.format(pid=pid), as_json=False)
            except Exception:  # noqa: BLE001
                continue
            with open(os.path.join(fasta_dir, f"{tid}.fasta"), "w") as fh:
                fh.write(to_boltz_fasta(chosen))
            with open(os.path.join(ref_dir, f"{tid}.cif"), "w") as fh:
                fh.write(cif)
            manifest.append({
                "target_id": tid, "pdb_id": pid, "regime": regime,
                "n_protein_chains": len(chosen), "total_len": sum(len(s) for s in chosen),
            })
            kept += 1
    with open(os.path.join(out_dir, "targets.jsonl"), "w") as fh:
        for row in manifest:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    summary = {
        "released_after": released_after, "max_resolution": max_resolution,
        "n_monomer": sum(1 for r in manifest if r["regime"] == "monomer"),
        "n_complex": sum(1 for r in manifest if r["regime"] == "complex"),
        "out_dir": out_dir,
    }
    with open(os.path.join(out_dir, "curation_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--released-after", default="2025-07-01")
    ap.add_argument("--max-resolution", type=float, default=3.0)
    ap.add_argument("--n-monomer", type=int, default=40)
    ap.add_argument("--n-complex", type=int, default=40)
    ap.add_argument("--min-len", type=int, default=50)
    ap.add_argument("--max-total-len", type=int, default=1200)
    ap.add_argument("--max-chains", type=int, default=4)
    ap.add_argument("--overfetch", type=int, default=8)
    ap.add_argument("--out-dir", default="experiments/trust_cue_attribution/hpc_outputs/phase2_targets")
    args = ap.parse_args()
    summary = curate(
        released_after=args.released_after, max_resolution=args.max_resolution,
        n_monomer=args.n_monomer, n_complex=args.n_complex, out_dir=args.out_dir,
        min_len=args.min_len, max_total_len=args.max_total_len,
        max_chains=args.max_chains, overfetch=args.overfetch,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
