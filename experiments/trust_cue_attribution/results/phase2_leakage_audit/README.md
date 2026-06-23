# Phase 2 — sequence-identity leakage audit of the v1 targets

**What.** The adversarial review's #2 finding: v1 controlled training leakage by
**release date alone** ("targets released 2026-06-17, after the cutoff"), with no
homolog/sequence-identity dedup. A post-cutoff *deposition* can still be a
near-duplicate (re-determination, point mutant, alternate crystal form) of an old
PDB entry that **was** in the specialist's training set — which the date filter
cannot catch.

We tested it: searched all 80 v1 target chains against the **entire PDB**
(`pdb_seqres`, 1.13 M chains) with MMseqs2 (`-s 6`), excluded self-matches, and
looked up each homolog's **RCSB initial release date** to keep only **pre-cutoff**
hits. Compute: Cayuga. Artifacts: [`leakage_audit.json`](leakage_audit.json)
(per-target), runner [`mmseqs_search.sh`](mmseqs_search.sh) + [`leak_dates.py`](leak_dates.py).

## Result — the date filter did NOT prevent leakage

Targets (of 80) with a **pre-cutoff** PDB homolog at ≥ coverage 0.8:

| training cutoff | ≥30% identity | ≥50% | **≥90%** |
|---|---:|---:|---:|
| 2021-09-30 | 70/80 | 60/80 | **55/80** |
| 2023-01-01 | 73/80 | 60/80 | **55/80** |
| 2024-01-01 | 73/80 | 60/80 | **56/80** |
| 2025-01-01 | 74/80 | 60/80 | **56/80** |

**~70% of the "leakage-safe" v1 targets have a ≥90%-identical structure that was in
the PDB years before any plausible Boltz-2 cutoff.** The 2026-06-17 release dates are
new *deposition* IDs of largely *old* sequences.

## Interpretation

1. **v1's "leakage-safe" claim does not hold.** Most targets are effectively
   memorizable; the specialist's high accuracy (~95% at lDDT ≥ 0.7) is, for the
   majority, predicting structures with near-identical training neighbors. This
   confirms the review's #2 finding empirically and compounds the low-stakes
   substrate problem (the routing question has little headroom when the model is
   near-perfect *because* the answer was seen).
2. **The pre-registration's homolog dedup is now empirically mandatory.** Excluding
   the ≥30% pre-cutoff homologs would leave **~6–10 of 80** targets — far too few;
   the confirmatory redo must *curate for* low-homology / genuinely novel folds
   (CASP-hard, orphan families) rather than filter an existing recent-deposition set.
3. Caveat: identity here is sequence (MMseqs2), a proxy for structural memorization;
   it does not prove a given target was in Boltz-2's exact training split (that set
   is not public), and the true cutoff is itself uncertain — hence the multi-cutoff
   table. But ≥90% identity to a years-old PDB entry is a strong leakage signal at
   any of these dates.
