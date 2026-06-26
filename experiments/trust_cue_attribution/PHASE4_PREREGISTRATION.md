# Phase 4 Pre-Registration: Enforcement vs free-form LLM trust routing

Date: 2026-06-25
Status: PRE-REGISTRATION for the confirmatory enforcement study. The Phase-4a run
(`results/phase4_enforcement/`: N = 57 hard complexes + N = 34 antibody-antigen,
3 models, 3 seeds) is treated as exploratory; this fixes the design BEFORE the powered
confirmatory so the result is not a garden-of-forking-paths.

## Question

§4–§7b established that **presentation cannot produce calibrated, manipulation-robust
routing**: a general LLM shown a calibrated reliability signal routes worse than the raw
number (H2) and follows misleading framing (cue-following; Turpin et al. 2023). If the
decision cannot be fixed by *what the LLM is shown*, the next lever is to **enforce** it.

> Does taking the routing decision OUT of free-form LLM judgment — via a deterministic
> calibrated-risk gate / allowed-action constraint / conformal abstention — improve
> cost-aware routing, AND make it robust to manipulation of the reliability channel, over a
> fallible specialist scientific model? Where (if anywhere) does the LLM's reasoning still
> beat a mechanical gate?

Action set per item: `trust_sfm | verify_assay | default_baseline | defer`, under a
verification price λ; reward `net = correct − λ·assays`. Truth: DockQ (complexes) / lDDT
(monomers). Specialist signal: ipTM / pLDDT, held-out-calibrated to P(wrong).

## What Phase 4a established (carried in, directional priors)

- **H4.1 (SUPPORT):** a deterministic calibrated gate beats the free-form LLM (gate − LLM
  = +0.10…+0.37, all CIs exclude 0; delegation is costly).
- **H4.2 (SUPPORT):** the gate is manipulation-robust — under a misleading cue the LLM drops
  +0.06…+0.24 (significant) while the gate, computing from the raw signal, drops 0.
- **H4.3 (NULL, mechanistic):** forbidding over-trust is a no-op — the LLM *over-verifies*,
  it does not over-trust.
- **H4.4 (NULL, expected):** the LLM does **not** recover where the gate is challenged —
  on naturalistic OOD (antibody-antigen) the gate ties/wins, and under *adversarial*
  miscalibration the LLM follows the corrupted card even with the raw signal in hand.

The confirmatory tests these as registered predictions, not as a hunt for a positive.

## Pre-registered hypotheses

- **H4.1 (expected SUPPORT):** enforced gate net > free-form LLM net at λ ≥ 0.5; primary
  confirmatory contrast.
- **H4.2 (expected SUPPORT):** under a misleading / inverted / prompt-injected reliability
  cue, free-form-LLM net degrades significantly while gate / constrained net does not.
- **H4.3 (expected SUPPORT):** a constrained LLM (action masked to the gate-allowed set)
  recovers most of the gate's net while preserving the LLM for orchestration.
- **H4.4 (expected NULL):** no naturalistic regime where the LLM beats the gate; under
  adversarial calibration corruption the LLM does not recover using the cross-checkable raw
  signal (a sharper test of cue-following than Turpin 2023).

## Design (fixes the 4a caveats)

- **Substrate:** ≥ 120 leakage-controlled complexes (DockQ truth) spanning easy→failing
  (DockQ base rate ≈ 50% at ≥ 0.49), plus a held-out **antibody-antigen** OOD slice and a
  pre-specified **adversarial-corruption** condition (calibration inverted / shifted / noised).
- **Calibration:** held-out isotonic ipTM/pLDDT → P(wrong), fit on a disjoint complex set;
  never in-distribution LOO.
