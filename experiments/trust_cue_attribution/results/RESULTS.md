# Results: Trust-Cue Attribution

Status: Phase 0B is a frozen full non-leakage Sonnet method-validation run.
Phase 1 (single-cell) reached a NO-GO (near-noise scFoundation cue, GEARS approx
additive, mechanism scooped by Turpin 2023); the project pivoted to Phase 2
(protein structure, Boltz-2 / pLDDT). Honest Phase 2 read: the project's central
intervention -- the calibrated reliability *interface* -- does NOT robustly beat
simply showing raw pLDDT (n.s. for Sonnet; significantly WORSE for Opus, which
over-verifies). The only robust positive is the near-trivial "confidence beats no
signal"; the genuinely useful findings are the A4 control and the cautionary
cross-model negative. The offline-gate PASS was engineered post-hoc. See
"Phase 2" below, including caveats.

## Phase 2 Protein-Structure Trust Interface (Boltz-2 / pLDDT)

Validated, leakage-safe substrate: 80 RCSB targets released 2026-06-17 (post
Boltz-2's 2023-06 training cutoff), 40 monomer + 40 complex. Compact artifacts
under `results/phase2_preflight/`: `boltz_contract.json`,
`boltz_smoke_report.json` (stack validated on Cayuga A40), `calibration_gate.json`
+ `threshold_sensitivity.json`, `calibrated_gate.json` (offline gate PASS),
`interface_pilot_score.json` + `interface_pilot_robustness.json`.

Offline calibration gate: pLDDT->lDDT calibration is strong for monomers
(Pearson 0.89) and degrades for complexes (0.16). The binary gate is degenerate
at lDDT>=0.7 (Boltz-2 is correct on ~95% of recent targets), but at an lDDT>=0.9
cutoff with leave-one-out isotonic risk->P(wrong) calibration it PASSES
(`eligible_for_phase2_interface_pilot`): signal AUROC 0.89; the risk>lambda policy
beats trust-all (+0.06) and shuffled/inverted controls (+0.14).

Sonnet interface pilot: 200 episodes (40 targets x 5 arms), 0 parse/provider
errors. Net reward/target at lambda 0.5 with target-bootstrap 95% CIs (seed 13,
1000 draws):

| arm | net | delta vs no_signal (95% CI) |
|---|---:|---|
| `calibrated_interface_shown` | 0.738 | +0.487 [+0.338, +0.625] |
| `calibrated_risk_shown_no_recommendation` | 0.725 | +0.475 [+0.325, +0.613] |
| `raw_plddt_shown` | 0.713 | +0.463 [+0.300, +0.613] |
| `inverted_reliability_interface_control` | 0.388 | +0.138 [+0.025, +0.250] |
| `no_signal` | 0.250 | -- |

Findings (bootstrap-backed): (1) any confidence cue robustly beats no-signal
(+0.46-0.49, CIs exclude 0, stable across lambda 0.2/0.5/0.8) -- the LLM converts
reliability evidence into better cost-aware routing; (2) A4 -- calibrated card vs
no-recommendation CI ~[0.000, 0.037] -- the benefit is the calibrated
*information*, not the directive; (3) calibrated card vs raw pLDDT CI
[-0.037, +0.087] crosses 0 -- calibration does NOT measurably beat raw pLDDT at
n=40; (4) regime-appropriate -- under the calibrated card the LLM verifies
complexes (0.55) far more than monomers (0.20), matching where pLDDT calibration
degrades; (5) cue-sensitivity persists -- the inverted card degrades routing
(0.74 -> 0.39).

Honest claim boundary (leads with what failed). The project's central
intervention -- converting confidence into a calibrated reliability *card* -- is
NOT supported: it does not robustly beat raw pLDDT (Sonnet +0.025, CI crosses 0;
Opus -0.225, robustly worse). What IS robust is near-trivial: any confidence cue
beats the no-signal baseline (where Claude defers/over-verifies for lack of any
info). The genuinely useful results are the A4 control (benefit is informational,
not directive) and the cautionary cross-model negative (the card backfires on a
risk-averse model).

Caveats that further bound the claim: (a) the offline-gate PASS was engineered
post-hoc -- the lDDT>=0.9 correctness cutoff was chosen AFTER lDDT>=0.7 proved
degenerate, and the isotonic calibration is fit in-distribution (LOO over the
same 80) -- a garden-of-forking-paths; (b) ground truth is a home-grown CA-lDDT,
unvalidated against OpenStructure, and complexes use all-chain CA-lDDT, not DockQ;
(c) the substrate is low-stakes (Boltz correct ~95% at lDDT>=0.7), a mirror of
the GEARS flat-surface problem; (d) the model-visible packet contains only the
confidence (+ regime), so "the LLM uses the signal" is partly forced by design;
(e) n=40, single primary lambda, single MSA source, one run per model, no real
template baseline (default-False placeholder).

Robustness note: the pilot's LLM-routing conclusions are cutoff-robust (re-scored
at lDDT 0.5/0.7/0.8/0.9; `cutoff_robustness.json`) -- the calibrated card is ~0
vs raw for Sonnet and ~-0.25 vs raw for Opus at every cutoff -- so the post-hoc
0.9 choice drives only the offline-gate variance, not the pilot result. A
pre-registered confirmatory redo (held-out calibration, lDDT validated vs
OpenStructure + DockQ, harder lower-base-rate targets, a competing-cue arm, >=3
models, lambda sweep) is specified in `PHASE2_PREREGISTRATION.md`.

