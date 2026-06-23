# HPC Runbook: Cayuga / Expanse

Local compute is limited. Treat local runs as editing and lightweight inspection only.

For build, test, panel generation, baseline sweeps, LLM episode generation, scFoundation inference, Evo2 inference, or any larger analysis, use Cayuga or Expanse.

## Policy

- Local: edit files, inspect small text files, run trivial syntax checks only when unavoidable.
- Cayuga: default target for Phase 0 and Phase 1 compute/build/test.
- Expanse: fallback or scale-out target for larger model inference or batch episode generation.
- Results should be written on HPC first, then synced back into this workspace only as compact summaries or selected artifacts.

## Preferred Cayuga Layout

Recommended remote root:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
```

If that scratch path is not available, use:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
```

Expected project layout on HPC:

```text
$REMOTE/
  experiments/trust_cue_attribution/
  data/external/Verify-or-Trust/gears_norman.csv
  data/external/Causal_Grounding_Eval/labeled_marginal.csv
```

## Stage Project To Cayuga

From the local project root:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
ssh <HPC_LOGIN> "mkdir -p $REMOTE/data/external/Verify-or-Trust $REMOTE/data/external/Causal_Grounding_Eval"
rsync -av --exclude '__pycache__' --exclude '.pytest_cache' --exclude 'hpc_outputs' ./ <HPC_LOGIN>:$REMOTE/
rsync -av <DATA_ROOT>/Verify-or-Trust/data/substrates/gears_norman.csv \
  <HPC_LOGIN>:$REMOTE/data/external/Verify-or-Trust/gears_norman.csv
rsync -av <DATA_ROOT>/Causal_Grounding_Eval/results/gears_norman/labeled_marginal.csv \
  <HPC_LOGIN>:$REMOTE/data/external/Causal_Grounding_Eval/labeled_marginal.csv
```

## Submit Phase 0 Smoke On Cayuga

Use Cayuga's newer Slurm binaries when available:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
SLURM=/opt/ohpc/pub/software/slurm/24.05.2/bin
ssh <HPC_LOGIN> "cd $REMOTE && $SLURM/sbatch experiments/trust_cue_attribution/hpc/run_phase0_smoke.sbatch"
```

Check status:

```bash
ssh <HPC_LOGIN> "$SLURM/squeue -u USER"
```

Fetch compact results:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
rsync -av <HPC_LOGIN>:$REMOTE/experiments/trust_cue_attribution/hpc_outputs/ \
  ./experiments/trust_cue_attribution/hpc_outputs/
```

After syncing the Phase 0A pilot artifacts locally, freeze compact tracked
summaries from the ignored HPC outputs:

```bash
python3 experiments/trust_cue_attribution/run.py freeze-phase0a \
  --input-dir experiments/trust_cue_attribution/hpc_outputs/phase0_smoke \
  --out-dir experiments/trust_cue_attribution/results/phase0a_freeze
```

This writes `manifest.json` and `summary.json`, verifies canonical Phase 0A
counts, excludes `raw_assay_stats_shown` from the main pilot, checks 4/4/4
pilot panel balance, and reruns scorer-dependent summaries with the current
micro gene-weighted scorer.

After syncing the completed Phase 0B full non-leakage Sonnet outputs locally,
freeze the compact tracked Phase 0B state:

```bash
python3 experiments/trust_cue_attribution/run.py freeze-phase0b \
  --input-dir experiments/trust_cue_attribution/hpc_outputs/phase0_smoke \
  --out-dir experiments/trust_cue_attribution/results/phase0b_freeze
