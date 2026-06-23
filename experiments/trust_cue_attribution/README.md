# Trust-Cue Attribution For LLM x SFM Systems

This experiment instruments the *trust decision* a general LLM makes when it reads a specialist biological model's output.

The goal is not to benchmark one biological model in isolation. The goal is to measure which evidence cues make an LLM choose:

- `trust_sfm`
- `verify_assay`
- `default_baseline`
- `defer`

> **Data availability.** The full test suite (`pytest`, 163 passing) runs with no
> external data, and the Phase 2 protein benchmark is bundled (`../../dist/hf_dataset/`).
> The Phase 0/1 perturbation inputs referenced below come from the author's other
> repositories and are **not redistributed here**; the tracked `results/` JSON
> artifacts summarize and hash those runs.

## Phase 0

Use the local GEARS / Verify-or-Trust perturbation substrate as a dry run.

Primary local inputs:

- `<DATA_ROOT>/Verify-or-Trust/data/substrates/gears_norman.csv`
- `<DATA_ROOT>/Causal_Grounding_Eval/results/gears_norman/labeled_marginal.csv`
- `<DATA_ROOT>/Causal_Grounding_Eval/results/gears_norman/gears_vs_real_all.csv`

The implementation standardizes these into an extended panel format:

```text
data edge -> panel -> cue evidence packet -> LLM action -> reward
```

See [`BENCHMARK_CARD.md`](BENCHMARK_CARD.md) for the Phase 0 task definition,
intended use, metrics, limitations, and claim boundaries.

Phase 0A and Phase 0B frozen compact artifacts live in:

- `experiments/trust_cue_attribution/results/phase0a_freeze/manifest.json`
- `experiments/trust_cue_attribution/results/phase0a_freeze/summary.json`
- `experiments/trust_cue_attribution/results/phase0b_freeze/manifest.json`
- `experiments/trust_cue_attribution/results/phase0b_freeze/summary.json`
- `experiments/trust_cue_attribution/results/phase0b_robustness/summary.json`
- `experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_contract.json`

These tracked files summarize and hash the larger ignored HPC outputs without
committing raw request, episode, or trajectory JSONL files.

## Cue Conditions

The first cue matrix is fixed to:

- `no_cue`
- `model_name_shown`
- `anonymized_genes`
- `confidence_shown`
- `additive_disagreement_shown`
- `misleading_reliability_card`
- `raw_assay_stats_shown`

`raw_assay_stats_shown` is a leakage-aware positive-control condition. It shows
measured DE statistics such as `raw_log2FC`, `raw_se`, `raw_q`, and sample counts.
Do not mix it into the main SFM trust-cue interpretation.

## Local Smoke Commands

Local memory is limited. These commands are documented for reproducibility, but real build/test/compute should run on Cayuga or Expanse. See [`HPC_RUNBOOK.md`](HPC_RUNBOOK.md).

Build panels from the local Verify-or-Trust substrate:

```bash
python3 experiments/trust_cue_attribution/run.py build-panels \
  --substrate <DATA_ROOT>/Verify-or-Trust/data/substrates/gears_norman.csv \
  --marginal <DATA_ROOT>/Causal_Grounding_Eval/results/gears_norman/labeled_marginal.csv \
  --out /tmp/trust_cue_panels.jsonl
```

Build the combo/additive subset for the additive-disagreement signal check:

```bash
python3 experiments/trust_cue_attribution/run.py build-panels \
  --substrate <DATA_ROOT>/Verify-or-Trust/data/substrates/gears_norman.csv \
  --marginal <DATA_ROOT>/Causal_Grounding_Eval/results/gears_norman/labeled_marginal.csv \
  --require-additive \
  --out /tmp/trust_cue_panels_additive.jsonl
```

Generate cue packets:

```bash
python3 experiments/trust_cue_attribution/run.py cue-packets \
  --panels /tmp/trust_cue_panels.jsonl \
  --out /tmp/trust_cue_packets.jsonl
```

Run deterministic baseline policies:

```bash
python3 experiments/trust_cue_attribution/run.py baselines \
  --panels /tmp/trust_cue_panels.jsonl
```

Materialize request JSONL without calling an API:

```bash
python3 experiments/trust_cue_attribution/run.py make-requests \
  --packets /tmp/trust_cue_packets.jsonl \
  --out /tmp/trust_cue_requests.jsonl
```

