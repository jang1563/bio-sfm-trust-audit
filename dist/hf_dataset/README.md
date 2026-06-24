---
license: cc-by-4.0
language:
- en
pretty_name: Phase-2 Protein-Structure Trust Benchmark (Boltz-2 / pLDDT)
tags:
- biology
- protein-structure
- alphafold
- boltz
- confidence-calibration
- selective-prediction
- llm-trust-routing
- ai-for-science
task_categories:
- tabular-classification
size_categories:
- n<1K
configs:
- config_name: default
  data_files:
  - split: test
    path: data/phase2_targets.jsonl
---

# Phase-2 Protein-Structure Trust Benchmark (Boltz-2 / pLDDT)

A small, leakage-safe benchmark for studying **confidence-calibrated trust routing**
over a protein-structure predictor: given a specialist model's *confidence*
(Boltz-2 pLDDT / ipTM) for a target, decide whether to **trust** the prediction or
**verify** it — and score that decision against the experimentally-measured
*correctness* (CA-lDDT vs the released structure).

It is the evaluation substrate behind the technical report **"When does an LLM
trust a specialist model? A cost-aware trust-routing audit — and why calibrated
reliability interfaces are not a free win"** ([repo](https://github.com/jang1563/bio-sfm-trust-audit)).

> The report's LLM trust-routing pilot scores a balanced **40-target subset
> (20 monomer + 20 complex)** of these 80 targets; the full 80 are used for the
> offline calibration gate.

## What's in it

80 targets released **2026-06-17**, i.e. **after Boltz-2's 2023-06 training
cutoff** (leakage-safe), curated from RCSB: 40 single-chain **monomers** and 40
multi-chain **complexes** (resolution ≤ 3 Å). For each target we record the
specialist's confidence and the measured correctness of its Boltz-2 prediction.

`data/phase2_targets.jsonl` — one JSON object per target:

| field | type | description |
|---|---|---|
| `target_id` | str | RCSB PDB identifier |
| `regime` | str | `monomer` or `complex` |
| `mean_plddt` | float | Boltz-2 mean pLDDT (0–100), the calibrated confidence |
| `iptm` | float/null | Boltz-2 interface pTM (complexes; null for monomers) |
| `truth_lddt` | float | CA-lDDT of the prediction vs the experimental structure (0–1), superposition-free (Mariani et al. 2013); complexes use all-chain CA-lDDT |
| `correct_at_0.7` / `_0.8` / `_0.9` | bool | `truth_lddt ≥ cutoff` (0.7 = standard "modelable") |
| `template_baseline_correct` | bool | placeholder (all `false`) — a real homology/template baseline is left to the pre-registered redo |

## Headline statistics

| regime | n | mean pLDDT | mean lDDT | correct@0.7 | correct@0.8 | correct@0.9 |
|---|---:|---:|---:|---:|---:|---:|
| monomer | 40 | 90.2 | 0.942 | 1.00 | 0.95 | 0.82 |
| complex | 40 | 88.1 | 0.849 | 0.90 | 0.80 | 0.48 |

pLDDT predicts lDDT well for monomers (Pearson **0.89**) and far worse for
complexes (**0.16**) — the designed monomer→complex calibration gap. Note the
**high base rate** at the standard 0.7 cutoff (Boltz-2 is correct on ~95% of
recent targets): this is a known low-stakes property of the substrate.

## Intended use

- Benchmark **selective prediction / trust routing**: map confidence → P(correct)
  and evaluate "trust vs verify" policies under a verification cost.
- Study **confidence calibration** across the monomer/complex regimes.
- Reproduce the report's finding that **raw calibrated confidence is the robust
  routing lever**, while a prompt-visible "reliability interface" does **not**
  robustly beat it and can backfire by model.

## Quick start

```python
# On the Hub:
from datasets import load_dataset
ds = load_dataset("jang1563/protein-structure-trust-benchmark", split="test")
# Or read it directly from the GitHub repo:
#   import json; ds = [json.loads(l) for l in open("dist/hf_dataset/data/phase2_targets.jsonl")]
print(ds[0])
# e.g. correctness vs a confidence threshold:
import numpy as np
plddt = np.array(ds["mean_plddt"]); correct = np.array(ds["correct_at_0.9"])
for thr in (80, 85, 90):
    keep = plddt >= thr
    print(thr, "coverage", keep.mean().round(2), "precision", correct[keep].mean().round(2))
```

## Provenance & limitations

- **Provenance.** Targets and reference coordinates from [RCSB PDB](https://www.rcsb.org)
  (public). Predictions from [Boltz-2](https://github.com/jwohlwend/boltz). Curation:
  `phase2_curate_pdb.py`; truth: `phase2_truth.py` in the repo.
- **Limitations (honest).** Ground truth is a **home-grown CA-lDDT**, not yet
  validated against OpenStructure; complexes use all-chain CA-lDDT, **not DockQ**.
  Low base rate at lDDT ≥ 0.7. n = 80, single MSA source, `template_baseline`
  is a placeholder. A pre-registered confirmatory redo addressing these is in the
  repo (`PHASE2_PREREGISTRATION.md`).

## Citation

See `CITATION.cff` in the [repo](https://github.com/jang1563/bio-sfm-trust-audit).
Archived report + data: Zenodo DOI pending deposit.

## Related work

Turpin et al. 2023 (cue-following); ASPEST (Kim et al. 2023, selective
prediction); Jumper et al. 2021 / pLDDT calibration; Mariani et al. 2013 (lDDT);
Ahlmann-Eltze et al. 2025 (why single-cell FMs were not a usable substrate here).
