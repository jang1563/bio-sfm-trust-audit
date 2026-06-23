# Phase 2 — DockQ validation of the complex truth metric

**What.** The adversarial review flagged that v1's complex correctness label —
home-grown *all-chain* CA-lDDT — is **intra-chain-dominated** (most sub-15 Å CA-CA
pairs fall *within* a chain), so it mostly re-measures per-chain fold quality, not
docking, and the reported pLDDT→complex "calibration collapse" (Pearson **0.16**)
might be a metric artifact rather than a real calibration failure.

We tested this directly: re-scored the **40 v1 complex targets** with gold-standard
**DockQ** (DockQ v2, bioconda; Boltz-2 `*_model_0.cif` vs the RCSB reference, automatic
chain mapping) and correlated the specialist's confidence against it.
Compute: Cayuga (CPU), no GPU. Artifacts: [`dockq_validation.json`](dockq_validation.json)
(per-target), [`summary.json`](summary.json), runner [`run_dockq_validation.py`](run_dockq_validation.py).

## Result (n = 40 complexes)

| correlation | value | note |
|---|---:|---|
| Pearson(pLDDT, **DockQ**) | **+0.44** | vs the report's "0.16" — pLDDT predicts complex quality **2.7× better** against the correct metric |
| Pearson(**ipTM**, **DockQ**) | **+0.77** | the *proper* interface confidence is **well-calibrated** to interface correctness |
| Pearson(CA-lDDT v1, DockQ) | +0.30 | the home-grown truth agrees only weakly with DockQ → it was the wrong complex axis |
| Pearson(pLDDT, CA-lDDT v1) | +0.16 | exactly reproduces the v1 number (pipeline check) |

DockQ spread: median 0.45, min 0.013, max 0.951; **33/40 "acceptable" (≥0.23), 18/40
"medium" (≥0.49)** — genuine quality variation, so complexes do carry routing stakes.

## Interpretation

1. The v1 complex **"calibration collapse" was largely a CA-lDDT artifact.** Against
   DockQ, pLDDT→complex is 0.44 (not 0.16), and the home-grown truth agrees with DockQ
   at only 0.30 — confirming the review's intra-chain-domination critique.
2. The specialist **does** emit a well-calibrated complex-interface confidence: **ipTM
   → DockQ = 0.77**. v1 under-sold complex calibration by using pLDDT as the cue and
   CA-lDDT as truth.
3. **For the confirmatory redo** (`../../PHASE2_PREREGISTRATION.md`): score complexes
   with DockQ (this run is a down-payment) and use **ipTM**, not pLDDT, as the complex
   reliability signal.

This does not by itself change the headline trust-routing finding (which is about
*reliability-interface packaging*, not the substrate), but it corrects the complex-regime
calibration story and supplies the validated metric the pre-registration requires.