Run the request JSONL through the API-free mock provider. This is a wiring check, not a scientific result:

```bash
python3 experiments/trust_cue_attribution/run.py run-llm-episodes \
  --requests /tmp/trust_cue_requests.jsonl \
  --provider mock_defer \
  --model mock-defer \
  --limit 12 \
  --out /tmp/trust_cue_mock_defer_episodes.jsonl
```

Run real LLM episodes through Claude when `ANTHROPIC_API_KEY` is available on the HPC node:

```bash
python3 experiments/trust_cue_attribution/run.py run-llm-episodes \
  --requests /tmp/trust_cue_requests.jsonl \
  --provider anthropic_messages \
  --model YOUR_CLAUDE_MODEL \
  --continue-on-error \
  --resume \
  --delay 0.2 \
  --out /tmp/trust_cue_llm_episodes.jsonl
```

OpenAI is still available by using `--provider openai_responses` with `OPENAI_API_KEY`.

Score completed LLM episodes:

```bash
python3 experiments/trust_cue_attribution/run.py score-episodes \
  --panels /tmp/trust_cue_panels.jsonl \
  --packets /tmp/trust_cue_packets.jsonl \
  --episodes /tmp/trust_cue_episodes.jsonl \
  --out /tmp/trust_cue_episode_scores.json
```

Compare each cue to `no_cue` for the same panel/gene:

```bash
python3 experiments/trust_cue_attribution/run.py paired-cue-effects \
  --panels /tmp/trust_cue_panels.jsonl \
  --packets /tmp/trust_cue_packets.jsonl \
  --episodes /tmp/trust_cue_episodes.jsonl \
  --out /tmp/trust_cue_paired_effects.json
```

Estimate categorical cue-attribution coefficients for action choice:

```bash
python3 experiments/trust_cue_attribution/run.py cue-attribution \
  --panels /tmp/trust_cue_panels.jsonl \
  --packets /tmp/trust_cue_packets.jsonl \
  --episodes /tmp/trust_cue_episodes.jsonl \
  --out /tmp/trust_cue_attribution.json
```

Compare stated cue use against measured cue sensitivity:

```bash
python3 experiments/trust_cue_attribution/run.py explanation-faithfulness \
  --panels /tmp/trust_cue_panels.jsonl \
  --packets /tmp/trust_cue_packets.jsonl \
  --episodes /tmp/trust_cue_episodes.jsonl \
  --out /tmp/trust_cue_explanation_faithfulness.json
```

Validate the episode scorer without an API by materializing a deterministic policy:

```bash
python3 experiments/trust_cue_attribution/run.py simulate-episodes \
  --panels /tmp/trust_cue_panels.jsonl \
  --packets /tmp/trust_cue_packets.jsonl \
  --policy signal_gated_verify \
  --out /tmp/trust_cue_policy_episodes.jsonl

python3 experiments/trust_cue_attribution/run.py score-episodes \
  --panels /tmp/trust_cue_panels.jsonl \
  --packets /tmp/trust_cue_packets.jsonl \
  --episodes /tmp/trust_cue_policy_episodes.jsonl \
  --out /tmp/trust_cue_policy_scores.json
```

Export deterministic-policy decisions as environment trajectories:

```bash
python3 experiments/trust_cue_attribution/run.py simulate-trajectories \
  --panels /tmp/trust_cue_panels.jsonl \
  --packets /tmp/trust_cue_packets.jsonl \
  --policy signal_gated_verify \
  --lam 0.5 \
  --out /tmp/trust_cue_policy_trajectories.jsonl
```

Trajectory records wrap the same Phase 0 episode with `observation`,
`tool_calls`, `actions`, `score`, and reward fields. This is the thin
environment bridge for later SFT/RL-style datasets; it is not a new scientific
claim by itself.

Convert completed LLM episodes into environment trajectories:

```bash
python3 experiments/trust_cue_attribution/run.py episodes-to-trajectories \
  --panels /tmp/trust_cue_panels.jsonl \
  --packets /tmp/trust_cue_packets.jsonl \
  --episodes /tmp/trust_cue_llm_episodes.jsonl \
  --lam 0.5 \
  --out /tmp/trust_cue_llm_trajectories.jsonl
```

By default this preserves provider/model metadata and self-reported cues, but
does not copy `raw_output` into the trajectory dataset. Add
`--include-raw-output` only when debugging provider responses.

Summarize a trajectory dataset:

```bash
python3 experiments/trust_cue_attribution/run.py summarize-trajectories \
  --trajectories /tmp/trust_cue_llm_trajectories.jsonl \
  --out /tmp/trust_cue_llm_trajectory_summary.json
```

Export model-visible packet features from trajectories:

```bash
python3 experiments/trust_cue_attribution/run.py trajectory-features \
  --trajectories /tmp/trust_cue_sonnet_trajectories.jsonl /tmp/trust_cue_opus_trajectories.jsonl \
  --out /tmp/trust_cue_feature_rows.jsonl \
  --summary-out /tmp/trust_cue_feature_summary.json
```

Create reward-derived preference pairs from trajectory datasets:

```bash
python3 experiments/trust_cue_attribution/run.py trajectory-preferences \
  --trajectories /tmp/trust_cue_sonnet_trajectories.jsonl /tmp/trust_cue_opus_trajectories.jsonl \
  --out /tmp/trust_cue_preference_pairs.jsonl \
  --summary-out /tmp/trust_cue_preference_summary.json
```

Preference pairs compare trajectories for the same `packet_id`. The higher
reward trajectory becomes `chosen`, and the lower reward trajectory becomes
`rejected`. These labels are derived from hidden scoring after the fact; the
model-visible input remains the shared `observation`.

Evaluate simple model-router baselines over matched trajectories:

```bash
python3 experiments/trust_cue_attribution/run.py evaluate-router \
  --trajectories /tmp/trust_cue_sonnet_trajectories.jsonl /tmp/trust_cue_opus_trajectories.jsonl \
  --out /tmp/trust_cue_router_eval.json
```

The first router is deliberately conservative: it learns mean reward by
`cue_condition` while leaving out one `panel_id` at a time. It is a sanity check,
not a final learned router.

Use `--feature-field feature_signature` to evaluate a slightly richer router
over binned, model-visible packet features such as SFM effect-rate, effect-size
distribution, displayed confidence, displayed baseline disagreement, displayed
reliability cards, and anonymization.

Freeze the Phase 0A benchmark state into compact tracked artifacts:

```bash
python3 experiments/trust_cue_attribution/run.py freeze-phase0a \
  --input-dir experiments/trust_cue_attribution/hpc_outputs/phase0_smoke \
  --out-dir experiments/trust_cue_attribution/results/phase0a_freeze
```

This command performs count, cue, panel-balance, and sanity checks. It also
recomputes scorer-dependent LLM pilot summaries from episode JSONL using the
current micro gene-weighted scorer.

Freeze the Phase 0B full non-leakage Sonnet state:

```bash
python3 experiments/trust_cue_attribution/run.py freeze-phase0b \
  --input-dir experiments/trust_cue_attribution/hpc_outputs/phase0_smoke \
  --out-dir experiments/trust_cue_attribution/results/phase0b_freeze
```

This command verifies the 642-request full non-leakage run, balanced cue
conditions, output integrity, and Phase 0B sanity checks.

Build the Phase 0B panel-cluster bootstrap robustness summary:

```bash
python3 experiments/trust_cue_attribution/run.py phase0b-robustness \
  --input-dir experiments/trust_cue_attribution/hpc_outputs/phase0_smoke \
  --out experiments/trust_cue_attribution/results/phase0b_robustness/summary.json \
  --n-boot 1000 \
  --seed 13 \
  --lam 0.5
```

This command computes uncertainty intervals for paired cue effects,
Sonnet-vs-baseline net/gene deltas, and selected explanation-faithfulness rates.

Write the Phase 1 scFoundation adapter preflight contract:

```bash
python3 experiments/trust_cue_attribution/run.py phase1-preflight \
  --out experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_contract.json
```

This is not a true-SFM result. It defines the input/output contract and claim
boundary that a scFoundation adapter must satisfy before Phase 1 compute starts
on Cayuga or Expanse.

Check Phase 1 scFoundation feasibility without loading model weights:

```bash
python3 experiments/trust_cue_attribution/run.py phase1-feasibility \
  --scfoundation-dir "$SCFOUNDATION_DIR" \
  --checkpoint "$SCFOUNDATION_CHECKPOINT" \
  --gene-index "$SCFOUNDATION_GENE_INDEX" \
  --input-data "$PHASE1_INPUT_DATA" \
  --output-dir "$PHASE1_OUTPUT_DIR" \
  --out experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_feasibility.json
```

