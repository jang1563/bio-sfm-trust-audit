# Robustness: in-distribution (graded) calibration — tempers the H4.1 headline

The pre-registered primary used calibration **transferred** from the v1 complexes, which mapped the new set's
confidences to a **near-binary** risk (§ parent README). That degeneracy had two consequences worth testing: the
"calibrated gate" was effectively a hard threshold, and conformal coincided with it. This robustness arm re-fits
the calibration **in-distribution** to get a graded risk, then asks what changes.

## Setup

Split the 158 leakage-clean complexes (seeded, stratified by DockQ-correct/wrong) into **cal = 52 / test = 106**.
Fit isotonic on the cal split → a **graded** risk for the test split (7 distinct levels, with a populated
(0.2, 0.5] band — vs 4 near-binary levels under transfer). Re-run the free-form LLM on the 106 test targets with
the **graded cards** (3 models × 3 seeds), and calibrate the CRC conformal threshold on the cal split (now
**exchangeable** with test). Scores: [`confirmatory_scores_indist.json`](confirmatory_scores_indist.json).

## What changes

1. **Conformal is now a genuinely independent mechanism.** The CRC threshold is **τ̂ = 0.333** (not 0.5), so
   conformal selects a *different* operating point than the price gate — conformal net ≠ gate net for all models
   (e.g. λ=0.5: conformal +0.641 vs gate +0.651). Its realized false-accept is **0.208 ≈ α = 0.20** (marginally
   over the target — honest finite-sample slack on n = 106, with an exchangeable but small cal set).

2. **H4.1 (gate > free-form LLM) shrinks sharply for capable models — it was partly a calibration artifact.**
   On the **same 106 targets**, the free-form LLM's behaviour depends strongly on the card:

   | calibration shown to the LLM | free-form net (λ=0.5) | verify rate |
   |---|---:|---:|
   | transferred, **near-binary** card | +0.524 | **95 %** (massive over-verification) |
   | in-distribution, **graded** card | +0.627 | **36 %** |

   With a graded card, capable LLMs (Sonnet 4.6, GPT-4.1) **stop over-verifying** and nearly match the gate:
   gate − free-form at λ=0.5 falls to **+0.008 (ns) / +0.002 (ns) / +0.141 (opus, p<.001)**. The gate's edge
   **persists** only for the risk-averse over-verifier (Opus 4.8, all λ) and at the **highest price**
   (λ=0.8: +0.048 / +0.018 / +0.379, all significant). The **gate net is essentially unchanged** across the two
   calibrations (~+0.65) — the gate is *robust* to calibration granularity; the free-form LLM is *fragile* to it.

## Honest revised conclusion

Enforcement does not *unconditionally* beat free-form LLM routing. A deterministic calibrated gate is a **robust**
policy (near-optimal whether the calibration is crude or graded); a free-form LLM is **fragile** — under a
crude / poorly-transferred reliability signal it over-verifies catastrophically (95 %) and the gate wins by a
wide margin, but given a **graded** signal a capable model recovers most of that gap. Enforcement's value is
therefore best stated as **insurance against the LLM's fragility**: it pays off most exactly where deployments
are most exposed — imperfect or transferred calibration, risk-averse models, and high verification cost. The
manipulation-robustness and over-verification (not over-trust) findings are unaffected; what this tempers is the
*size and universality* of the gate-vs-LLM net advantage under good calibration.
