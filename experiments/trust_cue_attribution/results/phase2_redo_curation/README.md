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

## Outcome — the substrate is saturated even without leakage (NO-GO for the routing pilot)

Boltz-2 predicted all 21 (Cayuga scu-gpu); truth via OST lDDT (monomers) + DockQ (complexes)
— see [`redo_records.json`](redo_records.json), [`redo_base_rate.json`](redo_base_rate.json).

At the **pre-registered** cutoffs the leakage-controlled set is **fully saturated**:

| regime | metric | base rate at pre-set cutoff |
|---|---|---|
| monomer (16) | OST lDDT ≥ 0.7 | **16/16 (100%)** |
| complex (5) | DockQ ≥ 0.23 | **5/5 (100%)** |

Monomer stakes appear only at lDDT ≥ 0.9 (5/16) — the *post-hoc* cutoff v1 was criticised for.
So **Boltz-2 succeeds on recent novel-fold structures too**: the low-stakes problem is
**intrinsic to recent high-resolution depositions, independent of leakage** (this redo
empirically separates the two confounds — leakage is real *and* low-stakes is real).

**Decision (by the project's own NO-GO discipline):** running the ≥3-model × ≥3-seed LLM
routing pilot on a 100%-base-rate substrate would repeat exactly v1's error — "trust-all" is
already optimal, so there is nothing to route. As with the Phase 1 single-cell NO-GO, the
pilot is **not run** here. A genuine routing substrate needs cases where the specialist
*actually fails* (harder modalities — large assemblies, disordered/low-MSA targets, function
not just fold), which recent crystallisable RCSB structures do not provide. This justifies the
report's pivot toward enforcement-based routing and a different specialist-failure regime.
