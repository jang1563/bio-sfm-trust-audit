# bio-sfm-trust-audit

Audit framework for **LLM trust-routing over biological science foundation model (SFM) outputs**.

> Frontier AI-for-science systems increasingly place a general LLM *above* specialist
> scientific models (protein, genome, single-cell), where the LLM must decide — under a
> verification cost — whether to **trust** a specialist's output, **verify** it, fall back
> to a **cheap baseline**, or **defer**. This project audits that trust-routing decision.

The action set per item is `trust_sfm | verify_assay | default_baseline | defer`, scored by
`net = correct − λ·assays` (λ = verification price; primary λ = 0.5).

## Headline finding (cautionary, not celebratory)

Across the initial perturbation, single-cell, and protein-structure substrates, and now a
follow-up variant-effect DMS arm:

- The LLM reasoning layer is strongly **cue-sensitive**: shown any reliability signal it routes
  far better than with none — but it also follows misleading signals.
- On a *validated, calibrated* signal (pLDDT, which predicts true lDDT at Pearson 0.89 for
  monomers), surfacing **raw calibrated confidence is the robust lever**.
- Repackaging that confidence as a calibrated **reliability *interface*** is **not a free win and
  is model-dependent** — neutral for Claude Sonnet 4.6, harmful for the more risk-averse Claude
  Opus 4.8, which over-verifies. The benefit, where present, is **informational, not directive**.

Presentation alone is insufficient; enforcement (tools / MCP constraints / post-training) is the
natural next lever. Full write-up: **[`REPORT.md`](REPORT.md)** (PDF: [`dist/REPORT.pdf`](dist/REPORT.pdf)).

Follow-up variant-effect result: on the first substrate that passes the full precondition gate,
the pre-registered H2 result is still null — a calibrated reliability interface does not robustly
beat raw specialist score across 3 models × 3 verification costs.

## Quickstart

```bash
pip install -r requirements.txt
pytest experiments/trust_cue_attribution/tests/   # 163 passing, runs in seconds
```

The test suite needs **no external data**. The **Phase 2 protein benchmark is
bundled** ([`dist/hf_dataset/`](dist/hf_dataset/)); the Phase 0/1 perturbation
inputs come from the author's other repositories and are not redistributed here —
the tracked [`results/`](experiments/trust_cue_attribution/results/) JSON artifacts
summarize those runs.

## Repository layout

| Path | What |
|---|---|
| [`REPORT.md`](REPORT.md) | Technical report (results, interpretation, limitations) |
| [`experiments/trust_cue_attribution/`](experiments/trust_cue_attribution/README.md) | Runnable trust-cue attribution harness (code + tests) |
| [`experiments/trust_cue_attribution/BENCHMARK_CARD.md`](experiments/trust_cue_attribution/BENCHMARK_CARD.md) | Benchmark card |
| [`experiments/trust_cue_attribution/SCHEMA.md`](experiments/trust_cue_attribution/SCHEMA.md) | Panel / cue / episode schema |
| [`experiments/trust_cue_attribution/PHASE2_PREREGISTRATION.md`](experiments/trust_cue_attribution/PHASE2_PREREGISTRATION.md) | Pre-registered confirmatory redo |
| [`experiments/trust_cue_attribution/PHASE4_PREREGISTRATION.md`](experiments/trust_cue_attribution/PHASE4_PREREGISTRATION.md) | Pre-registered enforcement confirmatory (Phase 4) |
| [`experiments/trust_cue_attribution/PHASE2_PROTEIN_TRUST_DESIGN.md`](experiments/trust_cue_attribution/PHASE2_PROTEIN_TRUST_DESIGN.md) | Phase 2 protein-substrate design |
| [`experiments/trust_cue_attribution/results/`](experiments/trust_cue_attribution/results/) | Compact result artifacts (JSON) |
| [`dist/hf_dataset/`](dist/hf_dataset/) | Public benchmark targets (Hugging Face dataset card + data) |

## Phases

- **Phase 0** — GEARS/Norman perturbation dry run (642 non-leakage Sonnet requests). Routing is
  strongly cue-sensitive and only weakly calibrated.
- **Phase 1** — single-cell scFoundation cue. **NO-GO**: the cue is near-noise (AUROC 0.599 vs
  0.576 random control); the specialist ≈ a cheap additive baseline. You cannot study calibrated
  trust where the signal carries no validated information.
- **Phase 2** — protein structure (Boltz-2 / pLDDT), the focus of the report: a substrate where
  the specialist is excellent *and* emits a validated calibrated confidence.
- **Follow-up variant-effect DMS** — the first precondition-passing substrate; confirms the same
  presentation-layer null and motivates enforcement-layer routing.

## Reproducibility

Code, tests (163 passing), and compact result artifacts live under
[`experiments/trust_cue_attribution/`](experiments/trust_cue_attribution/README.md). The Phase 2
pipeline: `phase2_curate_pdb.py` → Boltz predict → `phase2_truth.py` (CA-lDDT) → `phase2_records.py`
→ `phase2_calibrated_gate.py` → `phase2_interface_pilot.py` → `phase2_score_episodes.py` /
`phase2_robustness.py`. Large JSONL artifacts (requests, episodes, structures) are not tracked.

GPU jobs run on an HPC cluster; SLURM scripts are under
[`experiments/trust_cue_attribution/hpc/`](experiments/trust_cue_attribution/hpc/) and the runbook is
[`HPC_RUNBOOK.md`](experiments/trust_cue_attribution/HPC_RUNBOOK.md). Paths in the runbook use
placeholders (`/scratch/USER`, `<DATA_ROOT>`, `<HPC_LOGIN>`) — set them for your environment.

## How to cite

See [`CITATION.cff`](CITATION.cff). The report is intended for archival via Zenodo (GitHub release →
DOI); the pre-registration is intended for OSF.

## License

- **Code** — MIT (see [`LICENSE`](LICENSE)).
- **Report text** (`REPORT.md`, `dist/*.pdf`) and **benchmark data** (`dist/hf_dataset/`) — Creative
  Commons Attribution 4.0 ([CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)).
