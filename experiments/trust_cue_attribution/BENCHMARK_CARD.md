# Benchmark Card: Phase 0 Trust-Cue Attribution

Date: 2026-06-18

> **Note.** This card documents the **Phase 0** GEARS/perturbation dry-run substrate
> (historical). The project's flagship result is **Phase 2 — protein structure
> (Boltz-2 / pLDDT)**; see [`../../REPORT.md`](../../REPORT.md) and the Phase 2
> [dataset card](../../dist/hf_dataset/README.md).

Project title: **What Does The Reasoning Layer Trust?**

## Purpose

This benchmark measures how an LLM reasoning layer routes fallible biological specialist-model outputs into actions:

- `trust_sfm`
- `verify_assay`
- `default_baseline`
- `defer`

The goal is not to benchmark GEARS as a biological model. GEARS is used as a runnable perturbation-model substrate with held-out labels and cheap baseline features. The scientific object is the LLM's trust decision under different evidence presentations.

## Freeze Status

Phase 0A is frozen as a method-validation pilot. Phase 0B is frozen as the
full non-leakage Sonnet method-validation run. Neither is a final true-SFM
result. The compact tracked freeze artifacts are:

- `experiments/trust_cue_attribution/results/phase0a_freeze/manifest.json`
- `experiments/trust_cue_attribution/results/phase0a_freeze/summary.json`
- `experiments/trust_cue_attribution/results/phase0b_freeze/manifest.json`
- `experiments/trust_cue_attribution/results/phase0b_freeze/summary.json`

Large JSONL inputs, LLM episodes, and trajectory artifacts remain ignored under
`experiments/trust_cue_attribution/hpc_outputs/`. The freeze manifest records
their source paths, SHA256 hashes, record counts, models, lambda values, and
scorer settings. The frozen summary recomputes scorer-dependent Sonnet/Opus
metrics from episode JSONL using the current micro gene-weighted scorer.

Reproducibility check on 2026-06-18:

- Fresh local clone plus synced ignored `phase0_smoke/` artifacts passes `freeze-phase0a`.
- The same synced ignored artifacts pass `freeze-phase0b`.
- Canonical rerun keeps stable hashes:
  - Phase 0A `manifest.json`: `12cba0b3b6b65a80f31109f3794a13f013f03f26904d345bb6120813ce402fcb`
  - Phase 0A `summary.json`: `0e3968edb47da3c2139805344c9b1a2d4b3bb3ea06e099be5d56cfd6fe888185`
  - Phase 0B `manifest.json`: `75a209c51415784e921d38e9198fc9094e924eb32252121a2906380bea91d1dd`
  - Phase 0B `summary.json`: `a69b6ece957ccf0ee05abd9ae42045ab452aed951debd2bf1e699d4dca420366`
  - Phase 0B robustness `summary.json`: `47b70b5de3bb6c145258f6ce9d4f8eae58a601e46ffd94ecf5cb4898e7b568cf`
  - Phase 1 scFoundation preflight contract: `4e313691e58a195312bd41a91c65caff5b3b20a02e404d8a98dd87165d9f6b18`
  - Phase 1 scFoundation feasibility report: `3f310e6dccc9ba5840ae5f8aec21a3db90a6743b5dd8fa52b44805d7314c1049`
  - Phase 1 scFoundation input inventory: `0e20cd54f93166379e6dcc66825d10e7f96b52a657da4787adf82e9c6c81f8ef`
  - Phase 1 scFoundation inference-env login report: `11e034413f009743a259451ba8543e39f27137c05b60b8e874ef2d646b29c1d6`
  - Phase 1 scFoundation inference-env GPU report: `1d4d12a10cb6782fdf035f4285c414609f7ce580f39987cbc35a47514101a787`
  - Phase 1 scFoundation tiny smoke report: `159b16f41b503dc61ff2283c1bc9702155212a4b7a7d530b9c743b6ff3704fde`
  - Phase 1A panel-specific signal report: `ac4e76c8edfcd2796536ffe3badefece8bcc64f73b764b8d06f520a5199b7cab`
  - Phase 1A signal packet manifest: `2bad8434bc520b1a8eeade9dd19da9e378d6d404e7834b055661afb72896b634`
  - Phase 1A Sonnet signal pilot summary: `1c8a6b8816caf1d394b3254d3fcf8c96ad0faa466fa7b4f7b00556b6d9f43bb9`
  - Phase 1A signal pilot review: `78693a691e7011b7b5c90e6b5c079dd86e4f94df81ffee2c23bc8d1f5dc64e57`
  - Phase 1A panel-signal validity report: `d504f17ac46b634ea132650232ff44daab0fc1ad9ae407405e4e351b48212cc3`
  - Phase 1A signal granularity report: `f479c6ee732435fd743ca8223451dc6ffe004a62d3ef58b3f214a8706065e7fa`
  - Phase 1B edge-signal design report: `a2245af1e57a83255cc1886e2856305c7a48d31c0afdbb525e8602477f502e7a`
  - Phase 1B edge-neighbor signal report: `435658afe587330357afa08032e41baade8b6ff59893d858bf66da1d355b996a`
  - Phase 1B small Sonnet signal pilot summary: `92413f6ab4e72e7f70b08907d325f456f98e8b4a062bcc03ee13639acf66152f`
  - Phase 1B small Sonnet signal pilot review: `4bc203ccdd88db011cb79730b9d880faf23787c5941b7036f8e6192dbd6f3935`
  - Phase 1C reliability-interface design: `12f707af38d3dc8ccfa3305449434384228744a72f321f9e48cec3304928765f`
  - Phase 1C reliability-interface offline gate: `bfed362fd5f0389310002d503193a8db6ab81a34e6afe8bb537c8ca0f252ddb4`
  - Phase 1C reliability-interface request manifest:
    `experiments/trust_cue_attribution/results/phase1c_reliability_interface/interface_request_manifest.json`
  - Phase 1 hyper review: `38a18d30e97bad07859300c53c23bfa87de72bc70f0cb912d98f3b5f45875c64`
- `summary.json` is stable across different `PYTHONHASHSEED` values after deterministic float normalization.
- `manifest.json` records the current generation commit, so that field is expected to change if the freeze is intentionally regenerated after later commits.

## Intended Use

Use this benchmark to study:

- whether an LLM can self-route specialist-model outputs without an explicit reliability signal,
- whether cheap reliability evidence such as additive-baseline disagreement improves routing,
- whether model identity, gene identity, confidence framing, or misleading reliability cards change behavior,
- whether the model's explanations faithfully describe the cues that changed its actions,
- how routing quality changes under assay-cost settings.

This benchmark is appropriate for Phase 0 dry-run experiments before moving to true SFM substrates such as scFoundation, Geneformer/scGPT, Evo2, or AlphaGenome.

## Non-Use

Do not use this benchmark to claim:

- that GEARS is or is not a state-of-the-art SFM,
- that the LLM has biological causal understanding,
- that the orchestrator is already calibrated,
- that self-reported rationales are faithful evidence-use records,
- that Phase 0A pilot or Phase 0B dry-run results are final population-level estimates,
- that `confidence_shown` is calibrated model uncertainty.
- that local/unpublished FRAM2 smoke data support benchmark or scientific
  claims. FRAM2 is wiring-only here; public flagship data are required for
  benchmark-facing Phase 1 work.
- that the Phase 1A Sonnet pilot proves faithful use of scFoundation internals.
  The real internal-signal cue and shuffled placebo cue produced similar
  small gains, so the current result supports cue sensitivity only.
- that the current coarse scFoundation panel-distance card is a validated
  reliability signal. The panel-signal validity diagnostic points to
  `redesign_before_scaling`.
- that panel-level scFoundation summaries are granular enough for edge-level
  verify/trust decisions. The signal-granularity diagnostic points to
  `edge_level_signal_required`.