```

This verifies 642 non-leakage requests, 642 Sonnet episodes, 107 panels, six
balanced non-leakage cue conditions, no parse/provider errors, and Phase 0B
sanity checks. It records source hashes while keeping large JSONL artifacts
ignored.

## Expanse Pattern

Use the same layout and script with host/path overrides:

```bash
REMOTE_HOST=expanse
REMOTE=\$SCRATCH/LLM_SFM_interpretability
```

Then stage the project and submit the same `hpc/run_phase0_smoke.sbatch` script from the remote project root. If Expanse requires account/partition flags, pass them at submit time:

```bash
sbatch --account YOUR_ACCOUNT --partition YOUR_PARTITION experiments/trust_cue_attribution/hpc/run_phase0_smoke.sbatch
```

## What The Smoke Job Verifies

The Phase 0 smoke job:

1. Runs unit tests on HPC.
2. Builds full GEARS/Norman panels.
3. Builds combo-only observed-additive panels.
4. Generates cue packets.
5. Materializes request JSONL without calling any API.
6. Materializes synthetic policy episodes and scores them through the episode scorer.
7. Runs deterministic baselines on full and additive subsets.
8. Writes outputs under `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/`.

This is the minimum HPC gate before larger LLM episode runs or scFoundation/Evo2 work.

## Phase 1 scFoundation Probe

The Phase 1 probe checks readiness for scFoundation adapter work without loading
model weights or running inference. It should be run on Cayuga or Expanse after
the scFoundation repository, checkpoint, gene index, and a small Phase 1 input
dataset have been staged.

Required or recommended environment variables:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
SCFOUNDATION_DIR=/scratch/USER/external/scFoundation
SCFOUNDATION_CHECKPOINT=/scratch/USER/models/scFoundation/checkpoint.pt
SCFOUNDATION_GENE_INDEX=$SCFOUNDATION_DIR/OS_scRNA_gene_index.19264.tsv
PHASE1_INPUT_DATA=/scratch/USER/data/phase1_scfoundation/input.h5ad
PHASE1_OUTPUT_DIR=$REMOTE/experiments/trust_cue_attribution/hpc_outputs/phase1_preflight/generated
```

Submit:

```bash
ssh <HPC_LOGIN> "cd $REMOTE && SCFOUNDATION_DIR=$SCFOUNDATION_DIR \
  SCFOUNDATION_CHECKPOINT=$SCFOUNDATION_CHECKPOINT \
  SCFOUNDATION_GENE_INDEX=$SCFOUNDATION_GENE_INDEX \
  PHASE1_INPUT_DATA=$PHASE1_INPUT_DATA \
  PHASE1_OUTPUT_DIR=$PHASE1_OUTPUT_DIR \
  $SLURM/sbatch experiments/trust_cue_attribution/hpc/run_phase1_scfoundation_probe.sbatch"
```

Expected output:

```text
experiments/trust_cue_attribution/hpc_outputs/phase1_preflight/
  scfoundation_contract.json
  scfoundation_feasibility.json
```

The probe may finish with `status=blocked_missing_required_artifacts`; that is
a valid result if files are not staged yet. It becomes `ready_for_hpc_smoke`
only when required artifacts are present and the adapter contract checks pass.

## Phase 1 scFoundation Input Inventory

After the feasibility probe reaches `ready_for_hpc_smoke`, run a lightweight
input compatibility inventory before attempting true scFoundation inference.
This checks whether the staged h5ad genes overlap the scFoundation vocabulary.

Historical note: the FRAM2 path below was used only as a local wiring smoke
input. It is local/unpublished and must not be used for benchmark-facing
Phase 1 claims. Use the public Norman 2019 h5ad for current Phase 1A
panel-specific signal work.

The default script uses an existing Cayuga conda environment with `anndata`,
`scanpy`, `h5py`, `torch`, and `einops`:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
SLURM=/opt/ohpc/pub/software/slurm/24.05.2/bin
SCFOUNDATION_GENE_INDEX=/scratch/USER/huggingface/benchmark/scFoundation/OS_scRNA_gene_index.19264.tsv
PHASE1_INPUT_DATA=/scratch/USER/Perturb_seq/virtual_cell/2026_03_18_cfgA/data/fram2_val.h5ad
ssh <HPC_LOGIN> "cd $REMOTE && SCFOUNDATION_GENE_INDEX=$SCFOUNDATION_GENE_INDEX \
  PHASE1_INPUT_DATA=$PHASE1_INPUT_DATA \
  $SLURM/sbatch experiments/trust_cue_attribution/hpc/run_phase1_scfoundation_inventory.sbatch"
```

Expected output:

```text
experiments/trust_cue_attribution/hpc_outputs/phase1_preflight/
  scfoundation_input_inventory.json
```

The target status is `ready_for_adapter_smoke`. This is still not an inference
result; it only says the h5ad can be read and has enough vocabulary overlap to
justify a minimal adapter smoke job.

## Phase 1 scFoundation Inference Environment Probe

Before running true scFoundation inference, probe the selected Python
environment inside a GPU allocation. This checks imports, CUDA visibility,
scFoundation model files, and whether `model/load.py` imports cleanly. It does
not load checkpoints or produce embeddings.

Build an isolated smoke-test environment if no existing environment imports the
required stack cleanly:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
ssh <HPC_LOGIN> "cd $REMOTE && bash experiments/trust_cue_attribution/hpc/build_phase1_scfoundation_env.sh"
```

