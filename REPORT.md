# When does an LLM trust a specialist model? A cost-aware trust-routing audit — and why "calibrated reliability interfaces" are not a free win

**Technical report — bio-sfm-trust-audit**
Date: 2026-06-19 · Status: exploratory report; confirmatory redo pre-registered (see `PHASE2_PREREGISTRATION.md`)
Repo: `jang1563/bio-sfm-trust-audit`

## Abstract

Frontier AI-for-science systems increasingly place a general LLM *above*
specialist scientific models (protein, genome, single-cell), where the LLM must
decide — under a verification cost — whether to **trust** a specialist's output,
**verify** it, fall back to a **cheap baseline**, or **defer**. We audit that
trust-routing decision and ask whether converting a specialist's reliability
evidence into an explicit *calibrated reliability interface* improves routing
over simply showing the raw confidence.

Across three substrates (a GEARS/Norman perturbation dry-run, a single-cell
foundation-model cue, and protein-structure prediction with Boltz-2/pLDDT) the
robust finding is **cautionary, not celebratory**. (1) The LLM reasoning layer is
strongly **cue-sensitive**: shown any reliability signal it routes far better than
with none, but it also follows misleading signals. (2) On a *validated, calibrated*
signal (pLDDT, which predicts true lDDT at Pearson 0.89 for monomers), an LLM
(Claude Sonnet 4.6) converts it into much better cost-aware routing — **but the
benefit comes from the calibrated *information*, not a directive recommendation**,
and **packaging it as a "reliability card" does not robustly beat showing the raw
confidence number** (Δnet +0.025, 95% CI [−0.037, +0.087]). (3) The card is
**model-dependent and can backfire**: Claude Opus 4.8, a more risk-averse model,
**over-verifies** under the card (97.5% verify rate) and is *significantly worse*
than with raw confidence (Δnet −0.225, CI [−0.325, −0.113]), replicating the
"stronger reasoning ≠ better cost-aware orchestration" pattern. We conclude that
**raw calibrated confidence is the robust lever; prompt-visible reliability
*interfaces* are not a free win and are model-dependent** — presentation alone is
insufficient, motivating enforcement-based (tool/MCP/post-training) routing.

## 1. Question

> What does an LLM reasoning layer trust when it reads a specialist scientific
> model's output, and can that trust be made calibrated, auditable, and useful
> under verification cost?

Action set per item: `trust_sfm | verify_assay | default_baseline | defer`.
Reward: `net = correct − λ·assays` (λ = verification price; primary λ = 0.5).

## 2. What each phase found

- **Phase 0 (GEARS/Norman dry run, 642 non-leakage Sonnet requests).** Routing is
  strongly cue-sensitive and only weakly calibrated; additive-disagreement
  evidence helps, misleading "reliability cards" hurt, and self-reported
  rationales frequently cite unavailable evidence.
- **Phase 1 (single-cell scFoundation cue).** NO-GO. The scFoundation-derived
  edge cue predicts GEARS wrongness at AUROC 0.599 vs 0.576 for a random
  same-gene control — near-noise. A specialist-metric check found GEARS ≈ a
  cheap additive baseline (replicating Ahlmann-Eltze et al. 2025). You cannot
  study calibrated trust where the signal carries no validated information.
- **Phase 2 (protein structure, Boltz-2 / pLDDT).** A substrate where the
  specialist is excellent *and* emits a validated calibrated confidence — the
  focus of this report.

## 3. Phase 2 methods (brief)

- **Substrate.** 80 RCSB targets released 2026-06-17 (after Boltz-2's 2023-06
  training cutoff → leakage-safe), 40 monomer + 40 complex; sequences + reference
  structures from RCSB; structures predicted with Boltz-2 on an A100/A40 (Cayuga).
- **Truth.** Superposition-free CA-lDDT of prediction vs experimental reference
  (Mariani et al. 2013), monomer single-chain and complex all-chain
  (interface-inclusive). *Caveat: home-grown CA-lDDT, not yet validated against
  OpenStructure; complexes use lDDT, not DockQ.*