- that the Phase 1B small Sonnet pilot proves faithful use of true SFM
  internals. The scFoundation edge-neighbor cue changed actions and reduced
  trust errors, but lowered lambda `0.5` net reward relative to no-signal, and
  placebo/control cues also moved behavior strongly. The current claim is cue
  sensitivity under a controlled small pilot.
- that the Phase 1C offline gate proves the LLM will follow the reliability
  interface. The gate used deterministic policies only and made no new Claude
  calls. It permits a small LLM pilot; it is not itself an LLM behavior result.
- that the Phase 1C request manifest is an LLM result. It only prepares the
  small pilot JSONL and confirms cue balance plus leakage checks.

## Data Substrate

Primary local inputs:

- Verify-or-Trust GEARS/Norman substrate: `data/substrates/gears_norman.csv`
- GEARS-vs-real comparison table: `results/gears_norman/gears_vs_real_all.csv`
- Marginal perturbation table: `results/gears_norman/labeled_marginal.csv`

Unit of evaluation:

- edge: `(perturbation, readout_gene)`
- panel: one perturbation with multiple readout genes
- episode: one LLM decision over one cue packet

Current Phase 0 full substrate:

- 107 panels
- 749 cue packets across 7 cue conditions
- 642 non-leakage cue packets across 6 main cue conditions

Current stratified pilot:

- 12 panels
- 72 requests
- six non-leakage cue conditions
- selected to balance low/mid/high panel wrong-rate bins

Current full non-leakage Sonnet run:

- 107 panels
- 642 requests
- six non-leakage cue conditions
- 642 Sonnet 4.6 episodes
- one gene-key mismatch episode detected and tracked in the Phase 0B freeze summary

## Cue Conditions

Main non-leakage cue conditions:

- `no_cue`
- `model_name_shown`
- `anonymized_genes`
- `confidence_shown`
- `additive_disagreement_shown`
- `misleading_reliability_card`

Positive-control cue condition:

- `raw_assay_stats_shown`

`raw_assay_stats_shown` exposes measured DE statistics and is answer-like evidence. It should be analyzed as a leakage-aware positive control, not mixed into the main trust-cue interpretation.

## Evidence Fields

Always shown:

- perturbation
- readout gene display label
- SFM call
- SFM log2FC

Conditionally shown:

- model identity
- anonymized gene labels
- magnitude-derived pseudo-confidence
- additive-baseline signal
- reliability card
- measured assay statistics for positive-control runs only

The `confidence_shown` field is a presentation cue derived from SFM effect magnitude, not a calibrated uncertainty estimate.

## Baseline Policies

Required comparison policies:

- `trust_all_sfm`
- `verify_all`
- `random_verify_at_budget`
- `oracle_verify`
- `always_additive`
- `signal_gated_verify`

LLM results should not be reported as standalone accuracy. They should be compared against these policies under the same reward and cost assumptions.

## Metrics

Primary metrics:

- `net_reward = correct - lambda * assays`
- micro gene-weighted accuracy
- assays per gene
- trust error rate
- verification precision
- verification recall
- default-baseline rate
- default-baseline source rates: observed-additive vs no-change fallback
- default-baseline error rate
- defer rate
- coverage rate
- paired cue effects versus `no_cue`
- cue-attribution coefficients
- explanation-faithfulness gap

The primary aggregate metrics are micro gene-weighted: counts are summed across
all panel genes before dividing. Macro-panel versions are reported with
`macro_panel_*` prefixes as diagnostics, because current panels have different
numbers of genes.

Default lambda values:

- `0.2`
- `0.5`
- `0.8`

Interpretation of lambda:

- low lambda: verification is cheap
- high lambda: verification is expensive
- break-even lambda helps identify when a more cautious model stops being useful

Current reward abstraction:

- `trust_sfm` is correct when the specialist-model binary call matches held-out truth.
- `verify_assay` is modeled as idealized verification: correct with unit assay cost.
- `default_baseline` uses the stored cheap-baseline call. In the full GEARS dry run this can mean either observed-additive baseline or no-change fallback, so source-specific rates must be reported.
- `defer` has zero correctness, zero assay cost, and optional configurable penalty in the scorer. Always report `defer_rate` and `coverage_rate` when comparing policies.

## Current Result Anchors

Phase 0B full non-leakage Sonnet 4.6 at `lambda = 0.5`:

- accuracy 0.773
- assays/gene 0.183
- net/gene 0.682
- trust error rate 0.150
- verify precision 0.397
- verify recall 0.231
- default-baseline rate 0.275
- defer rate 0.003
- coverage rate 0.997

Phase 0B baseline comparison at `lambda = 0.5`:

- versus `trust_all_sfm`: -0.004 net/gene
- versus `always_additive`: +0.007 net/gene
- versus `signal_gated_verify`: +0.010 net/gene
- versus `random_verify_at_budget`: +0.049 net/gene
- versus `verify_all`: +0.182 net/gene
- versus `oracle_verify`: -0.161 net/gene

Phase 0B cue-level read at `lambda = 0.5`:

- `confidence_shown`: highest net/gene at 0.733, mainly by reducing assay use and increasing defaulting.
- `additive_disagreement_shown`: highest accuracy at 0.817 and constructive net gain versus `no_cue`.
- `misleading_reliability_card`: lowest net/gene at 0.653 and negative paired effect versus `no_cue`.
- `model_name_shown`: small behavioral shift relative to `no_cue`.

Phase 0B panel-cluster bootstrap read at `lambda = 0.5`:

- `additive_disagreement_shown` paired delta net: +0.024, 95% CI [+0.012, +0.037].
- `misleading_reliability_card` paired delta net: -0.018, 95% CI [-0.033, -0.004].
- Sonnet versus `trust_all_sfm`: -0.004 net/gene, 95% CI [-0.013, +0.006].
- Sonnet versus `always_additive`: +0.007 net/gene, 95% CI [-0.026, +0.039].
- Therefore, the cue-effect story is stronger than the simple-baseline superiority story.

Phase 0 full-substrate deterministic baseline at `lambda = 0.5`:

- `trust_all_sfm`: accuracy 0.681, assays/gene 0.000, net/gene 0.681
- `always_additive`: accuracy 0.675, assays/gene 0.000, net/gene 0.675
- `signal_gated_verify`: accuracy 0.770, assays/gene 0.201, net/gene 0.670
- `oracle_verify`: accuracy 1.000, assays/gene 0.319, net/gene 0.840

Additive-coverage subset at `lambda = 0.5`:

- `trust_all_sfm`: accuracy 0.673, net/gene 0.673
- `always_additive`: accuracy 0.812, net/gene 0.812
- `signal_gated_verify`: accuracy 0.846, net/gene 0.745
- `oracle_verify`: accuracy 1.000, net/gene 0.836

Stratified Sonnet 4.6 pilot at `lambda = 0.5`:

- accuracy 0.784
- assays/gene 0.183
- net/gene 0.692
- trust error rate 0.152
- verify recall 0.251
- defer rate 0.003
- coverage rate 0.997

Stratified Opus 4.8 pilot at `lambda = 0.5`:

- accuracy 0.809
- assays/gene 0.293
- net/gene 0.662
- trust error rate 0.143
- verify recall 0.372
- defer rate 0.016
- coverage rate 0.984

Lambda sweep:

- Opus wins only when verification is very cheap.
- Micro-primary break-even lambda for Opus versus Sonnet net/gene is approximately 0.223 (frozen full run; the earlier pilot72 estimate was ≈0.234).
- Above that, Sonnet's lower assay use gives better net reward.

## Current Scientific Read

The current Phase 0B result supports a cautious Phase 0 claim:

> In a full GEARS/Norman dry run, the LLM reasoning layer is strongly cue-sensitive and only weakly calibrated as a cost-aware orchestrator. Explicit reliability signals can improve routing, but reliability-looking cues can also mislead it; explanations often report unavailable evidence.