- **Enforcement mechanisms (pre-specified, compared head-to-head):**
  1. **Deterministic calibrated-risk gate** — verify iff calibrated P(wrong) > λ (trigger →
     predicate → enforce; cf. rule-based agent enforcement, AgentSpec 2026 / Progent 2025).
  2. **Allowed-action constraint** — the LLM reasons but its final action token is masked to
     the gate-allowed set (constrained decoding; Outlines, Willard & Louf 2023). Mask the
     **final action token only**, never the chain-of-thought (CRANE reasoning-tax caveat).
  3. **Conformal abstention** — a distribution-free abstention guarantee on a monotone
     false-acceptance loss (conformal risk control, Angelopoulos & Bates 2024; conformal
     abstention, Abbasi-Yadkori et al. 2024). Verify the loss is monotone in the threshold.
  - **Post-training (RL/RLAIF) is DEFERRED, with rationale:** an internalized policy is
    expected to remain promptable / cue-followable (the H2 failure), so it is not assumed to
    buy manipulation-robustness; it is registered as a *secondary, exploratory* arm only.
- **Baselines:** revive a **real template/homology `default_baseline`** (not the default-False
  placeholder), so "default to a cheap baseline" is a genuine action; trust-all; verify-all.
- **Models:** ≥ 3 (Claude Sonnet 4.6, Claude Opus 4.8, GPT-4.1, ≥ 1 further), ≥ 3 seeds.
- **Reward:** net = correct − λ·assays; λ-sweep {0.2, 0.5, 0.8}.

## Analysis plan (pre-set)

- **Primary:** gate − free-form-LLM net, per model, target-bootstrap 95% CI (seed 13, ≥ 1000
  draws). SUPPORT iff the CI excludes 0 in the positive direction.
- **Secondary:** manipulation degradation (free-form vs gate/constrained under the misleading
  / inverted / corrupted cue); constrained − free-form; conformal-abstention risk vs its
  guarantee; per-regime (general / OOD / adversarial); λ-sweep.
- **Multiplicity:** H4.1 (gate vs free-form, λ = 0.5) is the single confirmatory primary;
  the secondary family gets Holm–Bonferroni-adjusted intervals.
- **Boundary probe:** quantify whether the LLM ever beats the gate (H4.4); report the regimes
  where it does not, and the corruption severity (if any) at which a gate fails but reasoning
  recovers — the empirical edge of calibrated permissioning.

## Success / failure framing (both publishable)

- If H4.1/H4.2 SUPPORTED (expected): *enforcement — a deterministic calibrated gate — is the
  robust, manipulation-resistant trust layer; the routing decision should not live in
  free-form LLM text.*
- If H4.4 SUPPORTED anywhere (LLM beats the gate in a regime): that regime defines
  **calibrated permissioning** — enforce by default, defer to reasoning exactly where
  enforcement is unreliable.

## Stop rules

- Do not re-pick λ, the calibration split, or the corruption shape after seeing results.
- Freeze the leakage-exclusion list and the OOD / adversarial slices before scoring any LLM arm.
- Report the conformal guarantee's monotonicity/exchangeability preconditions explicitly;
  no claim rests on a violated precondition.

## Relation to prior work

Deterministic enforcement of agent actions is established for **security** policies — Progent
(Shi et al., arXiv:2504.11703) and AgentSpec (Wang et al., ICSE 2026) move the allow/block
decision out of free-form LLM judgment via symbolic rules; we adapt the pattern to a
**calibrated-risk** gate over a fallible scientific specialist. Constrained decoding (Outlines,
Willard & Louf 2023) and conformal risk control / abstention (Angelopoulos & Bates 2024;
Abbasi-Yadkori et al. 2024) supply the guarantee-bearing mechanisms. The nearest cost-aware
"trust vs escalate" cascade with a guarantee, *Trust or Escalate* (Jung et al., ICLR 2025),
routes an LLM-judge over its **own** preference for **human agreement**, not a router over a
fallible **non-LLM** specialist with a verification price and ground-truth correctness.
Agentic-science systems currently decide specialist-trust **naively** — fixed thresholds
(A-Lab, Szymanski et al., Nature 2023), LLM-judge self-evaluation (The AI Scientist, Lu et al.
2024; Google AI co-scientist, Gottweis et al. 2025), or human/wet-lab deferral — with no
calibrated, cost-aware, manipulation-robust gate; the closest analog, active-learning
acquisition (Settles 2009), is candidate *selection*, not a trust *gate*. Cue-following of
the reliability channel follows Turpin et al. (2023).