Cross-model (Opus 4.8, same 200 requests; `interface_pilot_score_opus.json`,
`interface_pilot_robustness_opus.json`): raw pLDDT helps both models robustly
(Opus +0.562 vs no_signal), but the calibrated *card* backfires for Opus -- it
over-verifies (0.975 verify rate under the card vs Sonnet's 0.375), making it
robustly WORSE than raw pLDDT (-0.225, CI [-0.325, -0.113]); for Sonnet the same
card was neutral (+0.025, n.s.). This replicates the Phase 0 "Opus over-verifies"
finding on the new substrate: stronger reasoning does not yield better cost-aware
orchestration, and the "estimated_wrong_risk" framing triggers excessive
verification in the more risk-averse model (it verifies even confident monomers).
A4 (info-not-directive) holds for both models (card vs no-recommendation = 0).
Refined claim: raw specialist confidence robustly improves routing across models;
repackaging it as a calibrated reliability card is model-dependent (neutral for
Sonnet, harmful for Opus).

Authoritative compact freeze artifacts:

- `experiments/trust_cue_attribution/results/phase0a_freeze/manifest.json`
- `experiments/trust_cue_attribution/results/phase0a_freeze/summary.json`
- `experiments/trust_cue_attribution/results/phase0b_freeze/manifest.json`
- `experiments/trust_cue_attribution/results/phase0b_freeze/summary.json`
- `experiments/trust_cue_attribution/results/phase0b_robustness/summary.json`
- `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_contract.json`
- `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_feasibility.json`
- `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_input_inventory.json`
- `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_inference_env_login.json`
- `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_inference_env_gpu.json`
- `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_smoke_report.json`
- `experiments/trust_cue_attribution/results/phase1a_panel_signals/panel_signal_report.json`
- `experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json`
- `experiments/trust_cue_attribution/results/phase1a_signal_pilot/summary.json`
- `experiments/trust_cue_attribution/results/phase1a_signal_pilot/review.json`
- `experiments/trust_cue_attribution/results/phase1a_signal_pilot/signal_validity.json`
- `experiments/trust_cue_attribution/results/phase1a_signal_pilot/signal_granularity.json`
- `experiments/trust_cue_attribution/results/phase1b_edge_signal_design/design.json`
- `experiments/trust_cue_attribution/results/phase1b_edge_neighbor/embedding_pool_report.json`
- `experiments/trust_cue_attribution/results/phase1b_edge_neighbor/neighbor_signal_report.json`
- `experiments/trust_cue_attribution/results/phase1b_signal_pilot/manifest.json`
- `experiments/trust_cue_attribution/results/phase1b_signal_pilot/summary.json`
- `experiments/trust_cue_attribution/results/phase1b_signal_pilot/review.json`
- `experiments/trust_cue_attribution/results/phase1c_reliability_interface/design.json`
- `experiments/trust_cue_attribution/results/phase1c_reliability_interface/offline_gate.json`
- `experiments/trust_cue_attribution/results/phase1c_reliability_interface/interface_request_manifest.json`
- `experiments/trust_cue_attribution/results/phase1c_reliability_interface/specialist_metric_check.json`
- `experiments/trust_cue_attribution/results/phase1_hyper_review/REVIEW.md`

Large JSONL inputs, LLM episodes, and trajectory artifacts remain ignored under
`experiments/trust_cue_attribution/hpc_outputs/`. The freeze manifest records
their SHA256 hashes and record counts. The freeze summary recomputes
scorer-dependent LLM metrics from episode JSONL with the current micro
gene-weighted scorer.

Benchmark-card guardrail: see
`experiments/trust_cue_attribution/BENCHMARK_CARD.md` for intended use,
non-use, metric definitions, and claim boundaries.

## Phase 1 Preflight Anchor

Phase 1 preflight artifact:

- `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_contract.json`
- SHA256: `4e313691e58a195312bd41a91c65caff5b3b20a02e404d8a98dd87165d9f6b18`

This is an adapter contract, not a true-SFM result. It defines what a
scFoundation-compatible adapter must provide before Phase 1 compute starts:
required inputs, standardized outputs, model-visible evidence fields, hidden
fields, internal-signal summaries, preflight checks, and the claim boundary.

Phase 1 claim boundary:

> Interface preflight only until one full Phase 1 run is scored; no claim that
> the LLM uses true SFM internals faithfully.

Phase 1 feasibility probe:

- `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_feasibility.json`
- SHA256: `3f310e6dccc9ba5840ae5f8aec21a3db90a6743b5dd8fa52b44805d7314c1049`
- status: `ready_for_hpc_smoke`

Confirmed Cayuga artifacts:

- scFoundation repo: `/scratch/USER/huggingface/benchmark/scFoundation`
- gene index: `/scratch/USER/huggingface/benchmark/scFoundation/OS_scRNA_gene_index.19264.tsv`
- checkpoint: `/scratch/USER/huggingface/benchmark/scFoundation/model/models/models.ckpt`
- local wiring-only smoke input: `/scratch/USER/Perturb_seq/virtual_cell/2026_03_18_cfgA/data/fram2_val.h5ad`

This means Phase 1 is ready for an HPC adapter smoke job. It does not mean
scFoundation inference has succeeded yet. The next gate is producing
schema-valid `phase1_panels.jsonl`, `phase1_cue_packets.jsonl`, and internal
signal summaries without exposing held-out truth or reward fields.

Data-use guardrail: the FRAM2 smoke input is local/unpublished and is not used
as benchmark data or as the basis for scientific claims. It remains only a
wiring check for scFoundation execution. Public, widely used flagship data are
required for benchmark-facing Phase 1 work.

Phase 1 input compatibility inventory:

- `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_input_inventory.json`
- SHA256: `0e20cd54f93166379e6dcc66825d10e7f96b52a657da4787adf82e9c6c81f8ef`
- status: `ready_for_adapter_smoke`
- input genes: 834
- scFoundation vocabulary genes: 19,264
- overlapping genes: 794
- overlap fraction of input: 0.952
- scFoundation vocabulary coverage: 0.041
- warning: `low_fraction_of_scfoundation_vocabulary_observed_input_is_likely_hvg_or_subset`

Interpretation: the staged `fram2_val.h5ad` is suitable only for wiring and
adapter smoke tests. It is local/unpublished and likely an HVG/subset
expression matrix, so it should not be used for benchmark claims or scientific
claims about scFoundation behavior.

Phase 1 inference environment probe, login/import gate:

- `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_inference_env_login.json`
- SHA256: `11e034413f009743a259451ba8543e39f27137c05b60b8e874ef2d646b29c1d6`
- status: `ready_for_gpu_env_probe`
- Python: `hpc_outputs/envs/scfoundation-smoke-py39/bin/python`
- torch: `2.8.0+cu128`
- CUDA visible: false, as expected on the login node
- scFoundation `model/load.py` import: true
- required imports OK: `numpy`, `pandas`, `scipy`, `torch`, `einops`,
  `scanpy`, `anndata`, `h5py`, `local_attention`

Interpretation: the isolated smoke environment is dependency-ready and can
import the scFoundation model code. The remaining gate is running the same probe
inside a GPU Slurm allocation and confirming CUDA visibility. This still does
not load the 1.4GB checkpoint or produce embeddings.

Phase 1 inference environment probe, GPU gate:

- `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_inference_env_gpu.json`
- SHA256: `1d4d12a10cb6782fdf035f4285c414609f7ce580f39987cbc35a47514101a787`
- status: `ready_for_inference_smoke`
- GPU visible: `NVIDIA A100 80GB PCIe`
- CUDA visible to torch: true
- torch: `2.8.0+cu128`
- scFoundation `model/load.py` import: true
- Cayuga job: `3044220`

Interpretation: the environment is ready for the first tiny scFoundation
inference smoke.

Phase 1 tiny scFoundation inference smoke:

- `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_smoke_report.json`
- SHA256: `159b16f41b503dc61ff2283c1bc9702155212a4b7a7d530b9c743b6ff3704fde`
- status: `ready_for_internal_signal_summary_adapter`
- Cayuga job: `3044223`
- job state: `COMPLETED`, exit code `0:0`, elapsed `00:00:43`
- smoke GPU visible: `NVIDIA A40`
- source h5ad shape: `[19464, 834]`
- tiny subset shape: `[3, 834]`
- scFoundation feature conversion: `[3, 19264]`
- embedding shape: `[3, 3072]`
- embedding dtype: `float32`
- embedding finite fraction: `1.0`
- embedding SHA256: `e85d63b288d121fd681e3017a2d0f0b7650cf9ca5d1227423de30414d536c520`

Interpretation: the official scFoundation embedding path is runnable in the
Cayuga smoke environment and can produce compact internal-signal summaries. This
still does not support a true-SFM trust claim, because no LLM routing run has
used the signal and the staged input remains an 834-gene subset. The next
efficient step is a Phase 1A minimal signal pilot, not a full 642-request run.

## Phase 1A Signal Packet Pilot Anchor

Phase 1A signal packet manifest:

- `experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json`
- SHA256: `2bad8434bc520b1a8eeade9dd19da9e378d6d404e7834b055661afb72896b634`
- status: `signal_packet_pilot_ready`
- source smoke report: `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_smoke_report.json`
- source panel-signal report: `experiments/trust_cue_attribution/results/phase1a_panel_signals/panel_signal_report.json`
- signal scope: `panel_specific`
- selected panels: `12`
- cue conditions: `no_internal_signal`, `scfoundation_internal_signal_shown`, `shuffled_internal_signal_shown`
- packets: `36`
- request records prepared under ignored `hpc_outputs/phase1a_signal_pilot/`: `36`
- shuffled-control behavior: deterministic placebo values are drawn from another
  panel-specific signal and relabeled to the target panel, while the hidden
  control label is excluded from model-visible prompts.

Leakage check: generated packet/request JSONL contains no `correct`, `truth`,
`real_call`, `real_label`, `scoring_key`, reward, assay stats, or control-label
strings in model-visible prompts. This is a packet-generation checkpoint only;
the separate scored pilot is summarized below.

Panel-specific signal correction:

- FRAM2 smoke h5ad perturbation overlap with Norman Phase 0 panels: `0`; it is
  local/unpublished and not benchmark-facing.
- Norman 2019 h5ad path on Cayuga: `/scratch/USER/nomos/data/norman_2019.h5ad`.
- Norman 2019 h5ad shape: `[111255, 19018]`.
- Direct overlap via `perturbation_name`: `107 / 107` Phase 0 panels.
- Phase 1A panel-specific signal job: `3044228`, completed on Cayuga GPU resources.
- Panel-specific signal report: `experiments/trust_cue_attribution/results/phase1a_panel_signals/panel_signal_report.json`
- Panel-specific signal report SHA256: `ac4e76c8edfcd2796536ffe3badefece8bcc64f73b764b8d06f520a5199b7cab`
- Source shape: `[111255, 19018]`
- scFoundation subset shape: `[256, 19018]`
- scFoundation embedding shape: `[256, 3072]`
- Embedding finite fraction: `1.0`
- Selected panels: `12`
- Sampled cells: `16` cells per selected panel plus `64` controls
- Panel signal status: `ready_for_phase1a_panel_specific_signal_packets`

Interpretation: the next valid Phase 1A LLM pilot should use these per-panel
scFoundation summaries from the public Norman h5ad, not the global FRAM2 smoke
summary. The regenerated 36-request pilot now points to the panel-specific
report.

## Phase 1A Sonnet Signal Pilot Result

Phase 1A signal pilot summary:

- `experiments/trust_cue_attribution/results/phase1a_signal_pilot/summary.json`
- SHA256: `1c8a6b8816caf1d394b3254d3fcf8c96ad0faa466fa7b4f7b00556b6d9f43bb9`
- Review artifact: `experiments/trust_cue_attribution/results/phase1a_signal_pilot/review.json`
- Review SHA256: `78693a691e7011b7b5c90e6b5c079dd86e4f94df81ffee2c23bc8d1f5dc64e57`
- Review decision: `do_not_scale_yet`
- Review reason: `placebo_effect_close_to_real_signal_effect`
- Signal-validity artifact: `experiments/trust_cue_attribution/results/phase1a_signal_pilot/signal_validity.json`
- Signal-validity SHA256: `d504f17ac46b634ea132650232ff44daab0fc1ad9ae407405e4e351b48212cc3`
- Signal-validity decision: `redesign_before_scaling`
- Signal-validity reason: `primary_signal_points_opposite_expected_direction`
- Signal-granularity artifact: `experiments/trust_cue_attribution/results/phase1a_signal_pilot/signal_granularity.json`
- Signal-granularity SHA256: `f479c6ee732435fd743ca8223451dc6ffe004a62d3ef58b3f214a8706065e7fa`
- Signal-granularity decision: `edge_level_signal_required`
- Signal-granularity reason: `panel_constant_signal_weak_for_edge_wrongness`
- model: `claude-sonnet-4-6`
- provider: `anthropic_messages`
- Cayuga job: `3044233`
- Slurm state: `FAILED` after outputs were written, due to a final
  summary-print heredoc temp-space error; episodes and scores are valid.
- episodes: `36 / 36`
- parse errors: `0`
- provider errors: `0`
- panels: `12`
- cue conditions: `no_internal_signal`,
  `scfoundation_internal_signal_shown`, `shuffled_internal_signal_shown`
- total gene decisions: `945`

Overall Sonnet Phase 1A score:

| lambda | accuracy | assays/gene | net/gene | trust error | verify precision | verify recall | default rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.2 | 0.790 | 0.237 | 0.743 | 0.187 | 0.330 | 0.242 | 0.090 |
| 0.5 | 0.790 | 0.237 | 0.672 | 0.187 | 0.330 | 0.242 | 0.090 |
| 0.8 | 0.790 | 0.237 | 0.601 | 0.187 | 0.330 | 0.242 | 0.090 |

Cue-level result at `lambda = 0.5`:

| cue | accuracy | assays/gene | net/gene | trust error | verify rate | default rate |
|---|---:|---:|---:|---:|---:|---:|
| `no_internal_signal` | 0.787 | 0.254 | 0.660 | 0.206 | 0.254 | 0.063 |
| `scfoundation_internal_signal_shown` | 0.794 | 0.229 | 0.679 | 0.190 | 0.229 | 0.086 |
| `shuffled_internal_signal_shown` | 0.790 | 0.229 | 0.676 | 0.165 | 0.229 | 0.121 |

Paired effect versus `no_internal_signal` at `lambda = 0.5`:

| cue | delta net/gene | delta accuracy | delta assays/gene | action changed rate |
|---|---:|---:|---:|---:|
| `scfoundation_internal_signal_shown` | +0.019 | +0.006 | -0.025 | 0.146 |
| `shuffled_internal_signal_shown` | +0.016 | +0.003 | -0.025 | 0.184 |

Baseline comparison on the same 12-panel, 36-packet surface at `lambda = 0.5`:

| policy | accuracy | assays/gene | net/gene |
|---|---:|---:|---:|
| Sonnet overall | 0.790 | 0.237 | 0.672 |
| `trust_all_sfm` | 0.676 | 0.000 | 0.676 |
| `always_additive` | 0.667 | 0.000 | 0.667 |
| `signal_gated_verify` | 0.752 | 0.203 | 0.651 |
| `verify_all` | 1.000 | 1.000 | 0.500 |
| `oracle_verify` | 1.000 | 0.324 | 0.838 |

Interpretation: this is a useful cue-sensitivity pilot, not evidence that
Claude faithfully interprets scFoundation internals. Real panel-specific signal
and shuffled placebo both slightly improve net reward versus no signal, and the
placebo effect is close enough that the honest read is: internal-signal-looking
evidence changes routing, but the current cue design does not yet prove
faithful use of the true SFM signal.

Phase 1A review diagnostic:

- Real signal delta net/gene versus no signal: `+0.019`
- Placebo delta net/gene versus no signal: `+0.016`
- Real minus placebo delta net/gene: `+0.003`
- Placebo fraction of real delta: `0.833`
- Real action changed rate: `0.146`
- Placebo action changed rate: `0.184`

Phase 1A panel-signal validity diagnostic:

- Matched selected panels: `12 / 12`
- Primary question: do coarse scFoundation panel embedding distance summaries
  align with GEARS wrongness strongly enough to justify scaling this cue?
- Strongest primary signal versus `wrong_rate`:
  `std_cell_distance_to_control`, Pearson `-0.505`.
- Other primary signal correlations versus `wrong_rate`:
  `centroid_distance_to_control` Pearson `-0.303`;
  `mean_cell_distance_to_control` Pearson `-0.400`.
- Strongest primary signal versus `high_risk_rate`:
  `mean_cell_distance_to_control`, Spearman `+0.469`.
- Decision: `redesign_before_scaling`.

Interpretation: the coarse scFoundation panel card may reflect broad
perturbation/embedding behavior, but it is not a validated reliability signal
for GEARS wrongness. In this selected pilot, larger panel-distance-style values
do not mean GEARS is more likely to be wrong. Therefore the next Phase 1A step
should not be a larger LLM matrix with the current card; it should be a
gene-level or task-aligned internal-signal cue with the shuffled-signal placebo
kept in the design.

Phase 1A signal granularity diagnostic:

- Matched selected panels: `12 / 12`
- Matched edge rows: `315`
- Wrong/correct edge counts: `102 / 213`
- Mixed correct-and-wrong panels: `12 / 12`
- Mixed panel fraction: `1.0`
- Best primary panel-level scFoundation signal for edge wrongness:
  `centroid_distance_to_control`, AUROC `0.467`.
- Best edge-level reference score for edge wrongness:
  `baseline_call_disagreement`, AUROC `0.649`.
- Decision: `edge_level_signal_required`.

Interpretation: the reward/action unit is an edge, but the current
scFoundation evidence unit is a panel. Because every selected panel contains
both correct and wrong GEARS genes, a panel-constant signal cannot tell the LLM
which readout genes deserve verification. This strengthens the route decision:
the next scFoundation cue should be readout-gene-specific or otherwise
task-aligned, then compared against baseline-disagreement and shuffled-signal
controls before any larger Phase 1A LLM matrix.

## Phase 1B Edge-Signal Design Gate

Phase 1B edge-signal design artifact:

- `experiments/trust_cue_attribution/results/phase1b_edge_signal_design/design.json`
- SHA256: `a2245af1e57a83255cc1886e2856305c7a48d31c0afdbb525e8602477f502e7a`
- status: `edge_signal_design_ready`
- recommended route: `scfoundation_neighbor_edge_support`
- route decision: `recommended_for_hpc_prototype`
- selected panels: `12`
- selected edges: `315`
- selected unique readout genes: `77`
- full panels considered for readout-gene reuse: `107`
- full unique readout genes: `97`
- selected edges with at least 10 other panels sharing the same readout gene:
  `302 / 315`, fraction `0.95873`
- selected edges with at least 20 other panels sharing the same readout gene:
  `256 / 315`, fraction `0.812698`
- median other-panel same-gene count: `58`

Recommended next route: build a small HPC prototype that uses scFoundation
panel/cell embeddings to retrieve nearby perturbation panels, then summarizes
non-truth same-readout-gene evidence per edge. The proposed model-visible field
is `evidence_packet.genes[].edge_internal_signal_summary`, with values such as
neighbor count, same-readout-gene neighbor count, embedding-distance summary,
neighbor SFM-call agreement rate, and neighbor baseline-disagreement rate.

Interpretation: the next cue should vary by `(perturbation, readout_gene)` and
must not expose target-edge correctness, held-out truth labels, target raw
assay statistics, or reward. The masked readout-gene prediction route remains
blocked until scFoundation exposes or we verify a gene-level prediction path;
the current official smoke path only proved embeddings.

Phase 1B edge-neighbor executable gate result:

- module: `experiments/trust_cue_attribution/phase1b_neighbor_signals.py`
- sbatch: `experiments/trust_cue_attribution/hpc/run_phase1b_embedding_pool.sbatch`
- embedding-pool command: `phase1b-embedding-pool`
- diagnostic command: `phase1b-neighbor-signals`
- Cayuga fallback job: `3045167`
- partition/QOS: `preempt_gpu` / `low`
- node: `g0004`, H100 NVL
- state: `COMPLETED`, exit code `0:0`, elapsed `00:02:22`
- original `scu-gpu` duplicate job: `3045068`, cancelled after fallback success
- embedding-pool report:
  `experiments/trust_cue_attribution/results/phase1b_edge_neighbor/embedding_pool_report.json`
- embedding-pool report SHA256:
  `d226e36a5fea3b075dfabf0b5e22d11577b17d73dd670d57f23c0d3301fd708e`
- neighbor-signal report:
  `experiments/trust_cue_attribution/results/phase1b_edge_neighbor/neighbor_signal_report.json`
- neighbor-signal report SHA256:
  `435658afe587330357afa08032e41baade8b6ff59893d858bf66da1d355b996a`
- source data policy: public Norman 2019 only; no local unpublished FRAM2 data
- full panels embedded: `107 / 107`
- selected Phase 1A-surface panels: `12`
- matched edge-level signal rows: `315`
- full model-visible edge signal records: `315`
- scFoundation subset shape: `[1412, 19018]`
- scFoundation embedding shape: `[1412, 3072]`
- control cells: `128`
- k-neighbors: `10`
- leakage check: passed, `0` forbidden key hits
- within-panel variation for primary score: `1.0`
- primary score: `real_neighbor_sfm_call_disagreement_rate`
- primary real AUROC for GEARS wrongness: `0.598779`
- random same-readout-gene control AUROC: `0.576073`
- shuffled readout-gene control AUROC: `0.513072`
- Phase 1A panel-card reference AUROC: `0.467366`
- decision: `eligible_for_small_llm_pilot`

Interpretation: this is the first Phase 1 result where the scFoundation-derived
cue is edge-level, leakage-safe, varies within panels, beats the previous
panel-card AUROC directionally, and clears the shuffled readout-gene control.
It only narrowly clears the random same-readout-gene control by about `0.023`,
so the next LLM pilot should be small and explicitly include that control. This
does not yet show that Claude faithfully uses scFoundation internals; it shows
that the edge-neighbor signal is strong enough to justify a controlled pilot.

Phase 1B signal-pilot input manifest:

- `experiments/trust_cue_attribution/results/phase1b_signal_pilot/manifest.json`
- SHA256: `87b576599d14d7beb907fa50824861fdfbcfe84c925c66e5be35aad83ff9dc38`
- status: `signal_packet_pilot_ready`
- panels: `12`
- packets / requests: `48`
- cue conditions:
  - `no_internal_signal`: `12`
  - `scfoundation_edge_neighbor_signal_shown`: `12`
  - `random_same_gene_neighbor_signal_shown`: `12`
  - `shuffled_readout_gene_neighbor_signal_shown`: `12`
- model-visible leakage check: passed
- prompt forbidden-key hits in generated request JSONL: `0`
- scorer compatibility: synthetic `signal_gated_verify` episodes scored successfully

Interpretation: this manifest remains the input-readiness checkpoint for the
small Sonnet-only LLM pilot.

Phase 1B small Sonnet LLM pilot result:

- summary:
  `experiments/trust_cue_attribution/results/phase1b_signal_pilot/summary.json`
- summary SHA256:
  `92413f6ab4e72e7f70b08907d325f456f98e8b4a062bcc03ee13639acf66152f`
- review:
  `experiments/trust_cue_attribution/results/phase1b_signal_pilot/review.json`
- review SHA256:
  `4bc203ccdd88db011cb79730b9d880faf23787c5941b7036f8e6192dbd6f3935`
- Cayuga Slurm job: `3045288`
- partition/QOS: `scu-cpu` / `normal`
- node: `c0022`
- state: `COMPLETED`, exit code `0:0`, elapsed `00:25:18`
- completion marker: `TRUST_CUE_PHASE1B_LLM_PILOT_OK`
- model: `claude-sonnet-4-6`
- episodes: `48`
- panels: `12`
- genes per condition: `315`
- total gene-level decisions: `1260`
- parse errors: `0`
- provider errors: `0`

Overall lambda `0.5` score across all four cue conditions:

- accuracy: `0.767460`
- net reward per gene: `0.633333`
- assays per gene: `0.268254`
- trust error rate: `0.156349`
- verify precision: `0.275148`
- verify recall: `0.227941`
- default-baseline rate: `0.191270`

Cue-level lambda `0.5` readout:

| cue condition | accuracy | net reward/gene | assays/gene | trust error | verify precision | verify recall | default baseline |
|---|---:|---:|---:|---:|---:|---:|---:|
| `no_internal_signal` | `0.790476` | `0.658730` | `0.263492` | `0.203175` | `0.349398` | `0.284314` | `0.050794` |
| `scfoundation_edge_neighbor_signal_shown` | `0.761905` | `0.620635` | `0.282540` | `0.152381` | `0.258427` | `0.225490` | `0.184127` |
| `random_same_gene_neighbor_signal_shown` | `0.752381` | `0.623810` | `0.257143` | `0.152381` | `0.222222` | `0.176471` | `0.209524` |
| `shuffled_readout_gene_neighbor_signal_shown` | `0.765079` | `0.630159` | `0.269841` | `0.117460` | `0.270588` | `0.225490` | `0.320635` |

Paired cue effects versus `no_internal_signal` at lambda `0.5`:

| cue condition | action changed | delta correct | delta assay | delta net | delta trust error |
|---|---:|---:|---:|---:|---:|
| `scfoundation_edge_neighbor_signal_shown` | `0.447619` | `-0.028571` | `0.019048` | `-0.038095` | `-0.050794` |
| `random_same_gene_neighbor_signal_shown` | `0.457143` | `-0.038095` | `-0.006349` | `-0.034921` | `-0.050794` |
| `shuffled_readout_gene_neighbor_signal_shown` | `0.606349` | `-0.025397` | `0.006349` | `-0.028571` | `-0.085714` |

Interpretation: the scFoundation edge-neighbor cue clearly changes Claude's
actions and reduces trust errors, but it also lowers accuracy and net reward
relative to the no-signal condition at lambda `0.5`. The placebo/control cues
also move behavior strongly, with the shuffled readout-gene control producing
the largest action-change rate and the lowest trust-error rate. Therefore this
is a useful method-validation result, not evidence that Claude faithfully uses
true SFM internals. The next Phase 1 step should refine the internal-signal
packet and control design before spending on a larger LLM matrix.

Post-pilot review decision:

- decision: `do_not_scale_larger_llm_matrix`
- reason: `real_signal_reduced_net_reward_vs_no_signal`
- real delta net: `-0.038095`
- best control delta net: `-0.028571`
- real minus best control delta net: `-0.009524`
- real action-changed rate: `0.447619`
- max control action-changed rate: `0.606349`

Interpretation: this review converts the pilot result into a concrete gate.
The next move should not be a larger Phase 1B LLM matrix using the same packet.
The next move should be deterministic signal redesign: turn the neighbor
summary into an explicit calibrated risk feature or thresholded policy, add
style-matched irrelevant and inverted-risk controls, and only then rerun a
small pilot if the deterministic signal-gated policy beats controls.

## Phase 1C Reliability-Interface Offline Gate

Phase 1C converts raw specialist/SFM evidence into an explicit reliability
interface before making any new LLM calls.

Artifacts:

- design:
  `experiments/trust_cue_attribution/results/phase1c_reliability_interface/design.json`
- design SHA256:
  `12f707af38d3dc8ccfa3305449434384228744a72f321f9e48cec3304928765f`
- offline gate:
  `experiments/trust_cue_attribution/results/phase1c_reliability_interface/offline_gate.json`
- offline gate SHA256:
  `bfed362fd5f0389310002d503193a8db6ab81a34e6afe8bb537c8ca0f252ddb4`
- command:
  `python3 experiments/trust_cue_attribution/run.py phase1c-offline-gate`
- status: `offline_gate_ready`
- decision: `eligible_for_small_phase1c_interface_pilot`
- scope: `12` panels, `315` edges, `315` edge-signal records
- no new Claude calls were made

The fixed reliability interface combines:

- additive-disagreement risk, weight `0.45`
- specialist output-margin risk, weight `0.35`
- scFoundation edge-neighbor disagreement risk, weight `0.20`

At lambda `0.5`, net reward per gene:

| policy/reference | net reward/gene |
|---|---:|
| combined real reliability interface | `0.747619` |
| combined random same-gene control | `0.744444` |
| combined shuffled readout control | `0.738095` |
| SFM margin-only interface | `0.726984` |
| neighbor-only real interface | `0.665079` |
| no-signal LLM reference | `0.658730` |
| raw edge-neighbor LLM reference | `0.620635` |
| inverted control | `0.423810` |

Gate margins:

- versus no-signal LLM: `+0.088889`
- versus raw edge-neighbor LLM: `+0.126984`
- versus margin-only ablation: `+0.020635`
- versus best control: `+0.003175`

Interpretation: the offline gate passes, but weakly. The reliability interface
is much better than asking the LLM to interpret raw edge-neighbor evidence, but
the real-vs-control margin is small. This permits only a small Phase 1C
interface pilot, not a large LLM matrix or a claim that scFoundation internals
are faithfully used.

Phase 1C small interface-pilot request preparation:

- manifest:
  `experiments/trust_cue_attribution/results/phase1c_reliability_interface/interface_request_manifest.json`
- request JSONL:
  `experiments/trust_cue_attribution/hpc_outputs/phase1c_interface_pilot/requests_phase1c_interface.jsonl`
- packet JSONL:
  `experiments/trust_cue_attribution/hpc_outputs/phase1c_interface_pilot/phase1c_interface_packets.jsonl`
- status: `interface_request_pilot_ready`
- panels: `12`
- packets / requests: `48`
- cue counts: `12` each for `no_internal_signal`,
  `edge_neighbor_signal_shown`, `calibrated_reliability_interface_shown`,
  and `inverted_reliability_interface_control`
- leakage check: passed
- no new Claude calls were made

Interpretation: this prepares the next small Sonnet-only interface pilot. It is
not itself an LLM result. The decisive comparison is whether the calibrated
interface improves net reward over both `no_internal_signal` and
`edge_neighbor_signal_shown`, while the inverted-control interface does not
dominate behavior.

## Phase 1C Specialist Metric Sensitivity Check

This check stress-tests the "GEARS approx additive" reading (which underpins the
flat-reward-surface interpretation) against the Miller et al. 2025 caveat that
such negative results can be artifacts of coarse / mis-calibrated metrics. It
re-scores the same GEARS and additive-baseline calls with threshold-free and
continuous metrics, plus an honest leave-one-panel-out (LOPO) effect-call
threshold recalibration. It makes no LLM calls and exposes no model-visible
leakage.

Artifacts:

- analysis: `experiments/trust_cue_attribution/phase1c_specialist_metric_check.py`
- result: `experiments/trust_cue_attribution/results/phase1c_reliability_interface/specialist_metric_check.json`
- result SHA256: `6a5fd43004742ed7d53753eaa0b152716d2e10b6185ff48c9fd4feb09436101b`
- command: `python3 experiments/trust_cue_attribution/run.py phase1c-specialist-metric-check`
- validation: reproduces the offline-gate binary accuracies exactly
  (phase1c_12 GEARS `0.67619` = `trust_all_sfm`; additive `0.666667` =
  `always_additive`).

Threshold-free discrimination (`abs(log2FC)` AUROC for true effect) and
continuous magnitude fidelity (Pearson vs measured `raw_log2FC`):

| slice | GEARS AUROC | additive AUROC | GEARS Pearson | additive Pearson |
|---|---:|---:|---:|---:|
| `phase1c_12` | `0.781885` | `0.661721` | `0.566949` | `0.779584` |
| `observed_additive` (combo) | `0.629246` | `0.625530` | `0.614820` | `0.924917` |
| `full_107` | `0.553017` | `0.575086` | `0.589895` | `0.675001` |

Honest LOPO threshold recalibration, net reward per gene at lambda `0.5`:

| slice | trust_all `@0.25` | trust_all LOPO | always_additive LOPO | oracle LOPO |
|---|---:|---:|---:|---:|
| `full_107` | `0.686` | `0.694` | `0.676` | `0.847` |
| `phase1c_12` | `0.676` | `0.727` | `0.635` | `0.863` |
| `observed_additive` | `0.677` | `0.712` | `0.818` | `0.856` |

Decision: `metric_mismatch_not_uniform_straw_man`.

Interpretation: the "GEARS approx additive" conclusion is regime- and
metric-dependent. On the combinatorial (`observed_additive`) slice the additive
baseline still matches or beats GEARS even on threshold-free and continuous
metrics (additive Pearson `0.925` vs GEARS `0.615`), consistent with the
published critique that combo effects are largely additive. But on the
`phase1c_12` surface used for all Phase 1C conclusions, GEARS carries real
effect-ranking signal (AUROC `0.782` vs `0.662`) that the fixed binary
effect-call at `abs(log2FC) >= 0.25` discards: honest LOPO recalibration lifts
`trust_all_sfm` net reward `0.676 -> 0.727` and opens a GEARS-over-additive gap
of about `+0.092`. This `phase1c_12` lift is `n=12`-fragile (additive net drops
under LOPO, signalling unstable threshold selection), and the `full_107`
recalibration gain is small (`0.686 -> 0.694`), so it does not overturn the
flat-surface read at scale.

Claim boundary: this concerns only the GEARS prediction substrate and the binary
reward metric. It does not address the scFoundation reliability cue, which
remains near-noise (edge AUROC `0.599` vs `0.576` random), nor the small-pilot
statistical power. Actionable takeaway: report threshold-free / ranking metrics
alongside the binary reward, and treat the binary effect/no-effect reward as a
known understatement of GEARS on the `phase1c_12` surface.

## Phase 1 Hyper Review

Phase 1 hyper-review artifact:

- `experiments/trust_cue_attribution/results/phase1_hyper_review/REVIEW.md`
- SHA256: `38a18d30e97bad07859300c53c23bfa87de72bc70f0cb912d98f3b5f45875c64`

Review bottom line: Phase 1 is not ready for a larger LLM matrix or a
true-SFM interpretation claim. It is ready for a small HPC prototype of an
edge-level scFoundation-derived cue. The current best route remains
`scfoundation_neighbor_edge_support`, with explicit controls to avoid turning
the result into baseline-disagreement in disguise.

Panel notes: FOXA1+FOXF1 shows a real-signal-specific gain, but
MAP2K3+SLC38A2 has a slightly larger placebo gain, and several panels show
zero or matching real/placebo deltas. Correlations between coarse panel-level
embedding distances and routing changes are exploratory at `n = 12` and are not
stable enough to justify scaling. The next step should sharpen the internal
signal into more decision-relevant evidence and add a stronger irrelevant-signal
control before spending on a larger Phase 1A matrix.

## Phase 0B Frozen Result Anchor

Phase 0B scope:

- Full GEARS/Norman dry-run substrate: 107 biological panels.
- Main non-leakage request records: 642.
- Real LLM full run: 642 Sonnet 4.6 episodes.
- Cue conditions: six non-leakage cue conditions, 107 episodes each.
- Large source artifacts remain ignored under `hpc_outputs/phase0_smoke/`.
- Compact tracked freeze artifacts:
  - `experiments/trust_cue_attribution/results/phase0b_freeze/manifest.json`
  - `experiments/trust_cue_attribution/results/phase0b_freeze/summary.json`

Phase 0B artifact hashes:

| artifact | SHA256 |
|---|---|
| `manifest.json` | `75a209c51415784e921d38e9198fc9094e924eb32252121a2906380bea91d1dd` |
| `summary.json` | `a69b6ece957ccf0ee05abd9ae42045ab452aed951debd2bf1e699d4dca420366` |

Phase 0B output integrity:

- parse errors: 0
- provider errors: 0
- episodes missing actions: 0
- gene-key mismatch episodes: 1
- mismatch example: `FOXF1+FOXL2::confidence_shown` used `CDKN1B` where the expected packet gene was `CDKN1C`; the scorer treats the expected gene as uncovered/deferred.

Frozen full Sonnet 4.6 run:

| lambda | accuracy | assays/gene | net/gene | trust error | verify precision | verify recall | default rate | defer rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.2 | 0.773 | 0.183 | 0.737 | 0.150 | 0.397 | 0.231 | 0.275 | 0.003 |
| 0.5 | 0.773 | 0.183 | 0.682 | 0.150 | 0.397 | 0.231 | 0.275 | 0.003 |
| 0.8 | 0.773 | 0.183 | 0.627 | 0.150 | 0.397 | 0.231 | 0.275 | 0.003 |

Baseline comparison at `lambda = 0.5`:

| baseline | Sonnet delta net/gene |
|---|---:|
| `trust_all_sfm` | -0.004 |
| `always_additive` | +0.007 |
| `signal_gated_verify` | +0.010 |
| `random_verify_at_budget` | +0.049 |
| `verify_all` | +0.182 |
| `oracle_verify` | -0.161 |

Break-even interpretation:

- Sonnet is near-tied but slightly below `trust_all_sfm` at lambda 0.5.
- Sonnet breaks even versus `trust_all_sfm` at lambda about 0.476.
- Sonnet breaks even versus `always_additive` at lambda about 0.536.
- Sonnet becomes better than `verify_all` above lambda about 0.277.
- Sonnet remains below `oracle_verify` across the planned lambda values.

Cue-level result at `lambda = 0.5`:

| cue | accuracy | assays/gene | net/gene | trust error | default rate |
|---|---:|---:|---:|---:|---:|
| `confidence_shown` | 0.784 | 0.101 | 0.733 | 0.043 | 0.638 |
| `additive_disagreement_shown` | 0.817 | 0.243 | 0.695 | 0.063 | 0.387 |
| `anonymized_genes` | 0.779 | 0.208 | 0.675 | 0.203 | 0.072 |
| `no_cue` | 0.772 | 0.202 | 0.671 | 0.213 | 0.053 |
| `model_name_shown` | 0.765 | 0.201 | 0.665 | 0.205 | 0.088 |
| `misleading_reliability_card` | 0.723 | 0.139 | 0.653 | 0.172 | 0.413 |

Paired effects versus `no_cue` at `lambda = 0.5`:

| cue | action changed | delta correct | delta assay | delta net | delta trust error |
|---|---:|---:|---:|---:|---:|
| `confidence_shown` | 0.698 | +0.012 | -0.101 | +0.062 | -0.170 |
| `additive_disagreement_shown` | 0.577 | +0.045 | +0.041 | +0.024 | -0.149 |
| `anonymized_genes` | 0.185 | +0.007 | +0.006 | +0.004 | -0.010 |
| `model_name_shown` | 0.136 | -0.007 | -0.001 | -0.006 | -0.008 |
| `misleading_reliability_card` | 0.676 | -0.049 | -0.063 | -0.018 | -0.041 |

Phase 0B claim boundary:

Supported:

- Full non-leakage Sonnet routing is strongly cue-sensitive.
- Additive-disagreement evidence improves routing relative to `no_cue`.
- Misleading reliability framing changes behavior and hurts accuracy/net reward.
- Self-reported explanations frequently mention unavailable evidence.
- The oracle gap shows useful routing signal remains uncaptured.

Not supported:

- The LLM is a robust calibrated SFM orchestrator.
- The result generalizes to true SFMs.
- Confidence-like cues are calibrated uncertainty.
- The learned/router layer is ready.
- Internal SFM signals are being used faithfully.

Best current claim:

> In a full GEARS/Norman dry run, the LLM reasoning layer is strongly cue-sensitive and only weakly calibrated as a cost-aware orchestrator. Explicit reliability signals can improve routing, but reliability-looking cues can also mislead it; explanations often report unavailable evidence.

## Phase 0B Robustness Anchor

Phase 0C robustness summary for the Phase 0B run:

- `experiments/trust_cue_attribution/results/phase0b_robustness/summary.json`
- SHA256: `47b70b5de3bb6c145258f6ce9d4f8eae58a601e46ffd94ecf5cb4898e7b568cf`
- bootstrap unit: biological panel
- bootstrap draws: 1000
- seed: 13
- lambda: 0.5

Panel-cluster bootstrap intervals for paired cue effects:

| cue | delta net estimate | 95% CI |
|---|---:|---:|
| `confidence_shown` | +0.062 | [+0.043, +0.081] |
| `additive_disagreement_shown` | +0.024 | [+0.012, +0.037] |
| `anonymized_genes` | +0.004 | [-0.007, +0.014] |
| `model_name_shown` | -0.006 | [-0.014, +0.001] |
| `misleading_reliability_card` | -0.018 | [-0.033, -0.004] |

Panel-cluster bootstrap intervals for Sonnet-vs-baseline net/gene deltas:

| baseline | delta net estimate | 95% CI |
|---|---:|---:|
| `trust_all_sfm` | -0.004 | [-0.013, +0.006] |
| `always_additive` | +0.007 | [-0.026, +0.039] |
| `signal_gated_verify` | +0.010 | [-0.011, +0.031] |
| `random_verify_at_budget` | +0.049 | [+0.037, +0.062] |
| `verify_all` | +0.182 | [+0.165, +0.199] |
| `oracle_verify` | -0.161 | [-0.172, -0.150] |

Robustness interpretation:

- The constructive `additive_disagreement_shown` cue remains positive under panel-cluster bootstrap.
- The harmful `misleading_reliability_card` cue remains negative under panel-cluster bootstrap.
- The comparison to `trust_all_sfm`, `always_additive`, and `signal_gated_verify` is not robustly positive.
- The explanation-faithfulness issue is robust: in `no_cue`, unavailable baseline self-report is 0.944 with 95% CI [0.897, 0.981].

## Phase 0A Frozen Result Anchor

Phase 0A scope:

- Full GEARS/Norman dry-run substrate: 107 panels.
- Additive-coverage subset: 45 panels.
- Full cue packets / request records: 749.
- Main non-leakage cue packets: 642.
- Stratified pilot: 12 panels, 72 requests, 4 low / 4 mid / 4 high wrong-rate panels.
- Real LLM pilot: 72 Sonnet 4.6 episodes and 72 Opus 4.8 episodes.

Primary metric basis: micro gene-weighted. Macro-panel metrics remain
diagnostics under `macro_panel_*` in scorer outputs and are not the main numbers
below.

Frozen deterministic baselines at `lambda = 0.5`:

| substrate | policy | accuracy | assays/gene | net/gene |
|---|---|---:|---:|---:|
| full | trust_all_sfm | 0.681 | 0.000 | 0.681 |
| full | always_additive | 0.675 | 0.000 | 0.675 |
| full | signal_gated_verify | 0.770 | 0.201 | 0.670 |
| full | oracle_verify | 1.000 | 0.319 | 0.840 |
| additive subset | trust_all_sfm | 0.673 | 0.000 | 0.673 |
| additive subset | always_additive | 0.812 | 0.000 | 0.812 |
| additive subset | signal_gated_verify | 0.846 | 0.202 | 0.745 |
| additive subset | oracle_verify | 1.000 | 0.327 | 0.836 |

Frozen Sonnet 4.6 vs Opus 4.8 pilot at `lambda = 0.5`:

| model | accuracy | assays/gene | net/gene | trust error | verify recall | defer rate |
|---|---:|---:|---:|---:|---:|---:|
| Sonnet 4.6 | 0.784 | 0.184 | 0.692 | 0.152 | 0.251 | 0.003 |
| Opus 4.8 | 0.809 | 0.293 | 0.662 | 0.143 | 0.372 | 0.016 |

Frozen paired cue effects at `lambda = 0.5`:

| model | cue | action changed | delta correct | delta assay | delta net | delta trust error |
|---|---|---:|---:|---:|---:|---:|
| Sonnet 4.6 | additive_disagreement_shown | 0.523 | +0.062 | +0.105 | +0.009 | -0.124 |
| Sonnet 4.6 | misleading_reliability_card | 0.675 | -0.046 | -0.046 | -0.023 | -0.025 |
| Opus 4.8 | additive_disagreement_shown | 0.415 | +0.050 | +0.065 | +0.017 | -0.046 |
| Opus 4.8 | misleading_reliability_card | 0.678 | -0.040 | +0.133 | -0.107 | +0.025 |

Frozen lambda read:

- Micro-primary Opus/Sonnet break-even lambda: approximately `0.223`.
- Below that, Opus's extra verification can pay off.
- Above that, Sonnet's lower assay use gives higher net reward.

Frozen sanity checks:

- Oracle beats random on the full substrate at `lambda = 0.5`.
- Always-additive beats trust-all-SFM on the additive-coverage subset.
- Opus/Sonnet break-even remains near the prior pilot estimate.
- Feature-signature router does not beat always-Sonnet.
- Packet oracle beats always-Sonnet, so useful routing signal remains uncaptured.

Sections below include historical smoke and pilot notes. Use the Phase 0A
freeze artifacts above for exact current aggregate values.

Reward-summary update, 2026-06-17: the scorer now reports primary aggregate
metrics as micro gene-weighted summaries and preserves macro-panel diagnostics
under `macro_panel_*` keys. It also reports `defer_rate`, `coverage_rate`,
`sfm_wrong_rate`, default-baseline source rates, and default-baseline error
rate. Older tables below remain directionally valid, but newly generated JSON
summaries should be treated as authoritative for exact aggregate values.

Environment trajectory update, 2026-06-17: completed Sonnet 4.6 and Opus 4.8
pilot episodes have been converted into environment-shaped trajectory JSONL
records:

- `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_trajectories.jsonl`
- `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_trajectory_summary.json`
- `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-opus-4-8_pilot72_main_trajectories.jsonl`
- `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-opus-4-8_pilot72_main_trajectory_summary.json`

These trajectory records preserve observations, actions, scores, rewards,
provider metadata, and self-reported cues. Raw provider output is excluded by
default.

Preference-pair update, 2026-06-17: Sonnet 4.6 and Opus 4.8 trajectory records
were compared packet-by-packet using trajectory reward at `lambda = 0.5`.

Artifacts:

- `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_sonnet4_6_vs_opus4_8_pilot72_preference_pairs.jsonl`
- `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_sonnet4_6_vs_opus4_8_pilot72_preference_summary.json`

Summary:

- Non-tie preference pairs: 60 out of 72 packets.
- Chosen models: Sonnet 4.6 = 36, Opus 4.8 = 24.
- Mean reward delta among non-tie pairs: 1.758.
- Cue-specific note: Opus is chosen more often under `no_cue` and
  `additive_disagreement_shown`, while Sonnet is chosen more often under
  `confidence_shown`, `misleading_reliability_card`, `model_name_shown`, and
  `anonymized_genes`.

Router baseline update, 2026-06-17: a conservative leave-one-panel-out router
was evaluated using only `cue_condition` mean reward from matched Sonnet/Opus
trajectories.

Artifact:

- `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_sonnet4_6_vs_opus4_8_pilot72_router_eval.json`

Micro trajectory reward per gene at `lambda = 0.5`:

- Always Sonnet 4.6: 0.692
- Always Opus 4.8: 0.662
- Cue-mean leave-panel-out router: 0.688
- Packet oracle: 0.705

Interpretation: cue-only routing is not enough; it underperforms always choosing
Sonnet in this small pilot. However, the packet oracle remains higher than both
single-model policies, so there is useful routing signal left to identify. The
next router should use model-visible packet features beyond cue condition, not
hidden correctness labels.

Feature-router update, 2026-06-17: model-visible trajectory features were added
for router analysis. These include cue condition, number of genes, SFM effect
rate, SFM effect-size summary, displayed confidence, displayed baseline
disagreement, displayed reliability cards, and anonymization. They are extracted
from `observation` only.

Artifacts:

- `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_sonnet4_6_vs_opus4_8_pilot72_feature_rows.jsonl`
- `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_sonnet4_6_vs_opus4_8_pilot72_feature_summary.json`
- `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_sonnet4_6_vs_opus4_8_pilot72_feature_signature_router_eval.json`

Feature summary:

- Feature rows: 144 trajectories.
- Binned feature signatures: 40.

Micro trajectory reward per gene at `lambda = 0.5`:

- Cue-only leave-panel-out router: 0.688
- Feature-signature leave-panel-out router: 0.691
- Always Sonnet 4.6: 0.692
- Packet oracle: 0.705

Interpretation: richer model-visible features improve slightly over cue-only
routing but still do not beat always choosing Sonnet in this 72-packet pilot.
This suggests the router direction is plausible but underpowered; the next step
needs either more packets, less sparse features, or a regularized router model.

Required result blocks:

1. Panel summary: number of panels, edges, wrong-rate, baseline coverage.
2. Baseline table: `trust_all_sfm`, `always_additive`, `signal_gated_verify`, `oracle_verify`, `random_verify_at_budget`, `verify_all`.
3. LLM unaided routing: no-cue condition compared with baselines.
4. Cue sensitivity: action shifts across cue conditions.
5. Fail + fix: signal-gated improvement using additive-disagreement reliability signal.
6. Explanation faithfulness: self-reported cues vs measured cue sensitivity.

## Cayuga Phase 0 Smoke Check

Validation job:

- Cayuga job id: `3043801`
- Python: `/usr/bin/python3.12`
- Remote root: `/scratch/USER/LLM_SFM_interpretability`
- Local synced outputs: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/`
- Test result: `16 tests OK`
- Job marker: `TRUST_CUE_PHASE0_SMOKE_OK`

The GEARS / Verify-or-Trust substrate builds successfully on Cayuga:

- Full substrate: 107 panels.
- Cue packets: 749 packets across 7 cue conditions.
- Request records: 749 prompt records materialized without API calls.
- Mock provider episodes: 12 `mock_defer` records generated and scored as an API-free runner wiring check.
- Claude provider path: `anthropic_messages` added and API-free response parsing tested.
- Synthetic `signal_gated_verify` episodes: 749 records.
- Synthetic episode scores: generated through the same episode scorer intended for real LLM runs.
- Additive-coverage subset: 45 panels.

Full-panel baseline smoke at λ=0.5:

| policy | accuracy | assays/gene | net/gene |
|---|---:|---:|---:|
| trust_all_sfm | 0.681 | 0.000 | 0.681 |
| always_additive | 0.675 | 0.000 | 0.675 |
| signal_gated_verify | 0.770 | 0.201 | 0.670 |
| oracle_verify | 1.000 | 0.319 | 0.840 |

Combo/additive-coverage subset baseline smoke at λ=0.5:

| policy | accuracy | assays/gene | net/gene |
|---|---:|---:|---:|
| trust_all_sfm | 0.673 | 0.000 | 0.673 |
| always_additive | 0.812 | 0.000 | 0.812 |
| signal_gated_verify | 0.846 | 0.202 | 0.745 |
| oracle_verify | 1.000 | 0.327 | 0.836 |

Interpretation: the full panel includes single perturbations where observed-additive is unavailable and falls back to no-change, so `always_additive` should not be read globally. The additive-coverage subset preserves the perturbation-baseline lesson: the cheap additive baseline is a real action, not a footnote. Signal-gated verification raises accuracy, but the cost term controls whether it beats free defaulting.

Synthetic episode scorer summary for `policy::signal_gated_verify` on all 642 cue packets at λ=0.5:

| metric | value |
|---|---:|
| accuracy | 0.770 |
| assays/gene | 0.201 |
| net/gene | 0.670 |
| verify precision | 0.349 |
| verify recall | 0.244 |
| default baseline rate | 0.799 |

This confirms that the request/episode/scoring path is internally consistent before any API-based LLM run.

Latest schema change: `raw_assay_stats_shown` was added as a leakage-aware positive-control cue. It exposes measured DE statistics (`raw_log2FC`, `raw_se`, `raw_q`, `n_trt`, `n_cntrl`) only in that condition. `confidence_shown` now marks its confidence as `magnitude_proxy_not_calibrated`, because GEARS does not provide calibrated uncertainty in the current substrate.

API-free runner smoke:

| check | value |
|---|---:|
| provider | `mock_defer` |
| episodes | 12 |
| scored rows | 12 |
| expected net/gene | 0.000 |

The mock provider is not a scientific result. It intentionally emits `defer` for every gene so malformed request/episode/scoring interfaces fail before paid or rate-limited LLM calls.

## Claude Pilot: 24 Requests

Status: real Claude API pilot completed; not a final result.

Run metadata:

- Cayuga job id: `3043795`
- Provider: `anthropic_messages`
- Model: `claude-sonnet-4-6`
- Scope: first 24 requests = 4 panels x 6 cue conditions
- Lambda: `0.5`
- Episodes: 24
- Parse/provider errors: none observed
- Output episodes: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_episodes_limit_24.jsonl`
- Output scores: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_scores_limit_24_lambda_0.5.json`

Overall pilot summary:

| metric | value |
|---|---:|
| accuracy | 0.816 |
| assays/gene | 0.155 |
| default baseline rate | 0.326 |
| net/gene | 0.738 |
| trust error rate | 0.119 |
| verify precision | 0.498 |
| verify recall | 0.300 |

Cue-condition averages:

| cue condition | accuracy | assays/gene | default rate | net/gene | trust error | verify precision | verify recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| no_cue | 0.840 | 0.209 | 0.000 | 0.735 | 0.160 | 0.480 | 0.410 |
| model_name_shown | 0.848 | 0.209 | 0.008 | 0.743 | 0.152 | 0.530 | 0.441 |
| anonymized_genes | 0.812 | 0.152 | 0.085 | 0.736 | 0.147 | 0.458 | 0.295 |
| confidence_shown | 0.796 | 0.085 | 0.725 | 0.753 | 0.067 | 0.438 | 0.153 |
| additive_disagreement_shown | 0.837 | 0.196 | 0.558 | 0.739 | 0.042 | 0.584 | 0.434 |
| misleading_reliability_card | 0.762 | 0.078 | 0.580 | 0.724 | 0.144 | 0.500 | 0.069 |

Initial read: additive disagreement behaved like a useful reliability signal in this small pilot, lowering trust errors and improving verify recall. Confidence and misleading reliability cues strongly changed action mix toward `default_baseline`, so the next analysis should separate productive reliability use from cue overreaction. This pilot is too small for a scientific claim, but it validates the real-LLM path and shows measurable cue sensitivity.

## Claude Positive-Control Pilot: Raw Assay Stats

Status: one-panel real Claude positive-control run completed after adding `raw_assay_stats_shown`.

Run metadata:

- Cayuga job id: `3043802`
- Provider: `anthropic_messages`
- Model: `claude-sonnet-4-6`
- Scope: first 7 requests = `AHR+KLF1` panel x 7 cue conditions
- Lambda: `0.5`
- Episodes: 7
- Parse/provider errors: none observed

Per-cue scores:

| cue condition | accuracy | assays/gene | default rate | net/gene | trust error | verify recall |
|---|---:|---:|---:|---:|---:|---:|
| no_cue | 0.767 | 0.167 | 0.033 | 0.683 | 0.233 | 0.222 |
| model_name_shown | 0.767 | 0.200 | 0.033 | 0.667 | 0.233 | 0.222 |
| anonymized_genes | 0.767 | 0.167 | 0.033 | 0.683 | 0.233 | 0.222 |
| confidence_shown | 0.733 | 0.000 | 0.733 | 0.733 | 0.133 | 0.000 |
| additive_disagreement_shown | 0.867 | 0.300 | 0.100 | 0.717 | 0.067 | 0.667 |
| misleading_reliability_card | 0.700 | 0.033 | 0.433 | 0.683 | 0.267 | 0.000 |
| raw_assay_stats_shown | 1.000 | 0.400 | 0.000 | 0.800 | 0.000 | 1.000 |

Initial read: the raw-assay-stat condition behaves as a positive control should. When Claude sees measured DE statistics, it catches every wrong SFM case in this panel. This should not be mixed with ordinary SFM trust cues because it is answer-like evidence. Also note an explanation-faithfulness issue: Claude's rationales used raw FC/q-values, but `self_reported_cues` did not explicitly list raw assay stats.

Episode-analysis note: `analyze-episodes` now summarizes action counts, self-reported cues, and rationale keyword traces by cue condition. In the raw-assay positive-control pilot, rationale text mentioned raw assay evidence for all 30 genes under `raw_assay_stats_shown`, while `self_reported_cues` did not explicitly include raw assay stats. This is a concrete example of an explanation-faithfulness gap.

## Stratified Main Pilot Request Set

Status: request set prepared; no new API calls in this step.

- Cayuga smoke job after selector: `3043805`
- Test result: `18 tests OK`
- Selected panels: 12
- Requests: 72
- Cue conditions: six non-leakage main cues
- Excluded cue: `raw_assay_stats_shown`
- Request file: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/requests_pilot72_main.jsonl`
- Manifest: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/requests_pilot72_main_manifest.json`

Selected panel balance:

| wrong-rate bin | panels |
|---|---:|
| low | 4 |
| mid | 4 |
| high | 4 |

This file is the recommended next real Claude run before scaling to the full 749-request set.

## Claude Stratified Main Pilot: 72 Requests

Status: completed real Claude run on the stratified non-leakage pilot.

Run metadata:

- Cayuga job id: `3043806`
- Provider: `anthropic_messages`
- Model: `claude-sonnet-4-6`
- Scope: 72 requests = 12 panels x 6 main non-leakage cue conditions
- Excluded cue: `raw_assay_stats_shown`
- Lambda: `0.5`
- Episodes: 72
- Parse/provider errors: none observed
- Output episodes: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_episodes.jsonl`
- Output scores: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_scores_lambda_0.5.json`
- Output analysis: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_analysis.json`
- Output paired cue effects: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_paired_effects.json`

Overall summary:

| metric | value |
|---|---:|
| accuracy | 0.779 |
| assays/gene | 0.183 |
| default baseline rate | 0.272 |
| net/gene | 0.687 |
| trust error rate | 0.153 |
| verify precision | 0.409 |
| verify recall | 0.263 |

Cue-condition averages:

| cue condition | accuracy | assays/gene | default rate | net/gene | trust error | verify precision | verify recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| no_cue | 0.766 | 0.173 | 0.085 | 0.680 | 0.208 | 0.465 | 0.270 |
| model_name_shown | 0.770 | 0.187 | 0.082 | 0.677 | 0.209 | 0.404 | 0.250 |
| anonymized_genes | 0.779 | 0.219 | 0.049 | 0.669 | 0.211 | 0.420 | 0.312 |
| confidence_shown | 0.802 | 0.117 | 0.645 | 0.744 | 0.037 | 0.385 | 0.164 |
| additive_disagreement_shown | 0.830 | 0.278 | 0.325 | 0.691 | 0.081 | 0.510 | 0.475 |
| misleading_reliability_card | 0.725 | 0.127 | 0.448 | 0.662 | 0.173 | 0.269 | 0.107 |

Initial read: the stratified pilot preserves the main pattern from smaller pilots. Additive disagreement improves verification recall and lowers trust errors, but at a higher assay rate. Misleading reliability cards reduce accuracy and verify recall. Confidence presentation strongly shifts Claude toward `default_baseline`, which improves net/gene in this pilot but needs careful interpretation because the confidence is a magnitude proxy, not calibrated SFM uncertainty.

Explanation-faithfulness note: the episode analysis again shows self-report mismatch. In `no_cue`, Claude often self-reported cues such as model name, confidence, and baseline disagreement even when these were not actually provided. This supports treating self-reported rationales as behavior to audit, not ground truth.

Paired cue effects compare each cue against `no_cue` for the same panel/gene at λ=0.5:

| cue condition | matched gene pairs | action changed | Δcorrect | Δassay | Δnet | Δtrust error |
|---|---:|---:|---:|---:|---:|---:|
| model_name_shown | 323 | 0.139 | 0.000 | 0.012 | -0.006 | 0.000 |
| anonymized_genes | 323 | 0.136 | 0.009 | 0.046 | -0.014 | 0.003 |
| confidence_shown | 323 | 0.690 | 0.037 | -0.056 | 0.065 | -0.167 |
| additive_disagreement_shown | 323 | 0.523 | 0.062 | 0.105 | 0.009 | -0.124 |
| misleading_reliability_card | 323 | 0.675 | -0.046 | -0.046 | -0.023 | -0.025 |

Paired read: additive disagreement is the cleanest constructive signal. It changes many decisions, improves correctness, and strongly reduces trust errors, but it spends more assays. Misleading reliability also changes many decisions, while hurting correctness and net reward; this supports the audit claim that the reasoning layer is cue-sensitive rather than intrinsically calibrated. The confidence cue is useful in this pilot mostly because it pushes Claude away from trusting the SFM and toward `default_baseline`; since this confidence is only a magnitude proxy, it should be treated as a cautionary result rather than a validated uncertainty signal.

## Claude Opus 4.8 Comparison: Same 72 Requests

Status: completed real Claude run on the same stratified non-leakage pilot used for Sonnet 4.6.

Run metadata:

- Cayuga job id: `3043812`
- Provider: `anthropic_messages`
- Model: `claude-opus-4-8`
- Scope: same 72 requests = 12 panels x 6 main non-leakage cue conditions
- Lambda: `0.5`
- Episodes: 72
- Parse/provider errors: none observed in progress/error logs
- Output episodes: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-opus-4-8_pilot72_main_episodes.jsonl`
- Output scores: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-opus-4-8_pilot72_main_scores_lambda_0.5.json`
- Output analysis: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-opus-4-8_pilot72_main_analysis.json`
- Output paired cue effects: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-opus-4-8_pilot72_main_paired_effects.json`

Overall Sonnet 4.6 vs Opus 4.8 at λ=0.5:

| metric | Sonnet 4.6 | Opus 4.8 | Opus - Sonnet |
|---|---:|---:|---:|
| accuracy | 0.779 | 0.804 | +0.026 |
| assays/gene | 0.183 | 0.293 | +0.110 |
| default baseline rate | 0.272 | 0.154 | -0.118 |
| net/gene | 0.687 | 0.658 | -0.029 |
| trust error rate | 0.153 | 0.145 | -0.008 |
| verify precision | 0.409 | 0.412 | +0.003 |
| verify recall | 0.263 | 0.383 | +0.120 |

Cue-condition averages for Opus 4.8:

| cue condition | accuracy | assays/gene | default rate | net/gene | trust error | verify precision | verify recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| no_cue | 0.814 | 0.264 | 0.135 | 0.682 | 0.159 | 0.429 | 0.368 |
| model_name_shown | 0.785 | 0.282 | 0.049 | 0.644 | 0.182 | 0.377 | 0.349 |
| anonymized_genes | 0.788 | 0.263 | 0.000 | 0.656 | 0.212 | 0.385 | 0.336 |
| confidence_shown | 0.799 | 0.223 | 0.533 | 0.687 | 0.029 | 0.550 | 0.361 |
| additive_disagreement_shown | 0.860 | 0.327 | 0.049 | 0.697 | 0.113 | 0.523 | 0.580 |
| misleading_reliability_card | 0.781 | 0.400 | 0.159 | 0.581 | 0.175 | 0.210 | 0.301 |

Paired cue effects, Opus 4.8 vs `no_cue` for the same panel/gene:

| cue condition | action changed | Δcorrect | Δassay | Δnet | Δtrust error |
|---|---:|---:|---:|---:|---:|
| model_name_shown | 0.276 | -0.025 | 0.019 | -0.034 | 0.022 |
| anonymized_genes | 0.217 | -0.025 | 0.000 | -0.025 | 0.053 |
| confidence_shown | 0.474 | -0.012 | -0.040 | 0.008 | -0.124 |
| additive_disagreement_shown | 0.415 | 0.050 | 0.065 | 0.017 | -0.046 |
| misleading_reliability_card | 0.678 | -0.040 | 0.133 | -0.107 | 0.025 |

Comparison read: Opus 4.8 is not simply "better" for this orchestrator objective. It improves accuracy and wrong-SFM verification recall, but it pays for that by verifying more often, so net reward falls at λ=0.5. The constructive additive-disagreement cue remains useful and is slightly more net-positive for Opus than Sonnet, because Opus gains correctness with less extra assay cost. However, the misleading reliability card remains a major failure mode: Opus changes behavior about as often as Sonnet, spends more assays, and loses much more net reward. This is strong evidence that stronger reasoning does not automatically solve reliability-cue calibration.

## Lambda Sweep: Sonnet 4.6 vs Opus 4.8

Status: completed from existing episode JSONL files; no new LLM/API calls.

Output summary: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/lambda_sweep_summary_sonnet4_6_vs_opus4_8.json`

Overall net/gene by assay-cost λ:

| lambda | Sonnet 4.6 | Opus 4.8 | Opus - Sonnet |
|---:|---:|---:|---:|
| 0.2 | 0.742 | 0.746 | +0.004 |
| 0.5 | 0.687 | 0.658 | -0.029 |
| 0.8 | 0.632 | 0.570 | -0.062 |

Break-even λ for Opus vs Sonnet is approximately `0.234`. Below this, verification is cheap enough that Opus's higher accuracy and verify recall slightly win. Above this, Opus's extra assay use makes it a worse cost-aware orchestrator.

Paired additive-disagreement cue, Δnet vs `no_cue`:

| lambda | Sonnet 4.6 | Opus 4.8 |
|---:|---:|---:|
| 0.2 | +0.041 | +0.037 |
| 0.5 | +0.009 | +0.017 |
| 0.8 | -0.022 | -0.002 |

Paired misleading-reliability cue, Δnet vs `no_cue`:

| lambda | Sonnet 4.6 | Opus 4.8 |
|---:|---:|---:|
| 0.2 | -0.037 | -0.067 |
| 0.5 | -0.023 | -0.107 |
| 0.8 | -0.009 | -0.147 |

Lambda-sweep read: the Opus comparison is aligned with the original hypothesis that stronger models can be better at raw accuracy while worse under non-trivial verification cost. The additive-disagreement cue is robustly useful at low/medium cost and close to neutral for Opus even at high cost. The misleading reliability card remains a real failure mode, especially for Opus, because it induces costly extra verification while still reducing correctness.

## Cue-Attribution Regression

Status: completed from existing episode JSONL files; no new LLM/API calls.

Method: one-vs-rest categorical logistic cue attribution with `no_cue` as the baseline. Because the current cue matrix shows one cue at a time, each coefficient is a log-odds shift for choosing a target action under that cue versus `no_cue`. Positive means the cue makes that action more likely; negative means less likely. Coefficients use additive smoothing, so extreme zero-count cases are finite.

Output files:

- Sonnet 4.6: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_cue_attribution.json`
- Opus 4.8: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-opus-4-8_pilot72_main_cue_attribution.json`

Selected log-odds coefficients vs `no_cue`:

| model | cue | verify_assay | trust_sfm | default_baseline |
|---|---|---:|---:|---:|
| Sonnet 4.6 | additive_disagreement_shown | +0.607 | -1.423 | +1.648 |
| Sonnet 4.6 | confidence_shown | -0.449 | -2.250 | +3.009 |
| Sonnet 4.6 | misleading_reliability_card | -0.363 | -1.321 | +2.189 |
| Opus 4.8 | additive_disagreement_shown | +0.312 | +0.129 | -1.249 |
| Opus 4.8 | confidence_shown | -0.218 | -1.741 | +1.942 |
| Opus 4.8 | misleading_reliability_card | +0.606 | -0.660 | +0.146 |

Rate shifts behind selected coefficients:

| model | cue | verify_assay Δrate | trust_sfm Δrate | default_baseline Δrate |
|---|---|---:|---:|---:|
| Sonnet 4.6 | additive_disagreement_shown | +0.105 | -0.334 | +0.235 |
| Sonnet 4.6 | confidence_shown | -0.056 | -0.511 | +0.563 |
| Sonnet 4.6 | misleading_reliability_card | -0.046 | -0.310 | +0.362 |
| Opus 4.8 | additive_disagreement_shown | +0.065 | +0.031 | -0.096 |
| Opus 4.8 | confidence_shown | -0.040 | -0.390 | +0.393 |
| Opus 4.8 | misleading_reliability_card | +0.133 | -0.164 | +0.019 |

Cue-attribution read: Sonnet's main cue response is to leave `trust_sfm` and move toward `default_baseline`, especially under confidence and misleading reliability framing. Opus's misleading-card failure mode is different: it moves away from trust but often into costly verification rather than cheap defaulting. This explains why misleading reliability hurts Opus more under lambda sweep: the cue does not merely change the answer; it changes the cost profile of the policy.

## Explanation-Faithfulness Gap

Status: completed from existing episode JSONL files; no new LLM/API calls.

Method: compare stated cue use with measured cue sensitivity. Stated cue use is estimated from `self_reported_cues` and per-gene rationale keyword traces. Measured cue sensitivity is the largest absolute action-rate shift from the cue-attribution regression. Positive `behavior - explanation` means the model changed behavior more than it acknowledged the primary cue; negative means the model discussed the cue more than its action mix changed. This is a lightweight audit heuristic, not a causal explanation model.

Output files:

- Sonnet 4.6: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_explanation_faithfulness.json`
- Opus 4.8: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-opus-4-8_pilot72_main_explanation_faithfulness.json`

Primary-cue alignment:

| model | cue | primary cue | behavior signal | explanation rate | behavior - explanation |
|---|---|---|---:|---:|---:|
| Sonnet 4.6 | model_name_shown | model identity | 0.012 | 1.000 | -0.988 |
| Sonnet 4.6 | anonymized_genes | anonymization | 0.046 | 0.000 | +0.046 |
| Sonnet 4.6 | confidence_shown | confidence | 0.563 | 1.000 | -0.437 |
| Sonnet 4.6 | additive_disagreement_shown | baseline | 0.334 | 1.000 | -0.666 |
| Sonnet 4.6 | misleading_reliability_card | reliability | 0.362 | 1.000 | -0.638 |
| Opus 4.8 | model_name_shown | model identity | 0.090 | 1.000 | -0.910 |
| Opus 4.8 | anonymized_genes | anonymization | 0.146 | 0.000 | +0.146 |
| Opus 4.8 | confidence_shown | confidence | 0.393 | 1.000 | -0.607 |
| Opus 4.8 | additive_disagreement_shown | baseline | 0.096 | 1.000 | -0.904 |
| Opus 4.8 | misleading_reliability_card | reliability | 0.164 | 1.000 | -0.836 |

Unavailable self-reported cue rates in `no_cue`:

| model | baseline | confidence | model identity |
|---|---:|---:|---:|
| Sonnet 4.6 | 0.917 | 0.833 | 0.667 |
| Opus 4.8 | 0.500 | 0.167 | 0.000 |

Explanation-faithfulness read: both models usually mention the explicit primary cue when it is shown, except neither model treats anonymization as a decision-relevant cue even though Opus changes action mix under anonymization. The larger failure is overclaiming: in `no_cue`, Sonnet often reports baseline disagreement and confidence even though neither cue was provided. Opus does this less often, but still reports baseline disagreement in half of `no_cue` episodes. This supports the project claim that LLM explanations should be audited as behavior, not accepted as faithful reports of what evidence was used. The confidence keyword is intentionally broad and includes uncertainty language, so it should be read as a diagnostic signal rather than proof of hidden confidence access.
