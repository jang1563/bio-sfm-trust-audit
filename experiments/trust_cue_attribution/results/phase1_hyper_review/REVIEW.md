# Phase 1 Hyper Review

Date: 2026-06-18
Review commit: `cd6044c`
Scope: Phase 1 scFoundation preflight, Phase 1A signal pilot, Phase 1A validity/granularity gates, and Phase 1B edge-signal design gate.

## Bottom Line

Phase 1 is not ready for a larger LLM matrix or a true-SFM interpretation claim. It is ready for a small HPC prototype of an edge-level scFoundation-derived cue.

The current best next route is `scfoundation_neighbor_edge_support`: use scFoundation embeddings to retrieve neighbor perturbation panels, then summarize same-readout-gene non-truth evidence per `(perturbation, readout_gene)` edge.

## Findings

### P0 - Phase 1A is not yet a true SFM-output benchmark

Phase 1A used GEARS calls/log2FC as the visible specialist-model output and added a scFoundation internal-signal-looking cue. This is valid for a trust-cue audit, but it is not yet a benchmark where scFoundation itself produces the actionable perturbation effect call.

Implication: claim only cue-sensitivity and design learning. Do not claim faithful scFoundation interpretation, true-SFM routing, or calibrated use of SFM internals.

### P0 - Current scFoundation panel card should not be scaled

The real scFoundation cue and shuffled placebo both improved net reward slightly versus no signal, but the placebo effect was close to the real effect:

- real signal delta net/gene: `+0.019048`
- placebo delta net/gene: `+0.015873`
- real minus placebo delta net/gene: `+0.003175`
- placebo fraction of real delta: `0.833333`

The current decision remains `do_not_scale_yet`.

### P0 - Panel-level signal is misaligned with edge-level reward

The reward/action unit is `(perturbation, readout_gene)`, but the Phase 1A scFoundation card was panel-level. All 12 selected panels mix correct and wrong GEARS genes:

- edge rows: `315`
- wrong/correct edges: `102 / 213`
- mixed correct-and-wrong panels: `12 / 12`
- best primary panel-level scFoundation AUROC for edge wrongness: `0.467366`
- edge-level baseline call-disagreement AUROC: `0.648785`

Implication: the next cue must vary across genes within a panel.

### P1 - The Phase 1B neighbor route is feasible, but not proven

The design gate shows strong readout-gene reuse:

- selected edges: `315`
- selected unique readout genes: `77`
- full panels available in the dry-run substrate: `107`
- selected edges with at least 10 other panels sharing the same readout gene: `302 / 315`, fraction `0.95873`
- median other-panel same-gene count: `58`

This supports an HPC prototype for `scfoundation_neighbor_edge_support`. It does not prove the neighbor signal predicts wrongness.

### P1 - The neighbor route must avoid becoming baseline-disagreement in disguise

The proposed neighbor cue includes non-truth summaries such as neighbor SFM-call agreement and neighbor baseline-disagreement rate. This is useful, but it creates a risk that apparent scFoundation value is actually driven by the already-known baseline-disagreement signal.

Required controls:

- embedding-neighbor signal
- random same-readout-gene neighbor control
- baseline-only edge control
- shuffled readout-gene signal
- panel-card control

### P1 - Full 107-panel scFoundation embedding coverage is not yet generated

Phase 1A generated scFoundation embeddings for 12 selected panels plus controls from the public Norman 2019 h5ad. Phase 1B feasibility uses GEARS panel/readout-gene reuse across 107 panels, but the full 107-panel embedding pool has not yet been generated locally.

Required next gate: verify Norman h5ad cell coverage and generate compact scFoundation embedding summaries for the full 107-panel pool before constructing neighbor evidence.

### P2 - Masked readout-gene prediction remains blocked

The official scFoundation smoke path verified embeddings, not a gene-level prediction or reconstruction output. A masked readout-gene prediction cue would be more directly task-aligned, but it should remain blocked until the model output path is verified.

## What Is Solid

- Public Norman 2019 h5ad is now the benchmark-facing Phase 1A source; local/unpublished FRAM2 is explicitly wiring-only.
- Cayuga environment can run the official scFoundation embedding path.
- Phase 1A generated panel-specific finite scFoundation embeddings: `[256, 3072]`.
- The 36-request Sonnet pilot completed with 36/36 episodes, 0 parse errors, and 0 provider errors.
- Validity and granularity gates now prevent premature scaling.
- Phase 1B has a concrete design artifact and model-visible schema for edge-level evidence.

## What Is Not Solid

- No scored Phase 1B edge-level LLM pilot exists.
- No full 107-panel scFoundation embedding pool exists yet.
- No evidence yet that scFoundation neighbor distance predicts GEARS wrongness.
- No evidence yet that Claude uses true scFoundation evidence more faithfully than shuffled/placebo evidence.
- No scFoundation-generated perturbation effect calls are being compared against held-out truth.

## Recommended Next Step

Build a Phase 1B HPC prototype with this order:

1. Generate full 107-panel scFoundation embedding summaries from public Norman 2019 h5ad.
2. Build neighbor evidence for selected 12-panel Phase 1A surface first.
3. Produce `edge_internal_signal_summary` per gene with no truth, correctness, reward, target raw assay stats, or scoring key.
4. Run leakage checks and within-panel variation checks.
5. Compute pre-LLM edge-level AUROC versus GEARS wrongness.
6. Only if the real edge signal beats the current panel-card AUROC directionally, create a small 4-condition LLM pilot:
   - `no_internal_signal`
   - `scfoundation_edge_neighbor_signal_shown`
   - `shuffled_readout_gene_signal_shown`
   - `panel_signal_card_control`

## Claim Boundary After Review

Current supported claim:

> Phase 1A shows that LLM routing is sensitive to scFoundation-looking internal-signal cues, but the current panel-level cue is not specific, not edge-granular, and should not be scaled. Phase 1B should move to readout-gene-specific, leakage-safe neighbor evidence before any larger LLM run.

Current unsupported claims:

- Claude faithfully interprets scFoundation internals.
- scFoundation panel distance is a calibrated reliability signal.
- Phase 1A is a true-SFM perturbation benchmark.
- Phase 1B has already demonstrated improved routing.
- The neighbor route is scientifically validated.