The expected local status before staging real artifacts is
`blocked_missing_required_artifacts`. The current Cayuga feasibility status is
`ready_for_hpc_smoke`, which means required files are present but scFoundation
inference has not been run yet.

Check Phase 1 input compatibility before attempting scFoundation inference:

```bash
python3 experiments/trust_cue_attribution/run.py phase1-input-inventory \
  --gene-index "$SCFOUNDATION_GENE_INDEX" \
  --input-data "$PHASE1_INPUT_DATA" \
  --out experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_input_inventory.json
```

The current Cayuga inventory status is `ready_for_adapter_smoke`: 794 of 834
input genes overlap the scFoundation vocabulary. This is enough for wiring, but
the input appears to be an HVG/subset matrix and should not support scientific
claims without a fuller gene-space input.

Check the scFoundation inference environment:

```bash
python3 experiments/trust_cue_attribution/run.py phase1-inference-env \
  --scfoundation-dir "$SCFOUNDATION_DIR" \
  --checkpoint "$SCFOUNDATION_CHECKPOINT" \
  --out experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_inference_env_login.json
```

The current login-node import gate is `ready_for_gpu_env_probe` using the
isolated `hpc_outputs/envs/scfoundation-smoke-py39` environment. This confirms
dependency and scFoundation `load.py` import readiness, but not CUDA visibility
or checkpoint loading.

The current Cayuga GPU environment gate is `ready_for_inference_smoke`. It
confirms A100 visibility, torch CUDA visibility, and scFoundation `load.py`
import readiness. It still does not load the checkpoint or generate embeddings.

The current tiny scFoundation smoke status is
`ready_for_internal_signal_summary_adapter`. Cayuga job `3044223` generated a
finite `[3, 3072]` cell embedding summary from a three-cell subset through the
official scFoundation embedding script. Treat this as adapter wiring evidence,
not as a scientific or LLM-trust result.

Build a small Phase 1A internal-signal packet pilot from the frozen Phase 0
panels, the compact scFoundation smoke report, and the panel-specific Norman
2019 signal report:

```bash
python3 experiments/trust_cue_attribution/run.py phase1a-signal-packets \
  --panels experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --scfoundation-smoke-report experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_smoke_report.json \
  --panel-signal-report experiments/trust_cue_attribution/results/phase1a_panel_signals/panel_signal_report.json \
  --out experiments/trust_cue_attribution/hpc_outputs/phase1a_signal_pilot/phase1a_signal_packets.jsonl \
  --manifest-out experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json \
  --n-panels 12 \
  --seed 23
```

This creates three conditions per selected panel: no internal signal, matched
scFoundation panel summary, and deterministic shuffled/control summary. It does
not call an LLM.

For the recommended panel-specific route, use the public Norman 2019 h5ad. The
local FRAM2 smoke h5ad is wiring-only, unpublished, and not benchmark-facing;
its perturbation labels do not overlap the Norman Phase 0 panels. The Norman
2019 h5ad on Cayuga overlaps the Phase 0 panels through `perturbation_name`.

```bash
SCFOUNDATION_DIR=/scratch/USER/huggingface/benchmark/scFoundation \
PHASE1A_INPUT_DATA=/scratch/USER/nomos/data/norman_2019.h5ad \
PYTHON=/scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution/hpc_outputs/envs/scfoundation-smoke-py39/bin/python \
sbatch --partition=scu-gpu --gres=gpu:1 \
  experiments/trust_cue_attribution/hpc/run_phase1a_panel_signals.sbatch
```

This samples selected-panel cells plus controls, runs official scFoundation
embedding, and writes a compact panel-specific signal report. Current completed
anchor: Cayuga job `3044228`, source shape `[111255, 19018]`, subset shape
`[256, 19018]`, embedding shape `[256, 3072]`, compact report
`experiments/trust_cue_attribution/results/phase1a_panel_signals/panel_signal_report.json`.
Large embeddings remain ignored under `hpc_outputs`.

After a 36-request Phase 1A Sonnet pilot is scored, review real-vs-placebo
specificity before scaling:

```bash
python3 experiments/trust_cue_attribution/run.py phase1a-review \
  --panels experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --packets experiments/trust_cue_attribution/hpc_outputs/phase1a_signal_pilot/phase1a_signal_packets.jsonl \
  --episodes experiments/trust_cue_attribution/hpc_outputs/phase1a_signal_pilot/llm_claude-sonnet-4-6_phase1a_signal_pilot_episodes.jsonl \
  --panel-signal-report experiments/trust_cue_attribution/results/phase1a_panel_signals/panel_signal_report.json \
  --out experiments/trust_cue_attribution/results/phase1a_signal_pilot/review.json
```

