# Phase 2 — pre-registered CONFIRMATORY pilot (hard-complex substrate)

The proper run the [illustrative pilot](../phase2_failure_substrate/) was not: it implements the
[pre-registration](../../PHASE2_PREREGISTRATION.md) on the leakage-controlled hard-complex
substrate (n = 14; DockQ ≥ 0.49 truth; ipTM/pLDDT cue). Fixes every deficiency the self-review
flagged. Run locally (keys never leave the machine). Artifacts: [`confirmatory_scores.json`](confirmatory_scores.json),
[`run_confirmatory.py`](run_confirmatory.py), [`score_confirmatory.py`](score_confirmatory.py).

**Design** (vs the illustrative pilot): **held-out calibration** (isotonic ipTM/pLDDT-risk →
P(DockQ < 0.49) fit on the **40 v1 complexes**, applied to the test set — not in-distribution
LOO); **6 arms** (adds a *competing-cue* arm: true confidence + a misleading high-authority
provenance); **3 seeds** (Sonnet & GPT-4.1 temperature draws 0.5/0.8/1.0; Opus single-run — it
rejects `temperature`); **λ-sweep** 0.2/0.5/0.8; **Holm-Bonferroni** over the secondary family,
with **H2 (interface vs raw) as the single confirmatory primary**.

## Results (paired target-bootstrap 95% CI, seed-aggregated)

**Primary — H2: calibrated_interface − raw_plddt (registered as a likely NULL):**

| λ | Sonnet 4.6 | GPT-4.1 | Opus 4.8 |
|---|---|---|---|
| **0.5 (primary)** | −0.02 [−0.19, +0.14] ns | −0.01 [−0.19, +0.18] ns | −0.11 [−0.39, +0.14] ns |
| 0.2 | +0.12 ns | +0.15 ns | +0.04 ns |
| 0.8 | −0.17 ns | −0.18 ns | −0.26 (p=.03, uncorr.) |

**At the primary λ = 0.5, H2 is NULL for all three models** — the calibrated reliability
*interface* does **not** beat raw confidence, **even with held-out calibration**. (The effect is
λ-dependent: the interface helps slightly when verification is cheap, hurts when it is expensive,
via over-verification — visible only because of the λ-sweep.)

**Secondary (Holm-Bonferroni corrected; 25/45 survive):**

- **H1 — raw − no_signal is SIGNIFICANT at λ = 0.8** (Sonnet **+0.34, p = .001**; GPT **+0.35,
  p = .005**; both survive Holm). Raw calibrated confidence **genuinely helps** over no signal
  when verification is costly — the project's **first statistically significant routing result**.
- **A4 — the benefit is informational, not directive:** `calibrated_interface` equals
  `calibrated_risk_no_recommendation` **exactly** (Δ = 0.000, Holm-sig). The recommended action
  adds nothing; the calibrated *number* is the whole effect.
- **Cue-following confirmed:** the inverted control is significantly worse than the calibrated arm
  (Δ −0.24…−0.33, Holm-sig).
- **A misleading authority cue does not override the numbers:** `competing_cue ≈ raw` (Δ +0.03…+0.06).

## Bottom line

A properly pre-registered, held-out-calibrated, multiplicity-corrected pilot **confirms the
project's headline and sharpens it**: the calibrated reliability **interface is not a free win**
(H2 null at the primary λ, robust to held-out calibration; A4 shows it is the information, not the
recommendation), while **raw calibrated confidence does significantly help** when verification is
costly (H1, Holm-robust). Presentation-layer interfaces add nothing over the raw number →
enforcement-based routing remains the motivated next lever.

**Caveats.** n = 14 (the H2 *null* is consistent-with, not proof-of, equivalence — a larger set
would tighten it; H1 *is* detected, so n = 14 carries real power for sizable effects); the held-out
isotonic from v1 is coarse; single MSA source; 11/84 Opus calls hit HTTP 529 (overload) → scored as
defer. A larger leakage-controlled hard-complex set (GPU) is the remaining lever for power.
