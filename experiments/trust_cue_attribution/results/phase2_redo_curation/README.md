# Phase 2 redo — leakage-controlled target curation

**Goal.** The [leakage audit](../phase2_leakage_audit/) showed v1's date-only curation
let ~70% of targets keep a ≥90% pre-cutoff homolog. The confirmatory redo
(`../../PHASE2_PREREGISTRATION.md`) requires a **genuinely low-homology** target set.
This curates one. Compute: Cayuga.

## Pipeline (reproducible)

1. [`curate_candidates.py`](curate_candidates.py) — RCSB Search API: protein entries
   released **≥ 2025-07-01**, resolution ≤ 3 Å, monomer (1 chain) or complex (2–6),
   total length ≤ 1800. → **452 candidates** (249 monomer, 203 complex), sequences fetched.
2. [`select_lowhom.py`](select_lowhom.py) — MMseqs2 (`-s 6`) each candidate vs the full
   PDB; for non-self hits with ≥30% identity over ≥50% coverage, look up the homolog's
   RCSB release date; a candidate is **leaky** if any such homolog is **pre-cutoff
   (< 2025-07-01)**. → **416/452 (92%) leaky**, **36 clean**.
3. Intra-set declustering (MMseqs2 `easy-cluster`, 30% id / 50% cov) + greedy
   target-level selection → **21 non-redundant low-homology targets** (16 monomer,
   5 complex), all with **0% pre-cutoff homology**. See [`redo_targets.json`](redo_targets.json),
   [`selection_summary.json`](selection_summary.json).
4. [`build_redo_inputs.py`](build_redo_inputs.py) — Boltz-2 input FASTA + RCSB reference
   structures for the 21. [`run_redo_boltz.sbatch`](run_redo_boltz.sbatch) — Boltz-2
   prediction (`--use_msa_server --model boltz2`), then OST lDDT (monomers) / DockQ
   (complexes) for truth, then the ≥3-model × ≥3-seed LLM pilot.

## Key finding (already a result)

**92% of recent post-cutoff RCSB depositions carry a ≥30%-identity pre-cutoff PDB
homolog** — genuinely novel recent structures are rare. A leakage-controlled
confirmatory set is therefore necessarily **small (n = 21)**; this is the honest cost
of the homolog dedup the pre-registration requires, and it is reported as such rather
than padded with leaky targets.

## Status

Boltz-2 prediction submitted on Cayuga (scu-gpu). Downstream — OST/DockQ truth, held-out
calibration (fit on v1, evaluate on this set), ≥3-model × ≥3-seed LLM runs, and the
multiplicity-corrected analysis — follow once predictions land.