Current review decision: `do_not_scale_yet`. The real signal and shuffled
placebo produce similar small gains, so this is cue-sensitivity evidence rather
than faithful scFoundation-internal interpretation evidence.

Check whether the coarse panel-level scFoundation signal itself aligns with
GEARS wrongness before spending on a larger Phase 1A matrix:

```bash
python3 experiments/trust_cue_attribution/run.py phase1a-signal-validity \
  --manifest experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json \
  --panel-signal-report experiments/trust_cue_attribution/results/phase1a_panel_signals/panel_signal_report.json \
  --out experiments/trust_cue_attribution/results/phase1a_signal_pilot/signal_validity.json
```

Current signal-validity decision: `redesign_before_scaling`. In the 12 selected
pilot panels, the strongest primary panel-distance signal versus GEARS
`wrong_rate` is `std_cell_distance_to_control` with Pearson `-0.505`, so the
current coarse card should not be scaled as a naive high-risk cue. The next cue
should be gene-level or task-aligned while keeping the shuffled-signal placebo
control.

Check whether the panel-level signal is granular enough for edge-level
verify/trust decisions:

```bash
python3 experiments/trust_cue_attribution/run.py phase1a-signal-granularity \
  --panels experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --manifest experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json \
  --panel-signal-report experiments/trust_cue_attribution/results/phase1a_panel_signals/panel_signal_report.json \
  --out experiments/trust_cue_attribution/results/phase1a_signal_pilot/signal_granularity.json
```

Current granularity decision: `edge_level_signal_required`. All 12 selected
panels mix correct and wrong GEARS genes; across 315 edge rows, the best
primary panel-level scFoundation AUROC for edge wrongness is `0.467`, while
edge-level baseline call disagreement reaches `0.649`. This supports designing
a readout-gene-specific or task-aligned scFoundation cue next.

Create the Phase 1B edge-level signal design gate:

```bash
python3 experiments/trust_cue_attribution/run.py phase1b-edge-signal-design \
  --panels experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --manifest experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json \
  --out experiments/trust_cue_attribution/results/phase1b_edge_signal_design/design.json
```

Current Phase 1B design recommendation: `scfoundation_neighbor_edge_support`.
Among the 315 selected edges, 302 have at least 10 other panels sharing the
same readout gene, so a readout-gene-specific neighbor cue is feasible for an
HPC prototype. This is still a design gate, not a scored LLM result.

Generate the Phase 1B scFoundation embedding pool on Cayuga or Expanse, not
locally:

```bash
python3 experiments/trust_cue_attribution/run.py phase1b-embedding-pool \
  --scfoundation-dir "$SCFOUNDATION_DIR" \
  --input-data /scratch/USER/nomos/data/norman_2019.h5ad \
  --panels experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --pool-out experiments/trust_cue_attribution/hpc_outputs/phase1b_edge_neighbor/embedding_pool.json \
  --report-out experiments/trust_cue_attribution/hpc_outputs/phase1b_edge_neighbor/embedding_pool_report.json
```

Then compute the pre-LLM edge-neighbor diagnostic:

```bash
python3 experiments/trust_cue_attribution/run.py phase1b-neighbor-signals \
  --panels experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --manifest experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json \
  --embedding-pool experiments/trust_cue_attribution/hpc_outputs/phase1b_edge_neighbor/embedding_pool.json \
  --out experiments/trust_cue_attribution/results/phase1b_edge_neighbor/neighbor_signal_report.json
```

This diagnostic checks leakage, within-panel signal variation, edge-level AUROC
against hidden GEARS wrongness, random same-gene controls, and shuffled
readout-gene controls. It does not call an LLM and does not support a
scFoundation-interpretation claim by itself.

If the diagnostic decision is `eligible_for_small_llm_pilot`, build the
Phase 1B pilot packets:

```bash
python3 experiments/trust_cue_attribution/run.py phase1b-signal-packets \
  --panels experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --neighbor-report experiments/trust_cue_attribution/results/phase1b_edge_neighbor/neighbor_signal_report.json \
  --out experiments/trust_cue_attribution/hpc_outputs/phase1b_signal_pilot/phase1b_signal_packets.jsonl \
  --manifest-out experiments/trust_cue_attribution/results/phase1b_signal_pilot/manifest.json
```

