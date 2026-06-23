"""Phase 2 truth: superposition-free CA-lDDT of Boltz predictions vs experimental
reference structures, producing the calibration-gate truth table.

OpenStructure is not on Cayuga and DockQ's wheel fails to build there, so we
implement lDDT (Mariani et al. 2013) directly over CA atoms using gemmi (a Boltz
dependency). Monomers use single-chain lDDT; complexes use all-chain lDDT
(inter-chain CA pairs included -> the interface), which is exactly what Boltz's
`complex_plddt` is trained to predict, so it is the cleanest calibration target.
Limitation: CA-only (not full-atom) and not interface-specific like DockQ; DockQ
can be swapped in for complexes later if it ever builds.

lDDT is superposition-free: it compares reference vs model CA-CA distances, so no
structural alignment is needed -- only a residue correspondence (sequence
alignment), which we compute with a small Needleman-Wunsch.

Pure logic (alignment, chain matching, lDDT math) has no gemmi dependency and is
unit-tested; gemmi is only used for structure I/O in `compute_target_lddt`.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
from typing import Any, Optional

LDDT_THRESHOLDS = (0.5, 1.0, 2.0, 4.0)
INCLUSION_RADIUS = 15.0
DEFAULT_CORRECT_LDDT = 0.7

Coord = tuple[float, float, float]
Residue = tuple[str, Coord]  # (one_letter, (x,y,z) of CA)


def _dist(a: Coord, b: Coord) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def nw_match(a: str, b: str, *, match: int = 1, mismatch: int = -1, gap: int = -1) -> list[tuple[int, int]]:
    """Needleman-Wunsch global alignment; return aligned index pairs (i in a, j in b)."""
    n, m = len(a), len(b)
    score = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        score[i][0] = i * gap
    for j in range(1, m + 1):
        score[0][j] = j * gap
    for i in range(1, n + 1):
        ai = a[i - 1]
        row, prev = score[i], score[i - 1]
        for j in range(1, m + 1):
            s = match if ai == b[j - 1] else mismatch
            row[j] = max(prev[j - 1] + s, prev[j] + gap, row[j - 1] + gap)
    i, j, pairs = n, m, []
    while i > 0 and j > 0:
        s = match if a[i - 1] == b[j - 1] else mismatch
        if score[i][j] == score[i - 1][j - 1] + s:
            pairs.append((i - 1, j - 1)); i -= 1; j -= 1
        elif score[i][j] == score[i - 1][j] + gap:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return pairs


def _seq(residues: list[Residue]) -> str:
    return "".join(r[0] for r in residues)


def match_chains(ref: dict[str, list[Residue]], pred: dict[str, list[Residue]],
                 *, min_identity: float = 0.5) -> list[tuple[str, str]]:
    """Greedy best-identity pairing of reference chains to predicted chains."""
    ref_seqs = {c: _seq(r) for c, r in ref.items()}
    pred_seqs = {c: _seq(r) for c, r in pred.items()}
    pairs, used = [], set()
    for rc, rseq in ref_seqs.items():
        best, best_id = None, -1.0
        for pc, pseq in pred_seqs.items():
            if pc in used:
                continue
            aln = nw_match(rseq, pseq)
            ident = (sum(1 for i, j in aln if rseq[i] == pseq[j]) / len(aln)) if aln else 0.0
            if ident > best_id:
                best_id, best = ident, pc
        if best is not None and best_id >= min_identity:
            used.add(best); pairs.append((rc, best))
    return pairs


def matched_ca_pairs(ref: dict[str, list[Residue]], pred: dict[str, list[Residue]]) -> list[tuple[Coord, Coord]]:
    """Return [(ref_ca_xyz, pred_ca_xyz)] over residue-aligned, chain-matched CAs."""
    out: list[tuple[Coord, Coord]] = []
    for rc, pc in match_chains(ref, pred):
        rres, pres = ref[rc], pred[pc]
        for i, j in nw_match(_seq(rres), _seq(pres)):
            out.append((rres[i][1], pres[j][1]))
    return out


def ca_lddt(matched: list[tuple[Coord, Coord]],
            *, inclusion_radius: float = INCLUSION_RADIUS,
            thresholds: tuple[float, ...] = LDDT_THRESHOLDS) -> Optional[float]:
    """Superposition-free CA-lDDT over matched (ref, pred) CA pairs. None if no pairs.

    All matched CAs are pooled across chains, so for complexes the inter-chain
    pairs (the interface) are naturally included.
    """
    n = len(matched)
    if n < 2:
        return None
    considered = 0
    preserved = [0] * len(thresholds)
    for i in range(n):
        rxi, pxi = matched[i]
        for j in range(i + 1, n):
            rxj, pxj = matched[j]
            d_ref = _dist(rxi, rxj)
            if d_ref >= inclusion_radius:
                continue
            considered += 1
            diff = abs(d_ref - _dist(pxi, pxj))
            for k, t in enumerate(thresholds):
                if diff < t:
                    preserved[k] += 1
    if considered == 0:
        return None
    return sum(preserved[k] / considered for k in range(len(thresholds))) / len(thresholds)


def lddt_for_structures(ref: dict[str, list[Residue]], pred: dict[str, list[Residue]]) -> Optional[float]:
    return ca_lddt(matched_ca_pairs(ref, pred))


# ---- gemmi structure I/O (not unit-tested; gemmi only here) ----

def read_ca_chains(path: str) -> dict[str, list[Residue]]:
    import gemmi  # boltz dependency
    st = gemmi.read_structure(path)
    st.setup_entities()
    out: dict[str, list[Residue]] = {}
    for chain in st[0]:
        residues: list[Residue] = []
        for res in chain:
            info = gemmi.find_tabulated_residue(res.name)
            if info is None or not info.is_amino_acid():
                continue
            ca = next((a for a in res if a.name == "CA"), None)
            if ca is None:
                continue
            ol = (info.one_letter_code or "x").upper()
            residues.append((ol if ol.isalpha() else "X", (ca.pos.x, ca.pos.y, ca.pos.z)))
        if residues:
            out[chain.name] = residues
    return out


def find_pred_cif(pred_dir: str, target_id: str) -> Optional[str]:
    hits = glob.glob(os.path.join(pred_dir, target_id, "**", f"{target_id}_model_0.cif"), recursive=True)
    if not hits:
        hits = glob.glob(os.path.join(pred_dir, target_id, "**", "*_model_0.cif"), recursive=True)
    return sorted(hits)[0] if hits else None


def compute_target_lddt(*, reference_cif: str, pred_cif: str) -> Optional[float]:
    return lddt_for_structures(read_ca_chains(reference_cif), read_ca_chains(pred_cif))


def build_truth_table(*, targets: list[dict[str, Any]], reference_dir: str, pred_dir: str,
                      correct_lddt: float = DEFAULT_CORRECT_LDDT,
                      template_baseline_correct: Optional[dict[str, bool]] = None,
                      ) -> tuple[list[dict[str, Any]], list[str]]:
    rows, skipped = [], []
    for t in targets:
        tid = str(t["target_id"])
        ref = os.path.join(reference_dir, f"{tid}.cif")
        pred = find_pred_cif(pred_dir, tid)
        if not os.path.exists(ref):
            skipped.append(f"{tid}: missing reference"); continue
        if pred is None:
            skipped.append(f"{tid}: missing prediction"); continue
        lddt = compute_target_lddt(reference_cif=ref, pred_cif=pred)
        if lddt is None:
            skipped.append(f"{tid}: lddt undefined (no matched CAs)"); continue
        tb = (template_baseline_correct or {}).get(tid, False)
        rows.append({
            "target_id": tid,
            "correct": bool(lddt >= correct_lddt),
            "quality": round(float(lddt), 6),
            "template_baseline_correct": bool(tb),
        })
    return rows, skipped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True, help="targets manifest JSONL (target_id, regime)")
    ap.add_argument("--reference-dir", required=True, help="dir of <target_id>.cif experimental refs")
    ap.add_argument("--pred-dir", required=True, help="Boltz predictions root (per-target subdirs)")
    ap.add_argument("--out", required=True, help="output truth JSONL")
    ap.add_argument("--correct-lddt", type=float, default=DEFAULT_CORRECT_LDDT)
    args = ap.parse_args()
    targets = [json.loads(line) for line in open(args.targets) if line.strip()]
    rows, skipped = build_truth_table(
        targets=targets, reference_dir=args.reference_dir,
        pred_dir=args.pred_dir, correct_lddt=args.correct_lddt)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    print(f"wrote {len(rows)} truth rows to {args.out}; skipped {len(skipped)}")
    for s in skipped[:20]:
        print(f"  - {s}")


if __name__ == "__main__":
    main()