- **Calibrated signal.** pLDDT→P(wrong) via leave-one-out isotonic regression.
  pLDDT predicts lDDT at **Pearson 0.89 (monomers), 0.16 (complexes)** — the
  designed monomer→complex calibration gap, confirmed.
- **Offline gate.** A deterministic "verify iff calibrated-risk > λ" policy must
  beat trust-all + shuffled/inverted controls before any LLM call. *Caveat: it
  is degenerate at the standard lDDT ≥ 0.7 cutoff (Boltz-2 is correct on ~95% of
  recent targets) and was made to pass at lDDT ≥ 0.9 — a post-hoc choice; signal
  AUROC there is 0.89.*
- **LLM pilot.** A balanced **40-target subset (20 monomer + 20 complex)** of the
  80-target benchmark, stratified across the lDDT range, × 5 arms = 200 requests,
  Sonnet 4.6 and Opus 4.8, scored against held-out lDDT-truth. (The full 80 targets
  are used for the offline calibration gate.) Arms: `no_signal`, `raw_plddt_shown`,
  `calibrated_risk_shown_no_recommendation` (information without a directive),
  `calibrated_interface_shown` (risk + recommended action),
  `inverted_reliability_interface_control`.

## 4. Results

### 4.1 Sonnet (λ = 0.5, lDDT ≥ 0.9; target-bootstrap 95% CIs, seed 13)

| arm | net/target | Δ vs no_signal (95% CI) |
|---|---:|---|
| calibrated_interface_shown | 0.738 | +0.487 [+0.338, +0.625] |
| calibrated_risk_shown_no_recommendation | 0.725 | +0.475 [+0.325, +0.613] |
| raw_plddt_shown | 0.713 | +0.463 [+0.300, +0.613] |
| inverted_reliability_interface_control | 0.388 | +0.138 [+0.025, +0.250] |
| no_signal | 0.250 | — |

- **Any confidence cue robustly beats no-signal** (+0.46–0.49, CIs exclude 0).
  With no signal Claude defers/over-verifies ("can't assess reliability").
- **A4 — the benefit is informational, not directive.** calibrated_interface vs
  calibrated_risk_*no_recommendation*: Δ +0.013, CI [+0.000, +0.037] ≈ 0.
- **The calibrated card does NOT robustly beat raw pLDDT.** calibrated_interface
  vs raw_plddt: Δ +0.025, CI [−0.037, +0.087] — crosses zero.
- **Regime-appropriate caution.** Under the card, verify rate is 0.55 on
  complexes vs 0.20 on monomers — more checking exactly where pLDDT calibration
  degrades.
- **Cue-sensitivity persists.** The inverted card degrades routing 0.738 → 0.388.

### 4.2 Cross-model (Opus 4.8, same 200 requests)

| arm | Sonnet net | Opus net | Sonnet verify | Opus verify |
|---|---:|---:|---:|---:|
| raw_plddt_shown | 0.713 | 0.713 | 0.225 | 0.275 |
| calibrated_interface_shown | 0.738 | **0.487** | 0.375 | **0.975** |
| no_signal | 0.250 | 0.150 | 0.500 | 0.300 |

Opus calibrated_interface vs raw_plddt: **Δ −0.225, CI [−0.325, −0.113]** —
**robustly worse**. The risk-framed card triggers blanket over-verification in
the more risk-averse model (it verifies even confident monomers). A4 holds for
Opus too (card vs no-recommendation = 0).

### 4.3 Robustness

The Sonnet/Opus conclusions are **stable across lDDT cutoffs 0.5–0.9**
(`results/phase2_preflight/cutoff_robustness.json`): calibrated_interface − raw
is ≈ 0 for Sonnet and ≈ −0.25 for Opus at every cutoff — so the post-hoc 0.9
choice affects only the offline-gate variance, not the pilot conclusions. Across
λ = 0.2/0.5/0.8 the lower arms keep their order; the only change is that
calibrated_interface and raw_plddt swap at the top under high cost (card−raw:
+0.070 / +0.025 / −0.020 at λ = 0.2/0.5/0.8) — which further supports that the
card does not robustly beat raw confidence.