The current Phase 1B pilot input is `signal_packet_pilot_ready`: 12 panels,
48 packets, four balanced conditions, and no prompt forbidden-key hits in the
generated request JSONL. The four conditions are no signal, real scFoundation
edge-neighbor signal, random same-readout-gene control, and shuffled
readout-gene control.

Run the bounded Phase 1B Sonnet pilot on HPC only after the packet manifest is
ready:

```bash
sbatch experiments/trust_cue_attribution/hpc/run_phase1b_llm_pilot.sbatch
```

After the pilot completes, write the post-pilot review gate:

```bash
python3 experiments/trust_cue_attribution/run.py phase1b-review \
  --panels experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --packets experiments/trust_cue_attribution/hpc_outputs/phase1b_signal_pilot/phase1b_signal_packets.jsonl \
  --episodes experiments/trust_cue_attribution/hpc_outputs/phase1b_signal_pilot/llm_claude-sonnet-4-6_phase1b_signal_pilot_episodes.jsonl \
  --neighbor-report experiments/trust_cue_attribution/results/phase1b_edge_neighbor/neighbor_signal_report.json \
  --out experiments/trust_cue_attribution/results/phase1b_signal_pilot/review.json
```

Current Phase 1B review decision: `do_not_scale_larger_llm_matrix`. The real
edge-neighbor cue changed behavior but reduced lambda `0.5` net reward versus
no-signal, and controls also shifted behavior. Redesign the deterministic
signal packet before any larger Phase 1B LLM matrix.

Build the Phase 1C calibrated reliability-interface offline gate:

```bash
python3 experiments/trust_cue_attribution/run.py phase1c-offline-gate \
  --panels experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --neighbor-report experiments/trust_cue_attribution/results/phase1b_edge_neighbor/neighbor_signal_report.json \
  --phase1b-summary experiments/trust_cue_attribution/results/phase1b_signal_pilot/summary.json \
  --design-out experiments/trust_cue_attribution/results/phase1c_reliability_interface/design.json \
  --out experiments/trust_cue_attribution/results/phase1c_reliability_interface/offline_gate.json
```

Current Phase 1C offline decision:
`eligible_for_small_phase1c_interface_pilot`. The combined reliability
interface reaches `0.747619` net/gene at lambda `0.5`, compared with no-signal
LLM `0.658730`, raw edge-neighbor LLM `0.620635`, and best control `0.744444`.
The control margin is only `0.003175`, so this permits only a small interface
pilot, not a large matrix.

Build the small Phase 1C reliability-interface request set:

```bash
python3 experiments/trust_cue_attribution/run.py phase1c-interface-requests
```

Current Phase 1C request-preparation manifest:

- `experiments/trust_cue_attribution/results/phase1c_reliability_interface/interface_request_manifest.json`
- status: `interface_request_pilot_ready`
- panels: `12`
- packets / requests: `48`
- cue conditions: `no_internal_signal`, `edge_neighbor_signal_shown`,
  `calibrated_reliability_interface_shown`,
  `inverted_reliability_interface_control`
- leakage check: passed

This is request preparation only. It made no Claude call and does not establish
that Claude will follow the reliability interface.

Build a stratified non-leakage pilot request set:

```bash
python3 experiments/trust_cue_attribution/run.py select-pilot-requests \
  --panels /tmp/trust_cue_panels.jsonl \
  --requests /tmp/trust_cue_requests.jsonl \
  --n-panels 12 \
  --out /tmp/trust_cue_pilot72_requests.jsonl \
  --manifest /tmp/trust_cue_pilot72_manifest.json
```

This default pilot uses the six main non-leakage cues and excludes
`raw_assay_stats_shown`.

Run tests:

```bash
python3 -m unittest discover -s experiments/trust_cue_attribution/tests
```

## Expansion Route

- Phase 0: GEARS / Verify-or-Trust dry run.
- Phase 1: scFoundation true-SFM extension.
- Phase 2: Evo2 internal-feature cue demo.
- Phase 3: AlphaGenome black-box flagship stress test.

## Compute Policy

Use Cayuga or Expanse for build, test, panel generation, baseline sweeps, LLM episodes, and SFM inference. Local runs should be treated as lightweight inspection only.
