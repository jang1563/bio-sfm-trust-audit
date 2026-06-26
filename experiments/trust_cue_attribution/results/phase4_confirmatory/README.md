# Phase 4 — powered enforcement confirmatory (fresh strict-leakage substrate)

The pre-registered ([`../../PHASE4_PREREGISTRATION.md`](../../PHASE4_PREREGISTRATION.md)) confirmatory of
the Phase 4a enforcement result, on a **fresh substrate built end-to-end for this test** and disjoint from
the 57-complex exploratory set.

## Substrate (built by the scripts in this repo)

`phase4_harvest.py` → `phase4_leakage.py` → `phase4_prep_predict.py` → Boltz-2 (`--use_msa_server`) →
`phase4_dockq.py` → `phase2_records.py`:

- Harvested 2000 post-cutoff hetero-complexes (RCSB, released ≥ 2025-07-01, resolution ≤ 3.5).
- **Strict leakage filter** (MMseqs2 `easy-search` of every chain vs the full PDB `pdb_seqres`, joined to RCSB
  release dates): a target is leakage-clean iff it has **no pre-cutoff (< 2023-06-01) homolog** at ≥ 30 %
  identity / ≥ 0.8 coverage. **161 / 2000 (8.1 %) survived.**
- **75** of the clean set were Boltz-2-predicted (`--use_msa_server --model boltz2`) and DockQ-scored before
  the public ColabFold MSA server stalled; the run is resumable and the remaining 86 can extend N later.

**N = 75. Genuine stakes: DockQ ≥ 0.49 base rate 47 % (35/75), DockQ range 0.005–0.902.**

### Headline that did NOT replicate — and that is the point of a confirmatory

On the exploratory 57, ipTM→DockQ Pearson was **+0.84**. On this **strictly** leakage-controlled set it is
**+0.41** (and not a resolution artifact: the res ≤ 3.0 subset is also +0.41). The exploratory cue strength
was optimistic; under strict leakage the specialist's interface confidence is only **moderately** predictive.
The v1-fit isotonic calibration transfers to the new set only weakly (Pearson(calibrated risk, actually-wrong)
= **+0.39**). The confirmatory therefore tests the harder, more honest question: **does enforcement still beat
free-form LLM routing when the calibrated signal is weak?**

## Mechanisms & analysis

`run_phase4_confirmatory_llm.py` (free-form LLM, arms: clean calibrated card / inverted / corrupted-{invert,
shift,noise}+raw) → `run_phase4_confirmatory.py` (mechanisms + analysis). Held-out isotonic calibration fit on
the v1 DockQ-validation complexes; CRC conformal threshold calibrated on the **disjoint 57-complex set**
([`cal_risk_57.json`](cal_risk_57.json)); 3 models × 3 seeds; paired target-bootstrap 95 % CIs;
Holm–Bonferroni on the secondary family. Scores: [`confirmatory_scores.json`](confirmatory_scores.json).

## Results (N = 75)

| hypothesis | result |
|---|---|
| **H4.1 — enforced gate > free-form LLM** | **replicates.** gate − free-form **+0.07 / +0.07 / +0.09 (λ=0.5, all p<.04)** and **+0.17 / +0.17 / +0.20 (λ=0.8, all p≈0)**; ns at λ=0.2 (trust-all near-optimal). Advantage grows with λ exactly as in 4a. The free-form LLM is the weak link (over-verifies). |
| **H4.2 — manipulation-robust** | **replicates.** free-form net drops significantly under the inverted reliability cue (Holm-adjusted p ≈ 0); the gate computes from the raw signal and does not move. |
| **H4.3 — constraint is a no-op on net** | **replicates.** constrained − free-form = **+0.000** everywhere: the LLM over-verifies, it does not over-trust. |
| **conformal abstention** | beats free-form (matches the gate) **and meets its guarantee**: realized false-accept **0.107 < α = 0.20**. |
| **H4.4 — does the LLM recover under corruption?** | **no** (replicates). Under inverted / shift / noise corruption with the truthful raw signal present, the LLM follows the corrupted card and loses to the blind corrupted gate at λ ≥ 0.5 (e.g. opus λ=0.8: −0.18…−0.25). Lone exception: opus, invert, λ=0.2 (+0.14) — a low-stakes corner. |

### The honest boundary the weak signal exposes

Because the transferred calibration is weak (+0.39), at the **highest** verification price the calibrated
gate no longer beats the **naive trust-all baseline**: at λ=0.8, trust-all **+0.467** > gate **+0.392** >
free-form LLM **+0.220**. The gate still beats the LLM (H4.1), but neither beats trust-all — verification is
not worth its cost when the signal is this dull. At λ=0.5 the gate (**+0.580**) does beat both trust-all
(+0.467) and verify-all (+0.500). **Enforcement's advantage over naive baselines is conditional on calibration
sharpness relative to the verification price; its advantage over free-form LLM routing is not.**

## Conclusion

On a fresh, strictly leakage-controlled substrate where the specialist's confidence is only moderately
calibrated (+0.41, not the exploratory +0.84), the core enforcement findings **replicate**: a deterministic
calibrated gate beats free-form LLM routing (significantly at λ ≥ 0.5, growing with λ), is manipulation-robust,
and the LLM over-verifies and fails to recover from a corrupted reliability channel even with cross-checkable
evidence. Conformal abstention delivers its distribution-free guarantee. The new boundary — that calibrated
verification beats naive baselines only when the signal is sharp enough for the price — is an honest limit, not
a failure of the enforcement thesis. **N = 75 (MSA-server-limited from the pre-registered ≥ 120; extendable).**