The evidence is strongest for:

- additive disagreement improving constructive routing,
- misleading reliability cards changing behavior in harmful ways,
- simple baseline comparison showing Sonnet is not a dominant policy and near-ties `trust_all_sfm`,
- self-reported cues overclaiming unavailable evidence.

The evidence is not yet strong enough for:

- final claims about all LLMs,
- final claims about true SFMs,
- claims about mechanistic biological understanding,
- claims about internal SFM-feature use.

## Explanation-Faithfulness Guardrail

Self-reported cues and rationales are treated as model behavior, not as ground truth about evidence use.

Current pilot examples:

- Sonnet 4.6 self-reports baseline disagreement in 91.7% of `no_cue` episodes.
- Sonnet 4.6 self-reports confidence in 83.3% of `no_cue` episodes.
- Opus 4.8 self-reports baseline disagreement in 50.0% of `no_cue` episodes.
- Anonymization affects Opus behavior more than it is acknowledged in explanations.

Therefore, explanation faithfulness must be evaluated against measured cue sensitivity.

Phase 0B full-run examples:

- In `no_cue`, Sonnet self-reports unavailable baseline evidence in 94.4% of episodes.
- In `no_cue`, Sonnet self-reports unavailable confidence evidence in 80.4% of episodes.
- In `model_name_shown`, model identity is self-reported in 100% of episodes, but the actual action shift is small.
- In `misleading_reliability_card`, the reliability-looking cue strongly shifts behavior and hurts net reward.

## Known Limitations

GEARS limitation:

- GEARS is a perturbation model substrate, not the final true-SFM target.
- Phase 0 should be described as a dry run for the reasoning-layer benchmark.

Pilot-size limitation:

- Phase 0A uses 72 requests and should remain a pilot anchor.
- Phase 0B uses the full 642 non-leakage Sonnet request set, but it is still a GEARS/Norman dry run.
- Use Phase 0B for method validation and dry-run claims, not true-SFM or final population-level claims.

Confidence limitation:

- `sfm_confidence` is magnitude-derived pseudo-confidence.
- It should not be interpreted as calibrated uncertainty.

Leakage limitation:

- `raw_assay_stats_shown` includes measured DE statistics.
- It is a positive-control condition only.

Biology limitation:

- The task abstracts perturbation biology into edge-level calls and rewards.
- It does not evaluate full mechanistic explanations, pathway validity, or downstream experimental design.
- Binary correctness is thresholded at the current effect/no-effect call level; it does not yet reward effect-size calibration, direction-specific magnitude error, FDR-aware uncertainty, or mechanistic validity.

Reward limitation:

- `verify_assay` is idealized as perfectly revealing held-out truth.
- Current assay cost is unit cost per gene, not batch-aware wet-lab cost.
- `default_baseline` is a unified action, but summaries now report whether it resolved to observed-additive or no-change fallback.
- Defer is tracked separately from wrong non-deferred calls, but the default Phase 0 defer penalty remains zero unless explicitly configured.

Generalization limitation:

- Current results are from Claude Sonnet 4.6 and Claude Opus 4.8 on a GEARS/Norman substrate.
- The next claim boundary requires one true-SFM extension.

## Reproducibility Anchors

Primary implementation:

- `experiments/trust_cue_attribution/`

Primary outputs:

- `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/`
- `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_contract.json`

Primary result document:

- `experiments/trust_cue_attribution/results/RESULTS.md`

HPC target:

- Cayuga remote root: `/scratch/USER/LLM_SFM_interpretability`
- Python: `/usr/bin/python3.12`

Current validation:

