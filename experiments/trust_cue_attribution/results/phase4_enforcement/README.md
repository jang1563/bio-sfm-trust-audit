# Phase 4 — enforcement-based trust routing

The audit established that **presentation cannot fix routing**: a general LLM shown a calibrated
reliability signal routes worse than the raw number and follows misleading framing (cue-following,
à la Turpin et al. 2023). Phase 4 takes the routing decision **out of free-form LLM judgment** and
**enforces** it, then asks whether that helps, is manipulation-robust, and where (if anywhere) the
LLM's reasoning still beats a mechanical gate.

Substrate: the N = 57 leakage-controlled hard-complex set (DockQ truth, held-out isotonic
ipTM/pLDDT→P(wrong) calibration fit on the v1 complexes). Conditions:

- **C1 free-form LLM** — the LLM chooses the action given the calibrated card.
- **C2 enforced gate** — deterministic: verify iff held-out calibrated risk > λ, else trust (no LLM).
- **C3 constrained LLM** — C1 but forbid over-trust (trust→verify when risk > λ).
- **C4 manipulation** — C1 under an inverted/misleading reliability cue.
- **C5 OOD** — antibody-antigen complexes, where ipTM→DockQ degrades (n = 34).
- **Adversarial** — corrupt the calibration (risk→1−risk); the blind `gate_corrupted` applies the
  threshold to the inverted risk, while the LLM (`corrupted_plus_raw`) sees the inverted card **and**
  the truthful raw ipTM/pLDDT, so it could cross-check.

3 models (Claude Sonnet 4.6, Claude Opus 4.8, GPT-4.1), 3 seeds, λ-sweep, paired target-bootstrap
95% CIs. Scores: [`enforcement_scores.json`](enforcement_scores.json), [`c5_ood_scores.json`](c5_ood_scores.json).

## Results

| finding | result |
|---|---|
| **H4.1 — enforced gate > free-form LLM** | gate − free-form **+0.105 / +0.105 / +0.193** (λ=0.5), **+0.242 / +0.242 / +0.372** (λ=0.8); all CIs exclude 0. Delegating the decision to the LLM costs net **−0.10…−0.37**, growing with λ and model risk-aversion. |
| **H4.2 — enforcement is manipulation-robust** | under the misleading cue the free-form LLM drops **+0.06…+0.24 (all significant)**; the gate/constrained conditions drop **0** — they compute the action from the raw signal and never read the prompt framing. |
| **H4.3 — constraint nuance** | forbidding over-trust is a no-op on net: the LLM **over-verifies**, it does not over-trust (consistent with the H2 over-verification result). |
| **C5 — gate is robust out-of-distribution** | on antibody-antigen, ipTM→DockQ falls 0.84→**0.61** (mild miscalibration) but the general-fit gate stays within ~0.03 of the in-regime *oracle* gate and still beats trust-all; gate **ties** the LLM at λ=0.5 and **significantly wins** at λ=0.8. |
| **Adversarial — the LLM does NOT recover, even with the raw signal present** | under corrupted calibration, `LLM_corrupted_plus_raw − gate_corrupted` = **−0.09 / −0.11 / +0.06** (λ=0.5) and **−0.24 / −0.24 / −0.18** (λ=0.8, all significant negative): the LLM **follows the corrupted reliability card** even though the truthful ipTM sits in the same packet to contradict it. |

## Conclusion

Across **every regime tested** — general complexes, naturalistic OOD (antibody-antigen), and
adversarial miscalibration with cross-checkable evidence — **free-form LLM routing never beats
enforcement**, and the LLM follows a corrupted reliability signal even when it has the means to detect
the manipulation. The "defer-to-reasoning" hybrid case did not materialise anywhere; the LLM is the
weak link in all regimes. **A deterministic, calibrated, enforced gate is the robust and
manipulation-resistant trust layer; the routing decision should not be held in free-form LLM text.**
This sharpens Turpin et al. (2023): cue-following persists even when disconfirming evidence is
available to the model.

## Relation to prior work

Deterministic enforcement of LLM-agent actions is established for **security** policies — Progent
(Shi et al., arXiv:2504.11703) and AgentSpec (Wang et al., ICSE 2026) take the allow/block decision
out of free-form LLM judgment via symbolic rules, cutting indirect-prompt-injection attack success
rates dramatically. Constrained decoding (Outlines, Willard & Louf 2023) and conformal risk control
(Angelopoulos & Bates, ICLR 2024; conformal abstention, Abbasi-Yadkori et al., NeurIPS 2024) give
guarantee-bearing gates. The nearest cost-aware "trust vs escalate" cascade with a guarantee,
*Trust or Escalate* (Jung et al., ICLR 2025), routes an LLM-judge over its **own** preference for
**human agreement**, not a router over a fallible **non-LLM scientific specialist** with a
verification price and **ground-truth** correctness. Structure-prediction confidence is gated in
practice by **fixed, uncalibrated** thresholds (pDockQ — Bryant et al. 2022; DockQ ≥ 0.23 — Basu &
Wallner 2016; AlphaFold-Multimer — Evans et al. 2021) and is regime-dependently miscalibrated
(antibody-antigen — Genz et al. 2025; fold-switching — Chakravarty & Porter 2024). Phase 4's
contribution — a **calibrated-risk enforced gate over a fallible specialist scientific model with
manipulation-robustness as the explicit objective** — occupies the unfilled cell.

## Caveats

n = 57 (general) / 34 (Ab-Ag); held-out isotonic calibration is coarse; single MSA source; the gate's
"immunity" is *computes the action from the raw signal, does not read the prompt framing* — not magic,
and its input signal could itself be spoofed upstream. The adversarial test inverts the calibration;
other corruption shapes (shift, noise) are untested.
