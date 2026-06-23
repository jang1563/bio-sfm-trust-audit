# HPC Scripts

Use these scripts on Cayuga or Expanse. Do not treat local compute as the validation target for this project.

## Scripts

- `run_phase0_smoke.sbatch`: Phase 0 GEARS/Verify-or-Trust smoke job. Runs tests, panel generation, cue packet generation, and deterministic baselines.
- `run_phase0_llm_pilot.sbatch`: parameterized small LLM episode runner for wiring checks and pilot batches.
- `run_phase0b_sonnet.sbatch`: full 642-request non-leakage Sonnet run plus scoring, paired cue effects, cue attribution, explanation-faithfulness, and trajectory summaries.
- `build_phase1_scfoundation_env.sh`: isolated conda/pip environment builder for Phase 1 scFoundation smoke tests. It writes under ignored `hpc_outputs/envs/` and does not modify existing user conda envs.
- `run_phase1_scfoundation_probe.sbatch`: lightweight Phase 1 scFoundation preflight/probe job. It runs tests, writes the adapter contract, and checks whether the scFoundation repo, gene index, checkpoint, and Phase 1 input data are staged. It does not load model weights or run inference.
- `run_phase1_scfoundation_inventory.sbatch`: lightweight Phase 1 input compatibility inventory. It checks whether the staged h5ad gene set overlaps the scFoundation gene vocabulary. It does not load model weights or run inference.
- `run_phase1_scfoundation_env_probe.sbatch`: lightweight Phase 1 inference-environment probe. It checks imports, CUDA visibility, scFoundation model files, and `load.py` import readiness. It does not load checkpoints or run inference.
- `run_phase1_scfoundation_smoke.sbatch`: tiny true scFoundation inference smoke. It creates a small h5ad subset, runs official `get_embedding.py`, and writes a compact embedding summary. It is not a scientific result.

See `../HPC_RUNBOOK.md` for staging and submission commands.
