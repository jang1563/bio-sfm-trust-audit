# Phase 2 — OpenStructure lDDT validation of the monomer truth metric

**What.** Completes the truth-metric validation: the [DockQ pass](../phase2_dockq_validation/)
showed the v1 *complex* metric (all-chain CA-lDDT) was the wrong axis; here we check the
v1 *monomer* metric (home-grown CA-lDDT) against gold-standard **OpenStructure lDDT**
(all-atom, OST 2.11) on the 40 v1 monomers. Compute: Cayuga. Artifacts:
[`ost_validation.json`](ost_validation.json), runner [`run_ost_validation.py`](run_ost_validation.py).

## Result (n = 40 monomers)

| correlation | value | note |
|---|---:|---|
| Pearson(CA-lDDT v1, **OST-lDDT**) | **+0.99** | the home-grown *monomer* truth **agrees with the gold standard** |
| Pearson(pLDDT, **OST-lDDT**) | **+0.894** | the **true** monomer calibration |
| Pearson(pLDDT, CA-lDDT v1) | +0.891 | the v1 monomer number (report claimed 0.89) |

mean |OST-lDDT − CA-lDDT v1| = 0.045.

## Interpretation

Unlike the complex metric, the **v1 monomer CA-lDDT was sound** (0.99 agreement with OST),
and the report's headline monomer calibration (**pLDDT→lDDT = 0.89**) is **confirmed against
the gold standard** (0.894). So the truth-metric problem was *specific to complexes*
(intra-chain-dominated all-chain CA-lDDT), now fixed by DockQ.

## The three validation passes together

| pass | finding | verdict on v1 |
|---|---|---|
| **monomer lDDT (OST)** | CA-lDDT≈OST 0.99; pLDDT→lDDT 0.89 confirmed | monomer truth + calibration **OK** |
| **complex DockQ** | CA-lDDT≈DockQ 0.30; pLDDT→DockQ 0.44, ipTM→DockQ 0.77 | complex truth **broken**; calibration **better than reported** (route on ipTM) |
| **leakage (MMseqs2)** | ~70% of targets have a ≥90% pre-cutoff homolog | "leakage-safe" claim **does not hold** |

Net: the routing **headline survives** (see the [DockQ re-score](../phase2_dockq_validation/#does-the-headline-survive-the-metric-fix-re-scoring-v1-routing)),
the complex-calibration story is corrected, and the substrate must be **re-curated for
low homology** for the confirmatory redo.
