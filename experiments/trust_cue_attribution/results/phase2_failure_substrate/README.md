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

## Result — headline confirmed on the first real-stakes substrate

Boltz-2 predicted all 15; DockQ truth on 14 ([`hard_complex_records.json`](hard_complex_records.json)).
**This set finally has stakes:** DockQ spans 0.005–0.895, base rate **50% at DockQ ≥ 0.49**
(7/14), and **ipTM → DockQ = 0.865** (large/multi-chain assemblies fail — e.g. 9rch/9rvy pLDDT
26–55, DockQ ≈ 0). The ipTM-cued 5-arm routing pilot (3 models × 14, [`hard_complex_pilot_scores.json`](hard_complex_pilot_scores.json)):

| contrast (DockQ ≥ 0.49) | Sonnet 4.6 | Opus 4.8 | GPT-4.1 |
|---|---:|---:|---:|
| **raw − no_signal** (does the signal help?) | **+0.143** | +0.071 | +0.107 |
| **calibrated_interface − raw** (does the card beat raw?) | −0.072 | −0.071 | −0.071 |

The project's headline is **confirmed on a genuinely-powered, leakage-controlled, real-stakes
substrate** — the first one that can actually test it:

1. **Raw calibrated confidence genuinely helps** here (raw − no_signal > 0; raw is the best arm)
   — *not* the trivial "any cue beats deferral" of the saturated monomer set.
2. **The calibrated reliability *interface* does not beat raw** — consistently **−0.07** across all
   three models (incl. non-Anthropic GPT-4.1); it induces over-verification (Opus collapses to
   verify-all under any risk card).
3. **Cue-following persists** (the inverted control degrades routing).

Conclusion: raw confidence is the robust lever; presentation-layer reliability interfaces are not
a free win — even where the signal is strong and the stakes are real — motivating enforcement-based
routing (Phase 4).
