# Phase 2 Pre-Registration: Calibrated Reliability Interface vs Raw Confidence

Date: 2026-06-19
Status: PRE-REGISTRATION for the robust redo. The exploratory Phase-2-v1 run
(80 targets, Sonnet+Opus, RESULTS.md "Phase 2") is treated as pilot/exploratory;
its offline-gate PASS was engineered post-hoc and its calibration was fit
in-distribution. This document fixes the analysis BEFORE the confirmatory run so
the result is not a garden-of-forking-paths.

What v1 already established (and what carries in): the LLM routing findings are
cutoff-robust (lDDT 0.5-0.9; see `results/phase2_preflight/cutoff_robustness.json`)
-- so the post-hoc 0.9 cutoff is not driving the pilot conclusions, only the
offline gate's variance.

## Question (unchanged North Star)

Does converting a validated specialist-confidence signal into a calibrated
reliability *interface* improve an LLM's cost-aware trust routing OVER simply
showing the raw confidence -- and is that effect model-general?

## Pre-registered hypotheses (directional, from v1)

- H1 (expected SUPPORT): any confidence cue beats the no-signal baseline.
- H2 (expected NULL / model-dependent): the calibrated card does NOT beat raw
  pLDDT; specifically ~0 for Sonnet and NEGATIVE for a risk-averse model (Opus).
  This is the primary, confirmatory test -- registered as a likely null.
- H3 (expected SUPPORT): the benefit is informational, not directive -- the
  no-recommendation arm equals the full card (A4).
- H4 (expected SUPPORT): an inverted card degrades routing vs the calibrated card.

A confirmatory NULL on H2 is the headline; we are testing it honestly, not
hunting for a positive.

## Design (fixes the v1 caveats)

- Substrate: protein structure (Boltz-2 / pLDDT), post-training-cutoff targets.
- Targets: powered N with a LOWER base rate so routing has stakes -- include
  harder targets (e.g., recent CASP-hard / low-homology / larger complexes) so
  the specialist is wrong often enough; pre-specify N per regime by a power
  calculation for the H2 effect size, not a default.
- Correctness metric: lDDT VALIDATED against OpenStructure (monomers) + DockQ
  (complexes), not the home-grown CA-lDDT. Cutoff PRE-SET (lDDT>=0.7, the
  standard "modelable" threshold) with a full sensitivity sweep reported.
- Calibration: fit risk->P(wrong) on a HELD-OUT split (train calibration on a
  disjoint target set; never in-distribution LOO over the evaluated set).
- Arms (>=6): no_signal, raw_plddt_shown, calibrated_risk_shown_no_recommendation,
  calibrated_interface_shown, inverted_reliability_interface_control, and a NEW
  competing-cue arm (e.g., correct confidence paired with a misleading
  model-name/provenance cue) so "the LLM uses the signal" is not forced by the
  packet containing only confidence.
- Models: >=3 (e.g., Sonnet, Opus, Haiku and/or a non-Anthropic model), with
  repeated sampling (>=3 seeds/temperature draws) so cross-model differences get
  their own CIs.
- Reward: net = correct - lambda*assays; lambda sweep {0.2,0.5,0.8}; a REAL
  template/homology baseline for default_baseline (revive that action), not the
  current default-False placeholder.

## Analysis plan (pre-set)

- Primary contrast: calibrated_interface_shown vs raw_plddt_shown, per model,
  target-bootstrap 95% CI (seed 13, 1000 draws). Decision: SUPPORT only if the
  CI excludes 0 in the positive direction; otherwise report the null / negative.
- Secondary: each arm vs no_signal; A4 (card vs no_recommendation); inverted vs
  calibrated; monomer/complex split; lambda sweep.
- Disentangle the regime LABEL from the risk VALUE (regress verify on risk
  within regime) so "regime-appropriate caution" is not a label artifact.

## Success / failure framing (both publishable)

- If H2 SUPPORTED: calibrated interfaces help over raw confidence -- a
  presentation-layer win.
- If H2 NULL/NEGATIVE (expected): "prompt-visible reliability interfaces are not
  a robust lever over raw calibrated confidence and can backfire by model;
  presentation is insufficient -- enforcement (tools/MCP/post-training) is the
  next lever." This motivates Phase 4.

## Stop rules

- Do not re-pick the cutoff or calibration after seeing results.
- Do not add modalities/SFMs before this confirmatory run is scored.
- Report the template-baseline and lDDT-validation status explicitly; no claim
  rests on the home-grown metric.