- `20 unittest discover` tests OK on Cayuga
- `24 unittest discover` tests OK locally after reward-summary diagnostics were added
- `44 unittest discover experiments/trust_cue_attribution/tests` tests OK locally after Phase 0B freeze support was added
- `53 unittest discover -s experiments/trust_cue_attribution/tests` tests OK on Cayuga during Phase 1 scFoundation feasibility probe
- `56 unittest discover -s experiments/trust_cue_attribution/tests` tests OK locally and on Cayuga during Phase 1 input inventory work
- `61 unittest discover -s experiments/trust_cue_attribution/tests` tests OK locally after Phase 1 inference-env gate support was added
- `77 unittest discover -s experiments/trust_cue_attribution/tests` tests OK locally after Phase 1A panel-signal support and placebo-control checks were added
- `82 unittest discover -s experiments/trust_cue_attribution/tests` tests OK locally after Phase 1A signal-validity diagnostics were added
- `84 unittest discover -s experiments/trust_cue_attribution/tests` tests OK locally after Phase 1A signal-granularity diagnostics were added
- `86 unittest discover -s experiments/trust_cue_attribution/tests` tests OK locally after Phase 1B edge-signal design gate was added
- `93 unittest discover -s experiments/trust_cue_attribution/tests` tests OK on Cayuga during the Phase 1B small Sonnet pilot
- `94 unittest discover -s experiments/trust_cue_attribution/tests` tests OK locally after Phase 1B post-pilot review support was added
- `97 unittest discover -s experiments/trust_cue_attribution/tests` tests OK locally after Phase 1C reliability-interface offline gate support was added
- `99 unittest discover -s experiments/trust_cue_attribution/tests` tests OK locally after Phase 1C interface request preparation support was added

## Expansion Gate

Before Phase 1, this benchmark should have:

- stable panel and cue schema,
- deterministic baselines,
- paired cue effects,
- cue-attribution regression,
- explanation-faithfulness analysis,
- benchmark card and result guardrails.
- compact Phase 0B freeze artifacts.
- scFoundation adapter preflight contract.

Phase 1 should add one true SFM while preserving the same action and reward interface. The likely first target is scFoundation or a closely related single-cell foundation model. The benchmark should not become a standalone GEARS leaderboard.

The Phase 1 preflight contract is an interface gate, not a true-SFM result. It
requires the adapter to produce standardized evidence packets, hide held-out
truth/reward fields from prompts, expose at least one internal-signal summary,
and run heavy model compute on Cayuga or Expanse.

The current Phase 1 feasibility report is `ready_for_hpc_smoke`. Cayuga has the
scFoundation repository, gene index, checkpoint, and a Phase 1 input placeholder
staged. This is a readiness gate only; it is not a scFoundation inference result.

The current Phase 1 input inventory is `ready_for_adapter_smoke`: 794 of 834
input genes overlap the scFoundation vocabulary. This is adequate for a wiring
smoke test but weak for scientific interpretation because it covers only 4.1%
of the 19,264-gene vocabulary.

The current Phase 1 inference environment login probe is
`ready_for_gpu_env_probe`. The isolated smoke environment imports the required
Python stack and scFoundation `model/load.py`, but CUDA is not visible on the
login node. A GPU Slurm allocation must pass before any true inference smoke.

The current Phase 1 tiny scFoundation smoke status is
`ready_for_internal_signal_summary_adapter`. Cayuga job `3044223` produced a
finite `[3, 3072]` cell embedding summary through the official scFoundation
embedding script. This supports adapter wiring only; it does not support
scientific interpretation or LLM trust claims.