Then pass the created Python to the env probe:

```bash
PYTHON=$REMOTE/experiments/trust_cue_attribution/hpc_outputs/envs/scfoundation-smoke-py39/bin/python
```

Cayuga GPU submission:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
SLURM=/opt/ohpc/pub/software/slurm/24.05.2/bin
SCFOUNDATION_DIR=/scratch/USER/huggingface/benchmark/scFoundation
SCFOUNDATION_CHECKPOINT=$SCFOUNDATION_DIR/model/models/models.ckpt
ssh <HPC_LOGIN> "cd $REMOTE && SCFOUNDATION_DIR=$SCFOUNDATION_DIR \
  SCFOUNDATION_CHECKPOINT=$SCFOUNDATION_CHECKPOINT \
  PYTHON=$PYTHON \
  $SLURM/sbatch --partition=scu-gpu --gres=gpu:1 \
  experiments/trust_cue_attribution/hpc/run_phase1_scfoundation_env_probe.sbatch"
```

Expanse pattern after staging repo/model/data there:

```bash
REMOTE=$SCRATCH/LLM_SFM_interpretability
ssh <HPC_LOGIN> "cd $REMOTE && SCFOUNDATION_DIR=$SCFOUNDATION_DIR \
  SCFOUNDATION_CHECKPOINT=$SCFOUNDATION_CHECKPOINT \
  sbatch --partition=gpu-shared --gpus=1 \
  experiments/trust_cue_attribution/hpc/run_phase1_scfoundation_env_probe.sbatch"
```

Expected output:

```text
experiments/trust_cue_attribution/hpc_outputs/phase1_preflight/
  scfoundation_inference_env.json
```

Target status: `ready_for_inference_smoke`. Any blocked status should be treated
as an environment/setup task, not a biological result.

## Phase 1 Tiny scFoundation Smoke

After `phase1-inference-env` passes inside a GPU allocation, run the tiny
embedding smoke. This creates a small h5ad subset before calling the official
scFoundation `model/get_embedding.py`, so the 834-gene HVG input is not expanded
for all 19,464 cells.

This is a wiring smoke only. It proves that the official scFoundation embedding
path can run, not that FRAM2 should be used as benchmark data.

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
SLURM=/opt/ohpc/pub/software/slurm/24.05.2/bin
SCFOUNDATION_DIR=/scratch/USER/huggingface/benchmark/scFoundation
PHASE1_INPUT_DATA=/scratch/USER/Perturb_seq/virtual_cell/2026_03_18_cfgA/data/fram2_val.h5ad
PYTHON=$REMOTE/experiments/trust_cue_attribution/hpc_outputs/envs/scfoundation-smoke-py39/bin/python
ssh <HPC_LOGIN> "cd $REMOTE && SCFOUNDATION_DIR=$SCFOUNDATION_DIR \
  PHASE1_INPUT_DATA=$PHASE1_INPUT_DATA \
  PYTHON=$PYTHON \
  $SLURM/sbatch --partition=scu-gpu --gres=gpu:1 \
  experiments/trust_cue_attribution/hpc/run_phase1_scfoundation_smoke.sbatch"
```

Expected compact report:

```text
experiments/trust_cue_attribution/hpc_outputs/phase1_preflight/
  scfoundation_smoke_report.json
```

Target status: `ready_for_internal_signal_summary_adapter`. This still only
means checkpoint loading and tiny embedding generation worked; it does not
support scientific interpretation or LLM trust claims.

## Phase 1A Panel-Specific scFoundation Signals

The local FRAM2 h5ad was only a scFoundation wiring smoke input. It is
local/unpublished, has zero perturbation overlap with the Norman Phase 0
panels, and must not be used for benchmark-facing Phase 1 claims. For
panel-specific Phase 1A signals, use the public Norman 2019 h5ad on Cayuga:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
SLURM=/opt/ohpc/pub/software/slurm/24.05.2/bin
SCFOUNDATION_DIR=/scratch/USER/huggingface/benchmark/scFoundation
PHASE1A_INPUT_DATA=/scratch/USER/nomos/data/norman_2019.h5ad
PYTHON=$REMOTE/experiments/trust_cue_attribution/hpc_outputs/envs/scfoundation-smoke-py39/bin/python
ssh <HPC_LOGIN> "cd $REMOTE && SCFOUNDATION_DIR=$SCFOUNDATION_DIR \
  PHASE1A_INPUT_DATA=$PHASE1A_INPUT_DATA \
  PYTHON=$PYTHON \
  $SLURM/sbatch --partition=scu-gpu --gres=gpu:1 \
  experiments/trust_cue_attribution/hpc/run_phase1a_panel_signals.sbatch"
