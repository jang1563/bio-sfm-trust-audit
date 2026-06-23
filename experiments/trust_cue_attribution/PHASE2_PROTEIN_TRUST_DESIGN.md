# Phase 2 Design Sketch: Protein-Structure Trust Interface (Boltz-1 / pLDDT)

Date: 2026-06-19
Status: DESIGN SKETCH ONLY. No adapter built, no compute run, no LLM call. This
is the gate-first design proposal for re-basing the trust-audit from single-cell
perturbation onto a substrate where a *validated, calibrated* specialist signal
exists.

> Note: this dated sketch references **Boltz-1**; the executed Phase 2 run (see
> `../../REPORT.md`) used **Boltz-2** (same AlphaFold3-class family, MIT/open).
> The design and the calibration-gate logic are unchanged by that substitution.

## Why Re-base (Path 2 rationale)

The single-cell perturbation substrate fails BOTH conditions required to study
calibrated trust-routing, so Phase 1C could only ever produce another null:

- (i) the specialist does not beat the cheap baseline: GEARS/scGPT/scFoundation
  fail to beat a simple linear/additive model (Ahlmann-Eltze, Huber & Anders
  2025, *Nature Methods*; replicated in this repo's
  `specialist_metric_check.json`, additive 0.818 vs GEARS 0.677 on combos);
- (ii) no native calibrated uncertainty: the scFoundation edge-neighbor cue has
  AUROC 0.599 vs 0.576 random (near-noise); GEARS MC-dropout is miscalibrated.

Protein structure is the one modality that satisfies both, with independent
validation:

- (i) AlphaFold/Boltz beat template/homology baselines categorically on hard
  targets (CASP14: AF2 z-sum 244.0 vs 90.8 next-best), but NOT on easy
  high-homology targets, so "default to the cheap template" is genuinely correct
  sometimes -> non-trivial routing;
- (ii) pLDDT is the strongest validated, calibrated, model-emitted reliability
  signal in computational biology: designed to predict per-residue lDDT
  (Jumper et al. 2021, *Nature*), independently audited as calibrated for
  monomers (pLDDT<->quality r approx 0.97; McGuffin group, *Bioinformatics* 2024,
  btae491).

Design gift: calibration DEGRADES from monomers (r approx 0.97) to
multimers/complexes (r approx 0.67, overconfident on low-quality models). That
gap is built-in routing stakes; we do not need to manufacture a discriminative
surface.

## North Star (restated for this substrate)

```text
structure prediction + calibrated confidence (pLDDT/PAE/pTM/ipTM) + verification cost
  -> LLM action: trust_sfm / verify_assay / default_baseline / defer
  -> reward under held-out experimental structure truth
```

The decisive POSITIVE-result question (impossible to ask on single-cell):

> When the specialist signal is genuinely calibrated, does the LLM track its
> regime-dependent reliability -- trusting confident monomer predictions and
> verifying/deferring on overconfident complex predictions -- or does it remain
> cue-sensitive (responding to framing rather than calibrated risk)?

## Decision Unit

- `panel` = one prediction target (a protein, or a complex).
- `edge` = the scored sub-unit. Pilot: one edge per target (whole-structure
  trust). Granular extension (mirrors Phase 0 panel->edge): per-domain
  (per-residue pLDDT) and per-interface (PAE/ipTM) edges.
- Start per-target for the pilot; add per-interface edges only after the
  per-target gate passes.

## Specialist + Baseline

- Specialist: Boltz-1 (MIT, open, reproduces AF3; emits pLDDT, PAE, pTM, ipTM,
  complex_plddt). Cayuga/Expanse GPU.
- Cheap baseline: best available template/homology model (e.g., top PDB template
  by sequence identity, or a fast homology build). This is the structure-side
  analog of the additive baseline.
- Criterion (i) holds non-trivially: Boltz beats the template baseline on
  hard/low-homology targets but not on easy ones, so `default_baseline` is the
  correct action in a real, non-empty subset.

## Calibrated Reliability Card (model-visible)

The card is the same shape as Phase 1C, but the signal inside it is VALIDATED:

```json
{
  "reliability_interface": {
    "regime": "monomer | complex",
    "risk_bucket": "low | medium | high",
    "estimated_wrong_risk": 0.0,
    "recommended_action": "trust_sfm | verify_assay | default_baseline",
    "evidence_basis": ["mean_plddt", "interface_pae", "ptm_iptm", "regime"],
    "calibration_status": "validated_monomer_calibrated_complex_degraded"
  }
}
```

Note the honest `calibration_status`: a real, regime-aware calibration label,
in contrast to Phase 1C's `offline_gate_not_biology_calibrated`.

## Actions + Reward (schema unchanged)

- `trust_sfm` = accept the predicted structure/interface.
- `verify_assay` = obtain experimental/orthogonal validation (guaranteed
  correct; cost lambda). This is the "assay" -- experimental structure
  determination is the authentic costly action.
- `default_baseline` = use the cheap template/homology model (correct iff the
  template is good).
- `defer` = abstain.

```text
net_reward = correct - lambda * assays      (lambda in {0.2, 0.5, 0.8})
```

- `correct` = predicted vs held-out experimental structure within a threshold:
  monomer lDDT >= 0.7 (or TM-score >= 0.5); complex DockQ >= 0.23 (acceptable).
  Thresholds fixed and reported; sweep as sensitivity.
- Truth from held-out experimental structures (see leakage controls).

## Cue Conditions (trust-routing matrix)

Mirrors Phase 0/1C controls, but now with a valid signal AND a fix for the A4
information-vs-compliance confound:

- `no_signal` -- structure only, no confidence.
- `raw_plddt_shown` -- raw per-residue/global confidence numbers.
- `calibrated_risk_shown_no_recommendation` -- the calibrated risk bucket /
  number, but NO recommended_action. (NEW: decouples "used the calibration"
  from "obeyed the card" -- directly addresses critique A4.)
- `calibrated_interface_shown` -- full card: risk + recommended_action.
- `inverted_reliability_interface_control` -- negative control (intentionally
  inverted card); tests blind card-following.
- optional: `regime_hidden` vs `regime_shown`; `model_name_shown` vs
  `anonymized` (reuse Phase 0 provenance-cue logic).

The decisive contrasts:

1. Does `calibrated_interface_shown` beat both `no_signal` and `raw_plddt_shown`
   on net reward? (Can the LLM convert a validated calibrated signal into better
   routing?)
2. Does `calibrated_risk_shown_no_recommendation` capture most of that gain?
   (If yes -> the LLM uses the calibration; if the gain only appears with the
   recommendation -> it is obeying the card, not calibrating. A4 resolved.)
3. Does `inverted_reliability_interface_control` dominate behavior? (If yes ->
   blind compliance, not calibration.)

Both outcomes are publishable: a positive result supports the calibrated-trust
interface thesis; a negative result is the stronger claim that even a validated
calibrated signal is insufficient without enforcement (tools/MCP/post-training).

## Offline Deterministic Gate (before ANY LLM call)

Same discipline as Phase 1C. Do not spend API until all pass:

1. Calibrated-signal validity: AUROC(pLDDT-derived risk vs structure-wrong) on
   held-out truth. Expectation: clears decisively (pLDDT IS calibrated), UNLIKE
   scFoundation's 0.599. If it does not clear, stop -- the substrate assumption
   was wrong.
2. Regime gap: reproduce monomer (r approx 0.97) vs complex (r approx 0.67)
   calibration, to confirm the routing stakes exist.
3. Deterministic reliability policy (threshold on calibrated risk) beats
   trust-all, default-all-template, and shuffled/inverted controls on net reward
   -- AND the real-vs-shuffled gap is LARGE (not the 0.003 of Phase 1C).
4. Power: pre-specify n_targets via a power argument for the planned contrast
   sizes (fix critique A3 -- no default n=12). Public targets are abundant
   (weekly CAMEO, recent PDB), so scaling is cheap.

Gate decision -> only then build cue packets + a small LLM pilot.

## Leakage Controls (one NEW axis vs Phase 0/1)

- Hidden: experimental truth (lDDT/DockQ), correctness flags, reward, the
  held-out experimental structure.
- Model-visible: predicted structure summary, pLDDT/PAE/pTM/ipTM, regime, the
  calibrated card.
- NEW leakage axis -- training-set memorization: the specialist may have seen
  the target during pretraining, so its confidence is not a fair test. Use only
  targets released AFTER the model's training cutoff (post-cutoff CAMEO / recent
  PDB). This is the structure-domain analog of the held-out-truth rule and must
  be enforced in the truth inventory.

## How This Fixes The Critique

- A1 / A7 (signal is near-noise): pLDDT is validated-calibrated; gate check 1
  should pass cleanly with high AUROC instead of 0.599.
- A2 / A8 (flat surface / straw-man specialist): Boltz beats the template
  baseline on hard targets but not easy ones (real routing stakes); the
  monomer/complex calibration gap supplies dynamic range.
- A3 (underpowered): pre-specified n via power; abundant public targets make
  scaling cheap.
- A4 (information vs compliance unidentifiable): the
  `calibrated_risk_shown_no_recommendation` arm decouples using-the-calibration
  from obeying-the-card.

## Claim Boundary

This tests LLM routing over a calibrated structure-confidence signal. It does
NOT claim: that Boltz/AF internal representations are interpreted; that pLDDT is
calibrated for all complex classes; that the result generalizes to all SFMs; or
that the LLM is a calibrated orchestrator in general.

## Gate-First Preflight Artifacts (deliverables, in priority order)

1. `results/phase2_preflight/boltz_contract.json` -- adapter contract
   (required_inputs, standardized_outputs, evidence_fields,
   internal_signal_fields, hidden_fields, preflight_checks, claim_boundary).
2. `results/phase2_preflight/structure_truth_inventory.json` -- held-out
   post-cutoff targets, leakage check, n / power statement.
3. `results/phase2_preflight/calibration_gate.json` -- gate checks 1-4 above.
4. Only if the calibration gate passes: cue packets + a small, power-justified
   LLM pilot, scored on the same actions/reward/cue-attribution/robustness stack.

Everything downstream of the adapter -- panels -> cues -> actions -> reward ->
scoring -> cue-attribution -> robustness -- transfers unchanged from Phase 0/1
(the adapter contract is modality-agnostic by design). Only the adapter and the
dataset are new.

## Positioning (for the eventual paper)

- Extends Turpin et al. 2023 (LLMs follow truth-orthogonal cues) into the
  unoccupied composition: LLM trust-routing over a fallible *scientific*
  foundation model under explicit verification cost (Agent-confirmed open gap;
  nearest priors ASPEST 2023, Adaptive-RAG, xRouter).
- Novel artifact: a specialist-emitted, agent-consumed calibrated reliability
  card -- now backed by a validated signal (pLDDT), unlike Phase 1C.
- Key cite ladder for the substrate: Jumper 2021; McGuffin 2024 (calibration
  audit); Abramson 2024 (AF3); Cheng 2023 (AlphaMissense, runner-up substrate);
  Ahlmann-Eltze 2025 (why single-cell was the wrong substrate).