## 5. Interpretation

The robust, cross-phase, cross-model claim:

> The LLM reasoning layer is **cue-sensitive**; surfacing **raw calibrated
> confidence** is the robust lever for better cost-aware routing; repackaging it
> as a calibrated **reliability *interface*** is **not a free win and is
> model-dependent** — neutral for Sonnet and harmful for the more risk-averse
> Opus, which over-verifies. The benefit, where present, is **informational, not
> directive**. Presentation alone is insufficient; **enforcement** (tools, MCP
> constraints, or post-training) is the natural next lever.

This extends Turpin et al. (2023) — LLMs follow cues regardless of validity —
into a constructive, *calibrated-signal* regime: a correctly calibrated cue helps
(via its information), a misleading one hurts, and a "reliability card" framing
can over-trigger a risk-averse model.

## 6. Relation to prior work

- **Proto / EvoDesign (Merchant, Guo, Viggiano, ... Hie; bioRxiv 2026.06.22.733870)
  — the most directly relevant system.** Proto is a high-level programming language
  for generative biology: an LLM/agent composes ~120 specialist models (Evo2, ESM3,
  AlphaFold3, Boltz-2, AlphaGenome, ProteinMPNN, ...) into multi-objective design
  programs, treating each specialist's confidence as an energy to minimize
  (pi(x) ~ p(x)*exp(-f(x)/T)). It is the strongest existing validation of the hybrid
  "reasoning layer above specialist models" stack this project assumes -- but it
  trusts specialist confidence UNCONDITIONALLY: no calibrated trust/verify/defer
  decision, no verification price, no audit of the reasoning layer's trust. Proto
  itself reports the gap we study -- "structure-prediction metrics are plausibility
  filters, not guarantees of function"; "no single in-silico metric separated
  functional from non-functional designs" -- and routes around it with multi-objective
  consensus plus tens of wet-lab tests. Two of its constructions are concrete,
  *uncalibrated* precedents for our actions: (i) its 8-stage CRISPR filter cascade
  runs cheap filters first and expensive AlphaFold3 last with short-circuiting -- a
  hand-built, cost-ordered verify-vs-defer pipeline (our net = correct - lambda*assays
  objective, minus the calibration); (ii) its multi-oracle structure consensus
  (require Boltz-2 AND AF2 AND AF3 to agree) is an uncalibrated verify-by-consensus.
  Our contribution is the calibrated, cost-aware, pre-registered trust layer that
  Proto-class agentic systems currently lack.
- **Cue-following / unfaithfulness:** Turpin et al. 2023. We add a cost-aware
  routing game and a *validated-calibrated* cue.
- **Cost-aware routing / selective prediction:** ASPEST (Kim et al. 2023),
  Adaptive-RAG, FrugalGPT/RouteLLM, learning-to-defer (Madras 2018; Mozannar &
  Sontag 2020). We route over a *fallible scientific specialist* under an assay cost.
- **Specialist soundness:** Ahlmann-Eltze, Huber & Anders 2025 (perturbation FMs
  ≈ linear baselines — why single-cell failed here); Jumper et al. 2021 and the
  McGuffin-group calibration audit 2024 (pLDDT calibration — why protein
  structure worked); Cheng et al. 2023 (AlphaMissense — a runner-up substrate).

## 7. Limitations

(a) Offline-gate PASS engineered post-hoc (lDDT ≥ 0.9 + in-distribution LOO
calibration); (b) home-grown CA-lDDT, unvalidated vs OpenStructure, complexes not
DockQ; (c) low-stakes substrate (~95% correct at lDDT ≥ 0.7); (d) the
model-visible packet contains only confidence (+ regime), so "uses the signal" is
partly forced; (e) n = 40, single primary λ, single MSA source, one run per
model, default-False template baseline. A pre-registered confirmatory redo
addressing all of these is specified in `PHASE2_PREREGISTRATION.md`.

## 7b. Post-publication validation (2026-06-23, on-cluster)

