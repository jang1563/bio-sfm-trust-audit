---
license: cc-by-4.0
language:
- en
pretty_name: Protein-Structure Trust-Routing Benchmark (Boltz-2)
tags:
- biology
- protein-structure
- docking
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
- config_name: strict_complex_dockq
  data_files:
  - split: test
    path: data/phase4_confirmatory.jsonl
- config_name: monomer_complex_lddt
  data_files:
  - split: test
    path: data/phase2_targets.jsonl
---

# Protein-Structure Trust-Routing Benchmark (Boltz-2)

Leakage-controlled benchmarks for **confidence-calibrated trust routing** over a protein-structure
predictor: given a specialist model's confidence (Boltz-2 ipTM / pLDDT) for a target, decide whether to
**trust** the prediction or pay to **verify** it — and score that decision against experimentally-measured
correctness. Evaluation substrate for the report *"When does an LLM trust a specialist model? A cost-aware
trust-routing audit"* ([repo](https://github.com/jang1563/bio-sfm-trust-audit)).

Two configs:

| config | n | truth | leakage control | base rate | role |
|---|---:|---|---|---:|---|
| **`strict_complex_dockq`** | 158 | **DockQ** (gold-standard interface) | MMseqs2 vs full PDB + release date (no pre-cutoff homolog ≥ 30 % id) | 60 % @ DockQ ≥ 0.49 | primary — genuine stakes |
| `monomer_complex_lddt` | 80 | CA-lDDT | release date only | high (~95 % @ 0.7) | original; low-stakes |

`strict_complex_dockq` is the recommended config: gold-standard DockQ truth, strict sequence-identity leakage
control, and a genuine ~50/50 success base rate (a real trust/verify decision rather than a saturated one).

## Fields

**`strict_complex_dockq`** (`data/phase4_confirmatory.jsonl`):

| field | type | description |
|---|---|---|
| `target_id` | str | RCSB PDB id (released ≥ 2025-07-01) |
| `regime` | str | `complex` |
| `mean_plddt` | float | Boltz-2 complex pLDDT (0–100) |
| `iptm` | float | Boltz-2 interface pTM |
| `dockq` | float | DockQ of the prediction vs the experimental structure (0–1) |
| `correct_at_0.49` | bool | `dockq ≥ 0.49` (CAPRI "medium") — the trust-is-correct label |
| `template_baseline_correct` | bool | a usable pre-cutoff homology template exists (≥ 50 % id) — all `false` here, the honest consequence of strict leakage control |

**`monomer_complex_lddt`** (`data/phase2_targets.jsonl`): `target_id, regime (monomer|complex), mean_plddt,
iptm (null for monomers), truth_lddt, correct_at_0.7/0.8/0.9, template_baseline_correct`.

## Key statistics

- **`strict_complex_dockq`** — ipTM→DockQ Pearson **0.57**: a moderately-predictive cue under strict leakage,
  deliberately weaker than the ~0.84 seen under looser controls. DockQ median 0.58, range 0.005–0.902;
  95/158 at DockQ ≥ 0.49.
- **`monomer_complex_lddt`** — pLDDT→lDDT Pearson 0.89 (monomers) vs 0.16 (complexes): the monomer→complex
  calibration gap; high, low-stakes base rate at lDDT ≥ 0.7.

## Intended use

- Benchmark **selective prediction / cost-aware trust routing**: map confidence → P(correct), evaluate
  trust-vs-verify policies under a verification price.
- Study **confidence calibration** (ipTM/pLDDT vs measured correctness) and its degradation under strict leakage.

## Quick start

```python
from datasets import load_dataset
ds = load_dataset("jang1563/protein-structure-trust-benchmark", "strict_complex_dockq", split="test")
print(ds[0])
```

## Provenance & honest limitations

- **Provenance.** Targets + reference coordinates from [RCSB PDB](https://www.rcsb.org); predictions from
  [Boltz-2](https://github.com/jwohlwend/boltz) (`--use_msa_server`). Build scripts (`phase4_harvest.py`,
  `phase4_leakage.py`, `phase4_dockq.py`) are in the repo.
- **Limitations.** Sequence-identity leakage is a proxy for memorization (not proof of a Boltz-2 training
  split); `template_baseline_correct` is derived from pre-cutoff homolog availability (all-false on the strict
  set); the `monomer_complex_lddt` truth is a home-grown CA-lDDT (not OpenStructure) with a low-stakes base rate.

## Citation

See `CITATION.cff` in the [repo](https://github.com/jang1563/bio-sfm-trust-audit). Archival: Zenodo DOI pending.
