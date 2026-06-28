# Phase 4 — powered enforcement confirmatory (fresh strict-leakage substrate)

The pre-registered ([`../../PHASE4_PREREGISTRATION.md`](../../PHASE4_PREREGISTRATION.md)) confirmatory of
the Phase 4a enforcement result, on a **fresh substrate built end-to-end for this test** and disjoint from
the 57-complex exploratory set. **N = 158 (the pre-registered ≥ 120 target is met.)**

## Substrate (built by the scripts in this repo)

`phase4_harvest.py` → `phase4_leakage.py` → `phase4_prep_predict.py` → Boltz-2 (`--use_msa_server`) →
`phase4_dockq.py` → `phase2_records.py`:

- Harvested 2000 post-cutoff hetero-complexes (RCSB, released ≥ 2025-07-01, resolution ≤ 3.5).
- **Strict leakage filter** (MMseqs2 `easy-search` of every chain vs the full PDB `pdb_seqres`, joined to RCSB
  release dates): a target is leakage-clean iff it has **no pre-cutoff (< 2023-06-01) homolog** at ≥ 30 %
  identity / ≥ 0.8 coverage. **161 / 2000 (8.1 %) survived.**
- **158** of the clean set were Boltz-2-predicted (`--use_msa_server --model boltz2`) and DockQ-scored
  (3 dropped on missing structure).

**N = 158. Genuine stakes: DockQ ≥ 0.49 base rate 60 % (95/158), DockQ range 0.005–0.902.**

### Headline that did NOT replicate — and that is the point of a confirmatory

On the exploratory 57, ipTM→DockQ Pearson was **+0.84**. On this **strictly** leakage-controlled set it is
**+0.57** (and on the first-75 subset, +0.41; not a resolution artifact — the res ≤ 3.0 subset is also +0.41).
The exploratory cue strength was optimistic; under strict leakage the specialist's interface confidence is only
**moderately** predictive of truth, and the v1-fit isotonic calibration transfers to the new set only partially
(Pearson(calibrated risk, actually-wrong) = **+0.49**). The confirmatory therefore tests the harder, more
honest question: **does enforcement still beat free-form LLM routing when the calibrated signal is weak?**

## Mechanisms & analysis

`run_phase4_confirmatory_llm.py` (free-form LLM, arms: clean calibrated card / inverted / corrupted-{invert,
shift,noise}+raw) → `run_phase4_confirmatory.py` (mechanisms + analysis). Held-out isotonic calibration fit on
the v1 DockQ-validation complexes; CRC conformal threshold calibrated on the **disjoint 57-complex set**
([`cal_risk_57.json`](cal_risk_57.json)); 3 models × 3 seeds; paired target-bootstrap 95 % CIs;
Holm–Bonferroni on the secondary family. Scores: [`confirmatory_scores.json`](confirmatory_scores.json).

## Results (N = 158)

| hypothesis | result |
|---|---|
| **H4.1 — enforced gate > free-form LLM** | **replicates, strongly.** gate − free-form **+0.15 / +0.15 / +0.17 (λ=0.5)** and **+0.30 / +0.30 / +0.33 (λ=0.8)**, all p ≈ 0, growing with λ as in 4a. The free-form LLM is the weak link (it over-verifies: at λ=0.8 it nets +0.20–0.24, far below even trust-all). |
| **H4.2 — manipulation-robust** | **replicates at moderate price.** under the inverted reliability cue the free-form LLM drops **+0.12 / +0.10 / +0.18 (λ=0.5, all p<.001)**; the gate computes from the raw signal and does not move. (At λ=0.8 the effect washes out — the LLM already over-verifies under any cue.) |
| **H4.3 — constraint is a no-op on net** | **replicates.** constrained − free-form = **+0.000** everywhere: the LLM over-verifies, it does not over-trust. |
| **conformal abstention** | beats free-form; realized false-accept **0.089 < α = 0.20**. *Caveat:* the transferred isotonic risk is **near-binary** (83 targets ≤ 0.5, 75 > 0.8, **none in between**), so the conformal threshold (τ̂ = 0.5) induces the **same trust/verify partition as the gate** — conformal is not an independent mechanism win here. And the CRC calibration set (the 57) is **not exchangeable** with the test set (wrong-rate 0.47 vs 0.40), so the distribution-free guarantee is approximate; the empirical bound nonetheless held. |
| **H4.4 — does the LLM recover under corruption?** | **no** (replicates). Under inverted / shift / noise corruption with the truthful raw signal present, the LLM follows the corrupted card and loses to the blind corrupted gate at λ ≥ 0.5 (opus λ=0.8: invert −0.32, shift −0.37, noise −0.22). Lone exception: opus, invert, λ=0.2 (+0.12) — a low-stakes corner. |

