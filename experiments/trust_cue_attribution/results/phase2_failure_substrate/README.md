# Phase 2 — finding a specialist-FAILURE substrate (where routing has stakes)

The redo established that **monomer fold prediction is saturated** even on
leakage-controlled novel structures (Boltz-2 ~100% at lDDT ≥ 0.7), so trust-routing has
no headroom there. The trust question needs a substrate where the specialist **actually
fails**. This identifies one — **without new compute** — by re-using data in hand.

## Key insight

Sequence leakage memorises a chain's **fold**; it does **not** solve **docking/assembly**.
So protein-**complex interface** prediction can fail even when every chain is leakage-clean.

## Test (v1 complexes, DockQ × leakage)

Cross-referencing the [DockQ validation](../phase2_dockq_validation/) with the
[leakage audit](../phase2_leakage_audit/) for the 40 v1 complexes
([`v1_complex_failure_analysis.json`](v1_complex_failure_analysis.json)):

Among the **6 leakage-clean** complexes (< 30% pre-cutoff identity):

| target | DockQ | ipTM | |
|---|---:|---:|---|
| 30kx | 0.013 | 0.36 | **fail** |
| 30ky | 0.145 | 0.37 | **fail** |
| 30yw | 0.303 | 0.40 | |
| 30yv | 0.485 | 0.53 | |
| 35wd | 0.704 | 0.79 | |
| 9zdm | 0.860 | 0.95 | |

**2/6 fail (DockQ < 0.23), median DockQ 0.39** — and the failures have **low ipTM**
(0.36–0.40) while the successes have **high ipTM** (0.79–0.95).

## Conclusion — the substrate

Protein-**complex interface prediction** (truth = **DockQ**, signal = **ipTM**) is the
viable specialist-failure substrate the monomer route lacked:

1. **Genuine routing stakes** — docking fails ~1/3 of the time *even under leakage control*
   (failure is independent of sequence leakage, unlike monomer fold).
2. **A validated reliability signal** — ipTM predicts DockQ (Pearson 0.77 on v1; here it
   cleanly separates the failures), so there is a calibrated cue to route on.
3. **Leakage-controllable** — the MMseqs2 + RCSB-date pipeline
   ([`../phase2_redo_curation/`](../phase2_redo_curation/)) applies directly to complexes.

## Powered routing experiment — in progress

The redo pipeline restricted to complexes ([`curate_complexes_big.py`](curate_complexes_big.py)
+ [`select_cx.py`](select_cx.py)): 787 recent post-cutoff hetero-complex candidates →
**28 leakage-clean (96% leaky)** → **15 non-redundant** hard complexes (2–4 chains, up to
1995 residues; [`hard_complex_targets.json`](hard_complex_targets.json),
[`hard_complex_curation_summary.json`](hard_complex_curation_summary.json)). Larger/multi-chain
assemblies retained to span docking difficulty.

## Result — directionally consistent, but NOT significant at n=14 (illustrative, not confirmatory)

Boltz-2 predicted all 15; DockQ truth on 14 ([`hard_complex_records.json`](hard_complex_records.json)).
**This set finally has stakes:** DockQ spans 0.005–0.895, base rate **50% at DockQ ≥ 0.49** (7/14),
and **ipTM → DockQ = 0.865**. The ipTM-cued 5-arm pilot (3 models × 14, 1 seed, λ = 0.5;
[`hard_complex_pilot_scores.json`](hard_complex_pilot_scores.json)), with **paired bootstrap 95% CIs**:

| contrast (DockQ ≥ 0.49) | Sonnet 4.6 | Opus 4.8 | GPT-4.1 |
|---|---:|---:|---:|
| raw − no_signal | +0.14 [−0.07, +0.32] | +0.07 [−0.14, +0.29] | +0.11 [−0.11, +0.32] |
| calibrated_interface − raw | −0.07 [−0.21, +0.07] | −0.07 [−0.29, +0.14] | −0.07 [−0.21, +0.07] |

**Every CI crosses zero — nothing is statistically significant.** The point estimates are
*directionally consistent* with the headline (raw is the best arm; the interface sits ~0.07 below
raw across all three models; the inverted control degrades routing), but at n = 14 a 0.07 gap is
~one target and the identical −0.07 across models is a structural coincidence, not three independent
confirmations.

**Honest limitations of this pilot** (see the artifact's `CAVEATS`):

1. **Not significant** (CIs above) — n = 14, single seed, single λ.
2. **In-distribution calibration** — the isotonic risk is fit LOO on these same 14 targets at the
   same DockQ ≥ 0.49 cutoff used for scoring, the exact flaw flagged in v1; the pre-registration
   requires **held-out** calibration, which this pilot does **not** meet.
3. **Stakes are dominated by catastrophic failures** of large/multi-chain complexes (9rch pLDDT 26,
   9rvy 55; DockQ ≈ 0) that ipTM trivially flags (ipTM ≈ 0.20) — closer to "detect obvious failure"
   than fine-grained calibration, which also inflates the ipTM→DockQ correlation.
4. **λ = 0.5 equals the base rate**, so no_signal's verify-all nets exactly 0.5 (a knife-edge); no
   λ-sweep was run. Only 5 arms (no competing-cue arm; no multiplicity correction).

**Conclusion (calibrated):** this substrate *can* finally test the routing question (unlike the
saturated monomer set), and the point estimates lean the project's way — but the pilot is
**illustrative, not confirmatory**. A real claim needs the **pre-registered** run: held-out
calibration, ≥ 3 seeds, ≥ 6 arms, a λ-sweep, and a larger leakage-controlled hard-complex set.