The current Phase 1A panel-specific signal status is
`ready_for_phase1a_panel_specific_signal_packets`. Cayuga job `3044228` used
the public Norman 2019 h5ad at
`/scratch/USER/nomos/data/norman_2019.h5ad`,
sampled 12 Phase 0 panels plus controls, and produced a finite `[256, 3072]`
scFoundation embedding summary. The compact tracked report is
`experiments/trust_cue_attribution/results/phase1a_panel_signals/panel_signal_report.json`.
The regenerated 36-request Phase 1A Sonnet pilot has now been run and scored.
Cayuga job `3044233` wrote 36/36 episodes with 0 parse errors and 0 provider
errors; Slurm marked the job failed only after outputs were written because the
final summary-print heredoc hit node temp-space limits. At `lambda = 0.5`,
Sonnet overall reached accuracy `0.790`, assays/gene `0.237`, and net/gene
`0.672`. The real scFoundation signal improved net/gene versus no signal by
`+0.019`, while the shuffled placebo improved it by `+0.016`, so the result is
cue-sensitivity evidence, not faithful internal-SFM interpretation evidence.
The follow-up review artifact sets the next gate to `do_not_scale_yet` because
the placebo effect is close to the real-signal effect. Before a larger Phase 1A
run, the internal-signal cue should become more decision-relevant and the
irrelevant-signal control should be strengthened.

The panel-signal validity artifact independently sets the next gate to
`redesign_before_scaling`: among the 12 selected panels, the strongest primary
panel-distance signal versus GEARS `wrong_rate` is
`std_cell_distance_to_control` with Pearson `-0.505`, while
`centroid_distance_to_control` and `mean_cell_distance_to_control` are also
negative versus `wrong_rate`. The current coarse scFoundation card should not
be scaled as a naive high-risk cue; the next cue should be gene-level or
task-aligned while preserving the shuffled-signal placebo control.

The signal-granularity artifact sets the more specific next gate to
`edge_level_signal_required`. All 12 selected panels contain both correct and
wrong GEARS genes, creating 315 edge rows with 102 wrong and 213 correct edges.
The best primary panel-level scFoundation signal reaches AUROC `0.467` for
edge wrongness, while edge-level baseline call disagreement reaches AUROC
`0.649`. The next scFoundation cue should therefore be readout-gene-specific or
task-aligned before any larger Phase 1A LLM matrix.

The Phase 1B edge-signal design artifact recommends
`scfoundation_neighbor_edge_support` for the next HPC prototype. This route is
feasible because 302 of 315 selected edges, or `0.95873`, have at least 10 other
panels sharing the same readout gene. The proposed evidence unit is
`(perturbation, readout_gene)` and the model-visible schema is
`evidence_packet.genes[].edge_internal_signal_summary`. The masked readout-gene
prediction route remains blocked until a scFoundation gene-level prediction
path is verified.

The Phase 1B small Sonnet pilot completed on Cayuga job `3045288` with 48
episodes, 12 panels, 315 genes per condition, zero parse errors, and zero
provider errors. At lambda `0.5`, `scfoundation_edge_neighbor_signal_shown`
changed 44.8% of paired actions and reduced trust error by 5.1 percentage
points, but net reward per gene fell from `0.6587` under no-signal to `0.6206`.
The random same-gene and shuffled readout-gene controls also shifted behavior,
so the result supports controlled cue sensitivity rather than calibrated SFM
interpretation.

The Phase 1B post-pilot review sets the gate to
`do_not_scale_larger_llm_matrix` because the real edge-neighbor signal reduced
lambda `0.5` net reward versus no-signal (`delta_net = -0.038095`) and did not
beat the best control (`real_minus_best_control_delta_net = -0.009524`). The
next step is deterministic signal redesign, not more LLM calls using the same
packet.

The Phase 1C offline gate converts additive-disagreement risk, specialist
output-margin risk, and scFoundation edge-neighbor disagreement risk into an
explicit reliability interface. It clears the offline gate at lambda `0.5`
with net reward/gene `0.747619`, beating no-signal LLM `0.658730`, raw
edge-neighbor LLM `0.620635`, and the best control `0.744444`. The real-control
margin is only `0.003175`, so this supports at most a small Phase 1C interface
pilot.

The Phase 1C interface request set is now prepared for that small pilot:
`12` panels x `4` cue conditions = `48` requests. The cue conditions are
`no_internal_signal`, `edge_neighbor_signal_shown`,
`calibrated_reliability_interface_shown`, and
`inverted_reliability_interface_control`. The model-visible leakage check
passes, and no new Claude call was made in request preparation.