```

Default sampling is 16 cells per selected panel plus 64 controls. The target
status is `ready_for_phase1a_panel_specific_signal_packets`. This creates a
compact JSON report only; large h5ad/npy outputs remain under ignored
`hpc_outputs`.

Current completed anchor:

- Cayuga job: `3044228`
- status: `COMPLETED`, exit code `0:0`
- source h5ad shape: `[111255, 19018]`
- scFoundation subset shape: `[256, 19018]`
- scFoundation embedding shape: `[256, 3072]`
- compact tracked report:
  `experiments/trust_cue_attribution/results/phase1a_panel_signals/panel_signal_report.json`

After syncing the compact report locally, regenerate the Phase 1A pilot packets
with the panel-specific report:

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

This remains a packet-generation checkpoint. Do not claim LLM use of
scFoundation internals until the regenerated request set is run and scored.

After the 36-request Phase 1A pilot is scored, run the compact signal-validity
gate before scaling:

```bash
python3 experiments/trust_cue_attribution/run.py phase1a-signal-validity \
  --manifest experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json \
  --panel-signal-report experiments/trust_cue_attribution/results/phase1a_panel_signals/panel_signal_report.json \
  --out experiments/trust_cue_attribution/results/phase1a_signal_pilot/signal_validity.json
```

Current decision: `redesign_before_scaling`. The current coarse panel-distance
card should not be scaled as a naive high-risk cue; build a gene-level or
task-aligned signal next and keep the shuffled-signal placebo control.

Then run the edge-level granularity gate:

```bash
python3 experiments/trust_cue_attribution/run.py phase1a-signal-granularity \
  --panels experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --manifest experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json \
  --panel-signal-report experiments/trust_cue_attribution/results/phase1a_panel_signals/panel_signal_report.json \
  --out experiments/trust_cue_attribution/results/phase1a_signal_pilot/signal_granularity.json
```

Current decision: `edge_level_signal_required`. Do not scale a panel-constant
scFoundation card into a larger LLM matrix until the next cue can vary at the
readout-gene or task-aligned evidence level.

Create the Phase 1B edge-signal design gate before writing a new HPC job:

```bash
python3 experiments/trust_cue_attribution/run.py phase1b-edge-signal-design \
  --panels experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --manifest experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json \
  --out experiments/trust_cue_attribution/results/phase1b_edge_signal_design/design.json
```

Current recommendation: `scfoundation_neighbor_edge_support`. This should be
implemented as a small HPC prototype that creates
`evidence_packet.genes[].edge_internal_signal_summary` without target-edge
truth, target raw assay stats, or reward fields.

## Phase 1B Edge-Neighbor scFoundation Prototype

Phase 1B uses the public Norman 2019 h5ad only. Do not use FRAM2/local
unpublished data for this benchmark-facing gate.

The Phase 1B prototype first creates a full 107-panel scFoundation embedding
pool, then computes readout-gene-specific neighbor evidence for the 12-panel
Phase 1A surface. It is a pre-LLM diagnostic: it checks leakage, within-panel
variation, edge-level AUROC versus hidden GEARS wrongness, random same-gene
controls, and shuffled readout-gene controls.

Submit on Cayuga:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
SLURM=/opt/ohpc/pub/software/slurm/24.05.2/bin
PYTHON=$REMOTE/experiments/trust_cue_attribution/hpc_outputs/envs/scfoundation-smoke-py39/bin/python
ssh <HPC_LOGIN> "cd $REMOTE && PYTHON=$PYTHON \
  $SLURM/sbatch --partition=scu-gpu --gres=gpu:1 \
  experiments/trust_cue_attribution/hpc/run_phase1b_embedding_pool.sbatch"
```

Expected outputs:

```text
experiments/trust_cue_attribution/hpc_outputs/phase1b_edge_neighbor/
  phase1b_embedding_pool_subset.h5ad
  phase1b_embedding_pool_01B-resolution_singlecell_cell_embedding_t4_resolution.npy
  embedding_pool.json
  embedding_pool_report.json

experiments/trust_cue_attribution/results/phase1b_edge_neighbor/
  neighbor_signal_report.json
```

Target status markers:

- `PHASE1B_EMBEDDING_POOL_STATUS=ready_for_phase1b_edge_neighbor_signals`
- `PHASE1B_NEIGHBOR_SIGNAL_STATUS=phase1b_edge_neighbor_signal_diagnostic_ready`
- `TRUST_CUE_PHASE1B_EDGE_NEIGHBOR_OK`