Three follow-up checks on Cayuga directly test the limitations above against
gold-standard tools (artifacts under `results/phase2_{ost,dockq,leakage}_*`):

- **Monomer truth — confirmed.** OpenStructure all-atom lDDT vs the home-grown CA-lDDT
  on the 40 monomers: Pearson **0.99**; pLDDT→OST-lDDT = **0.894**, confirming the
  headline 0.89 monomer calibration against the gold standard.
- **Complex truth — corrected.** The all-chain CA-lDDT is intra-chain-dominated, so the
  reported pLDDT→complex "calibration collapse" (0.16) was largely a **metric artifact**.
  Against gold-standard **DockQ** (40 complexes): pLDDT→DockQ = **0.44**, and the proper
  interface confidence **ipTM→DockQ = 0.77** — the specialist *is* well-calibrated on
  complexes; route on ipTM, not pLDDT. Re-scoring the v1 episodes with DockQ truth leaves
  the headline intact (interface−raw ≈ 0 for Sonnet, ≈ −0.25 for Opus).
- **Leakage — the "leakage-safe" claim does not hold.** An MMseqs2 search of all 80
  targets vs the full PDB, date-filtered via RCSB, finds that **~70% (56/80 at a 2024
  cutoff) have a ≥90%-identical pre-cutoff homolog**. Release-date curation did not prevent
  training leakage; the ~95% base rate is partly memorization. The pre-registered redo's
  homolog dedup is therefore empirically required, and the substrate must be re-curated
  for genuinely low-homology folds.

Net: the routing **headline survives**, the monomer metric holds, the complex-calibration
story is corrected, and the substrate's leakage is the principal reason to execute the
confirmatory redo rather than lean on v1.

**Redo update (executed).** A genuinely leakage-controlled set was then curated
(MMseqs2 vs full PDB + RCSB dates: **92% of recent post-cutoff depositions carry a ≥30%
pre-cutoff homolog**; 21 non-redundant low-homology targets survive) and predicted with
Boltz-2. It is **100%/100% correct at the pre-registered cutoffs** (monomer lDDT ≥ 0.7,
complex DockQ ≥ 0.23). So Boltz-2 succeeds on recent novel folds too: the **low-stakes
problem is intrinsic to recent high-resolution structures, not an artifact of leakage**
(the redo separates the two confounds). By the project's own NO-GO discipline a full *confirmatory*
pilot cannot run on a 100%-base-rate substrate — a real routing substrate needs specialist
*failure* cases (harder modalities), motivating the enforcement-layer pivot. A bounded
3-model demo (Sonnet 4.6, Opus 4.8, GPT-4.1) makes the consequence concrete and is
identical across all three: `calibrated_interface − raw_plddt` net = **−0.476** on the
saturated substrate (the risk card triggers blanket over-verification where trust-all is
free) vs **+0.05** only once stakes are manufactured (lDDT ≥ 0.9) — fresh, leakage-controlled,
cross-model evidence that **reinforces the headline** (raw confidence is the robust lever;
the reliability interface is not a free win). See `results/phase2_redo_curation/`.

## 8. Reproducibility

All code, tests (163 passing), and compact result artifacts are in the repo under
`experiments/trust_cue_attribution/`. Key artifacts:
`results/phase2_preflight/{boltz_contract,boltz_smoke_report,calibration_gate,
calibrated_gate,interface_pilot_score,interface_pilot_robustness,
interface_pilot_score_opus,interface_pilot_robustness_opus,cutoff_robustness}.json`.
Pipeline: `phase2_curate_pdb.py` → Boltz predict → `phase2_truth.py` (CA-lDDT) →
`phase2_records.py` → `phase2_calibrated_gate.py` → `phase2_interface_pilot.py`
→ `phase2_score_episodes.py` / `phase2_robustness.py`. Large JSONL (requests,
episodes, structures) stay ignored under `hpc_outputs/`.

## How to cite

See `CITATION.cff`. This report is intended for archival via Zenodo (GitHub
release → DOI); the pre-registration is intended for OSF.