### The honest boundary the weak signal exposes

Because the transferred calibration is only moderately sharp (+0.49), at the **highest** verification price the
calibrated gate no longer beats the **naive trust-all baseline**: at λ=0.8, trust-all **+0.601** > gate
**+0.532** > free-form LLM **+0.20–0.24**. The gate still beats the LLM (H4.1), but neither beats trust-all —
verification is not worth its cost when the signal is this dull. At λ=0.5 the gate (**+0.674**) beats both
trust-all (+0.601) and verify-all (+0.500). **Enforcement's advantage over free-form LLM routing is robust to a
weak signal; its advantage over naive baselines is conditional on calibration sharpness relative to the price.**

## Caveats

- **Coarse transferred calibration.** The v1-fit isotonic maps the new set's confidences to a **near-binary**
  risk (bimodal at ≈ 0 and ≈ 1, nothing in (0.5, 0.8]). So the "calibrated gate" is here effectively a **hard
  ipTM/pLDDT threshold**, and the λ value does not change which targets are verified (only the cost charged).
  This does not weaken H4.1 — the LLM fails to match even this crude threshold — but "calibrated" should be read
  as "leakage-honest and validated-direction," not "finely graded," on the transferred calibration.
- **Conformal coincides with the gate** (above) and its CRC guarantee is approximate (non-exchangeable cal set).
- **Multi-interface DockQ:** 22/158 targets have > 1 native interface; the score is the tool's "Total DockQ over
  N interfaces" (all values stay ≤ 1, max 0.902), the same convention as the exploratory set.
- **opus uses 1 seed** (sonnet/gpt use 3); its per-target nets are single-sample.
- **Reproducibility:** the committed `records_confirmatory.json` + risk files + `run_phase4_confirmatory.py`
  regenerate `confirmatory_scores.json`, but the raw LLM episodes (≈ 5 MB jsonl) are kept out of the repo
  (gitignored, durable in the author's planning dir) — the scores are the tracked artifact, as in prior phases.

## Conclusion

On a fresh, strictly leakage-controlled substrate (N = 158) where the specialist's confidence is only
moderately calibrated (ipTM→DockQ +0.57, not the exploratory +0.84), the core enforcement findings
**replicate and strengthen**: a deterministic calibrated gate beats free-form LLM routing (highly significant at
λ ≥ 0.5, +0.15 → +0.33 growing with λ), is manipulation-robust at moderate price, and the LLM over-verifies and
fails to recover from a corrupted reliability channel even with cross-checkable evidence. Conformal abstention's
realised false-accept stays under α = 0.20 (0.089; approximately — the cal set is not exchangeable, and on the
near-binary transferred risk it coincides with the gate; see Caveats and `in_distribution/`). The boundary — that
calibrated verification beats naive baselines only when the signal is sharp enough for the price — is an honest
limit, not a failure of the enforcement thesis.

**Important robustness caveat** ([`in_distribution/`](in_distribution/README.md)): because the transferred
calibration is near-binary, we re-fit it in-distribution (graded risk) and re-ran the LLM. The gate − free-form
advantage is then **not unconditional** — given a *graded* card, capable models (Sonnet/GPT) stop over-verifying
(95 % → 36 %) and nearly match the gate at λ=0.5; the gate's edge persists only for the risk-averse over-verifier
(Opus) and at high price. The gate is *robust* to calibration granularity; the free-form LLM is *fragile* to it.
Read enforcement as **insurance against that fragility**, not an unconditional win. (Conformal also becomes a
genuinely independent mechanism under the graded calibration, τ̂ = 0.333 ≠ the price gate.)