Only if the diagnostic decision is `eligible_for_small_llm_pilot` should the
next step create a small 4-condition Phase 1B LLM pilot. If the decision is
`diagnostic_only_do_not_run_llm_yet`, inspect whether the failure is leakage,
insufficient within-panel variation, weak real-signal AUROC, or failure to beat
the random/shuffled controls.

Current Phase 1B diagnostic status is `eligible_for_small_llm_pilot`. The
pilot input manifest is ready with 48 requests over four balanced conditions:

- `no_internal_signal`
- `scfoundation_edge_neighbor_signal_shown`
- `random_same_gene_neighbor_signal_shown`
- `shuffled_readout_gene_neighbor_signal_shown`

Submit the bounded Sonnet pilot on Cayuga CPU:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
SLURM=/opt/ohpc/pub/software/slurm/24.05.2/bin
ssh <HPC_LOGIN> "cd $REMOTE && $SLURM/sbatch \
  experiments/trust_cue_attribution/hpc/run_phase1b_llm_pilot.sbatch"
```

The script regenerates packets/requests from the tracked Phase 1B reports,
checks that exactly 48 requests are present, loads `~/.api_keys`, runs Sonnet,
then writes analysis, lambda-sweep scores, paired cue effects, cue attribution,
explanation-faithfulness, and trajectory summaries under
`hpc_outputs/phase1b_signal_pilot/`.

Target status marker:

- `TRUST_CUE_PHASE1B_LLM_PILOT_OK`

## Run Real LLM Episodes

The real LLM step consumes the request JSONL produced by `make-requests` and writes scorer-compatible episode JSONL.

Use `mock_defer` first to verify wiring without an API call:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
ssh <HPC_LOGIN> "cd $REMOTE && /usr/bin/python3.12 experiments/trust_cue_attribution/run.py run-llm-episodes \
  --requests experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/requests_full.jsonl \
  --provider mock_defer \
  --model mock-defer \
  --limit 12 \
  --out experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/mock_defer_episodes_12.jsonl"
```

For a real Claude run, make sure `ANTHROPIC_API_KEY` is available in the remote shell or sbatch environment:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
ssh <HPC_LOGIN> "cd $REMOTE && source ~/.api_keys && /usr/bin/python3.12 experiments/trust_cue_attribution/run.py run-llm-episodes \
  --requests experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/requests_full.jsonl \
  --provider anthropic_messages \
  --model YOUR_CLAUDE_MODEL \
  --continue-on-error \
  --resume \
  --delay 0.2 \
  --out experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_episodes.jsonl"
```

## Submit Phase 0B Full Non-Leakage Sonnet Run

Phase 0B is the first full main-cue LLM run:

- 107 panels
- six non-leakage cue conditions
- 642 requests
- Sonnet first
- `raw_assay_stats_shown` excluded

The dedicated sbatch script creates `requests_full_nonleakage.jsonl` from
`requests_full.jsonl`, checks that it has exactly 642 records, runs Sonnet with
resume enabled, then writes scores, paired cue effects, cue-attribution,
explanation-faithfulness, trajectories, and trajectory summaries.

Submit on Cayuga:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
SLURM=/opt/ohpc/pub/software/slurm/24.05.2/bin
ssh <HPC_LOGIN> "cd $REMOTE && $SLURM/sbatch experiments/trust_cue_attribution/hpc/run_phase0b_sonnet.sbatch"
```

Use the same script to resume after interruption. It appends only missing
packet IDs because `run-llm-episodes` uses `--resume`.

Check progress:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
SLURM=/opt/ohpc/pub/software/slurm/24.05.2/bin
ssh <HPC_LOGIN> "$SLURM/squeue -u USER"
ssh <HPC_LOGIN> "wc -l $REMOTE/experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_phase0b_main_episodes.jsonl"
```

Expected final main outputs:

```text
experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/
  requests_full_nonleakage.jsonl
  llm_claude-sonnet-4-6_phase0b_main_episodes.jsonl
  llm_claude-sonnet-4-6_phase0b_main_analysis.json
  llm_claude-sonnet-4-6_phase0b_main_scores_lambda_0.2.json
  llm_claude-sonnet-4-6_phase0b_main_scores_lambda_0.5.json
  llm_claude-sonnet-4-6_phase0b_main_scores_lambda_0.8.json
  llm_claude-sonnet-4-6_phase0b_main_paired_effects_lambda_0.2.json
  llm_claude-sonnet-4-6_phase0b_main_paired_effects_lambda_0.5.json
  llm_claude-sonnet-4-6_phase0b_main_paired_effects_lambda_0.8.json
  llm_claude-sonnet-4-6_phase0b_main_cue_attribution.json
  llm_claude-sonnet-4-6_phase0b_main_explanation_faithfulness.json
  llm_claude-sonnet-4-6_phase0b_main_trajectories.jsonl
  llm_claude-sonnet-4-6_phase0b_main_trajectory_summary.json
