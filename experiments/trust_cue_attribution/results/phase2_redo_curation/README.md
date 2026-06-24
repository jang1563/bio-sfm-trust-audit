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

**Decision (by the project's own NO-GO discipline):** a full powered ≥3-model × ≥3-seed
*confirmatory* pilot on a 100%-base-rate substrate cannot establish routing value — "trust-all"
is already optimal, so there is nothing to route (cf. the Phase 1 single-cell NO-GO). A genuine
routing substrate needs cases where the specialist *actually fails* (large assemblies,
disordered/low-MSA targets, function not just fold), which recent crystallisable RCSB structures
do not provide — motivating the report's enforcement-layer pivot.

## Bounded 3-model demo (illustrative, not confirmatory)

A small demo (5 arms × 21 targets × **3 models** — Sonnet 4.6, Opus 4.8, GPT-4.1 — 1 seed,
105 requests/model, run locally) makes the saturation consequence concrete; scores in
[`redo_demo_scores.json`](redo_demo_scores.json). The `calibrated_interface − raw_plddt`
net-reward contrast, **identical across all three models**:

| monomer cutoff | base rate | interface − raw |
|---|---|---|
| lDDT ≥ 0.7 (pre-registered) | 100% | **−0.476** |
| lDDT ≥ 0.9 (post-hoc stakes) | 48% | +0.048 |

On the **saturated** substrate the calibrated reliability *interface* is **dramatically worse
than raw pLDDT** (raw → net ≈ 1.0 by trusting; the interface's risk card triggers blanket
over-verification → wasted cost). Only when stakes are manufactured (0.9 cutoff) does the
interface edge ahead. The fresh, leakage-controlled, cross-model evidence thus **reinforces the
v1 headline** — raw calibrated confidence is the robust lever; the reliability interface is not
a free win and can actively hurt — and shows the effect is governed by whether the substrate
has any routing stakes at all.