```

Fetch after completion:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
rsync -av <HPC_LOGIN>:$REMOTE/experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/ \
  ./experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/
```

Freeze the synced full-run state locally:

```bash
python3 experiments/trust_cue_attribution/run.py freeze-phase0b \
  --input-dir experiments/trust_cue_attribution/hpc_outputs/phase0_smoke \
  --out-dir experiments/trust_cue_attribution/results/phase0b_freeze
```

Build the Phase 0B panel-cluster bootstrap robustness summary:

```bash
python3 experiments/trust_cue_attribution/run.py phase0b-robustness \
  --input-dir experiments/trust_cue_attribution/hpc_outputs/phase0_smoke \
  --out experiments/trust_cue_attribution/results/phase0b_robustness/summary.json \
  --n-boot 1000 \
  --seed 13 \
  --lam 0.5
```

Then score the real episodes:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
ssh <HPC_LOGIN> "cd $REMOTE && /usr/bin/python3.12 experiments/trust_cue_attribution/run.py score-episodes \
  --panels experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --packets experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/cue_packets_full.jsonl \
  --episodes experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_episodes.jsonl \
  --out experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_scores_lambda_0.5.json"
```

Run paired cue effects against `no_cue` for the same panel/gene:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
ssh <HPC_LOGIN> "cd $REMOTE && /usr/bin/python3.12 experiments/trust_cue_attribution/run.py paired-cue-effects \
  --panels experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --packets experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/cue_packets_full.jsonl \
  --episodes experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_episodes.jsonl \
  --out experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_paired_effects_lambda_0.5.json"
```

Run categorical cue-attribution coefficients against `no_cue`:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
ssh <HPC_LOGIN> "cd $REMOTE && /usr/bin/python3.12 experiments/trust_cue_attribution/run.py cue-attribution \
  --panels experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --packets experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/cue_packets_full.jsonl \
  --episodes experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_episodes.jsonl \
  --out experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_cue_attribution.json"
```

Or submit the bounded pilot sbatch script. Start with a small `LIMIT` before running all 642 cue packets:

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
SLURM=/opt/ohpc/pub/software/slurm/24.05.2/bin
ssh <HPC_LOGIN> "cd $REMOTE && MODEL=YOUR_MODEL LIMIT=24 $SLURM/sbatch experiments/trust_cue_attribution/hpc/run_phase0_llm_pilot.sbatch"
```

The bounded pilot defaults to `PROVIDER=anthropic_messages`. Override `PROVIDER=openai_responses` only when intentionally running OpenAI instead of Claude.

## Latest Cayuga Smoke

Latest validated run:

- Job id: `3043801`
- Status marker: `TRUST_CUE_PHASE0_SMOKE_OK`
- Tests: `16 tests OK`
- Full panels: 107
- Additive panels: 45
- Cue packets: 749
- Request records: 749
- Mock provider episodes: 12
- Claude provider path: `anthropic_messages`
- Synthetic policy episodes: 749
- Synthetic policy scores: generated
- Synced local outputs: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/`

## Latest Claude Pilot

Latest real Claude pilot:

- Job id: `3043795`
- Provider: `anthropic_messages`
- Model: `claude-sonnet-4-6`
- Limit: 24 requests
- Status marker: `TRUST_CUE_PHASE0_LLM_PILOT_OK`
- Episodes: 24
- Parse/provider errors: none observed
- Overall net/gene at lambda 0.5: 0.738
- Synced local outputs:
  - `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_episodes_limit_24.jsonl`
  - `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_scores_limit_24_lambda_0.5.json`

Latest raw-assay positive-control pilot:

- Job id: `3043802`
- Provider: `anthropic_messages`
- Model: `claude-sonnet-4-6`
- Limit: 7 requests
- Status marker: `TRUST_CUE_PHASE0_LLM_PILOT_OK`
- Positive-control cue: `raw_assay_stats_shown`
- Raw-assay cue score on first panel: accuracy 1.000, trust error 0.000, verify recall 1.000

Latest stratified main-pilot request set:

- Smoke job after selector: `3043805`
- Tests: `18 tests OK`
- Selected panels: 12
- Requests: 72
- Cues: six non-leakage main cues
- Request file: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/requests_pilot72_main.jsonl`
- Manifest: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/requests_pilot72_main_manifest.json`

Latest stratified main-pilot Claude run:

- Job id: `3043806`
- Provider: `anthropic_messages`
- Model: `claude-sonnet-4-6`
- Episodes: 72
- Status marker: `TRUST_CUE_PHASE0_LLM_PILOT_OK`
- Parse/provider errors: none observed
- Overall net/gene at lambda 0.5: 0.687
- Output episodes: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_episodes.jsonl`
- Output scores: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_scores_lambda_0.5.json`
- Output analysis: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_analysis.json`
- Output paired cue effects: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_paired_effects.json`
- Latest analysis-code validation: 19 `unittest discover` tests OK on Cayuga

Latest Opus 4.8 comparison run:

- Job id: `3043812`
- Provider: `anthropic_messages`
- Model: `claude-opus-4-8`
- Requests: same 72-request stratified main pilot
- Status marker: `TRUST_CUE_PHASE0_LLM_PILOT_OK`
- Episodes: 72
- Overall accuracy at lambda 0.5: 0.804
- Overall net/gene at lambda 0.5: 0.658
- Output episodes: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-opus-4-8_pilot72_main_episodes.jsonl`
- Output scores: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-opus-4-8_pilot72_main_scores_lambda_0.5.json`
- Output analysis: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-opus-4-8_pilot72_main_analysis.json`
- Output paired cue effects: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-opus-4-8_pilot72_main_paired_effects.json`

Latest Sonnet/Opus lambda sweep:

- Inputs: existing Sonnet 4.6 and Opus 4.8 pilot72 episode JSONL files
- Lambda values: `0.2`, `0.5`, `0.8`
- No new LLM/API calls
- Break-even lambda for Opus vs Sonnet net/gene: approximately `0.234` (pilot72 estimate; the frozen full run gives ≈`0.223`)
- Output summary: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/lambda_sweep_summary_sonnet4_6_vs_opus4_8.json`
- Interpretation: Opus wins only when verification is very cheap; Sonnet wins once assay cost is non-trivial.

Latest cue-attribution regression:

- Analysis-code validation: 20 `unittest discover` tests OK on Cayuga
- Method: one-vs-rest categorical logistic cue attribution with `no_cue` baseline
- Sonnet output: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_cue_attribution.json`
- Opus output: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-opus-4-8_pilot72_main_cue_attribution.json`
- Interpretation: Sonnet mainly shifts from trust to default under strong cues; Opus shifts more into costly verification under misleading reliability.

Latest explanation-faithfulness gap:

- Analysis-code validation: 20 `unittest discover` tests OK on Cayuga
- Method: compare `self_reported_cues` and rationale keyword traces against measured cue-attribution action-rate shifts
- Sonnet output: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_explanation_faithfulness.json`
- Opus output: `experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-opus-4-8_pilot72_main_explanation_faithfulness.json`
- Interpretation: explicit primary cues are usually acknowledged, but unavailable cues are often self-reported, especially Sonnet reporting baseline/confidence under `no_cue`.

Reproduce explanation-faithfulness on an existing episode file:

```bash
env PYTHONPATH=/scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution \
/usr/bin/python3.12 /scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution/run.py explanation-faithfulness \
  --panels /scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl \
  --packets /scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/cue_packets_full.jsonl \
  --episodes /scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_episodes.jsonl \
  --out /scratch/USER/LLM_SFM_interpretability/experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/llm_claude-sonnet-4-6_pilot72_main_explanation_faithfulness.json
```

## Phase 2: Protein-Structure Trust Substrate (Boltz)

Phase 2 re-bases the trust audit onto protein structure, where the specialist
(Boltz-2 / AlphaFold-class) beats baselines AND emits a validated, calibrated
confidence (pLDDT/PAE). See `PHASE2_PROTEIN_TRUST_DESIGN.md` and the adapter
contract `results/phase2_preflight/boltz_contract.json`. The calibration gate
code (`phase2_calibration_gate.py`, `phase2-calibration-gate`) is already in the
repo and tested; this runbook produces the records it consumes.

Leakage rule (new and critical in Phase 2): use ONLY targets released AFTER the
predictor's training cutoff (recent PDB / weekly CAMEO), so confidence is not
inflated by memorization. Experimental truth (lDDT/DockQ) is scorer-side only
and must never enter a model-visible packet.

### Step 1 — Boltz environment (Cayuga GPU)

Build the Boltz env via the committed script (uses `/usr/bin/python3.12` ->
`hpc_outputs/envs/boltz-py312`; Boltz needs Python >= 3.10). VALIDATED: Boltz
2.2.1 installs and runs on `scu-gpu` (A40, torch 2.12.1+cu130, MSA server
reachable) -- see `results/phase2_preflight/boltz_smoke_report.json`.

```bash
REMOTE=/scratch/USER/LLM_SFM_interpretability
ssh <HPC_LOGIN> "cd $REMOTE && bash experiments/trust_cue_attribution/hpc/build_phase2_boltz_env.sh"
```

### Step 2 — select leakage-safe targets

Pick post-training-cutoff targets with experimental structures, balanced across
regimes (power floor: >= 30 monomers AND >= 30 complexes, matching the gate's
`min_per_regime`). For each target record `target_id`, `regime`, sequence(s),
and the experimental-structure path. Do not let truth enter the prediction
inputs.

### Step 3 — Boltz inference (GPU)

Run the VALIDATED predict command (working invocation in
`run_phase2_boltz_smoke.sbatch`; `--no_kernels` avoids the optional
cuequivariance kernel, which is absent under cu13). One FASTA per target named
`<target_id>.fasta`, header `>A|protein` (complexes use `>A|protein` /
`>B|protein` chains):

```bash
ENV=experiments/trust_cue_attribution/hpc_outputs/envs/boltz-py312
$ENV/bin/boltz predict <target_id>.fasta \
  --out_dir "$PRED_DIR" --cache "$BOLTZ_CACHE" --use_msa_server \
  --accelerator gpu --model boltz2 --no_kernels --override --output_format mmcif
```

Then assemble the gate records with `phase2_records.py` (parser confirmed
against real Boltz 2.2.1 output): it reads each `confidence_<id>_model_0.json`
(`complex_plddt` is 0-1 -> scaled to 0-100; `iptm`/`protein_iptm` for complexes)
and joins the truth/baseline table.

### Step 4 — cheap baseline + held-out truth (hidden, scorer side)

- baseline: best PDB template by sequence identity (e.g. `foldseek`/`hmmer`
  search) -> homology model; set `template_baseline_correct` against truth.
- truth: superpose prediction vs experimental structure:
  - monomer: lDDT (OpenStructure `lddt`) or TM-score (`TMalign`); `correct = lDDT >= 0.7`
  - complex: `DockQ`; `correct = DockQ >= 0.23`
  - `quality` = the continuous lDDT/DockQ value.

### Step 5 — emit the records JSONL (gate input)

One line per target, matching `phase2_calibration_gate`'s schema; `truth.*` is
scorer-side only and must never appear in a model-visible packet:

```json
{"target_id":"7XYZ_A","regime":"monomer","mean_plddt":88.2,"iptm":null,"template_baseline_correct":true,"truth":{"correct":true,"quality":0.83}}
```

### Step 6 — run the offline calibration gate (no LLM call)

```bash
python3 experiments/trust_cue_attribution/run.py phase2-calibration-gate \
  --records experiments/trust_cue_attribution/hpc_outputs/phase2_boltz/records.jsonl \
  --out experiments/trust_cue_attribution/results/phase2_preflight/calibration_gate.json \
  --lam 0.5
```

Decision targets:

- `eligible_for_phase2_interface_pilot` -> build the cue matrix + a small pilot.
- `eligible_pending_more_targets` -> add post-cutoff targets (power floor).
- `redesign_policy_before_pilot` -> signal calibrated but policy weak; revisit.
- `do_not_run_signal_not_calibrated` -> stop; the substrate assumption failed.

The gate checks: confidence-derived wrong-risk AUROC, the monomer/complex
calibration gap, and whether `verify iff risk > lambda` beats trust-all,
default-template, and shuffled/inverted controls by a real margin.

### Step 7 — only if the gate passes

Build the five-arm cue matrix (`no_signal`, `raw_plddt_shown`,
`calibrated_risk_shown_no_recommendation`, `calibrated_interface_shown`,
`inverted_reliability_interface_control`), then run a small, power-justified
Sonnet pilot on the same actions/reward/cue-attribution/robustness stack. Do not
scale to a large matrix until the small pilot is scored.
