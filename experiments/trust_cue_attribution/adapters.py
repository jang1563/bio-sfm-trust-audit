"""Model adapter contracts for trust-cue attribution.

Adapters turn model-specific outputs into the standardized panel and evidence
packet schema. The evaluator should consume these standardized records without
knowing which specialist model produced them.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class AdapterContract:
    name: str
    phase: str
    status: str
    compute_target: str
    specialist_model: str
    task_family: str
    required_inputs: list[str]
    standardized_outputs: list[str]
    evidence_fields: list[str]
    internal_signal_fields: list[str]
    hidden_fields: list[str]
    preflight_checks: list[str]
    claim_boundary: str

    def describe(self) -> dict[str, Any]:
        return asdict(self)


GEARSAdapter = AdapterContract(
    name="GEARSAdapter",
    phase="phase0",
    status="implemented",
    compute_target="local_or_hpc",
    specialist_model="GEARS dry-run substrate",
    task_family="perturbation_effect_call",
    required_inputs=[
        "gears_norman.csv",
        "gears_vs_real_all.csv",
        "labeled_marginal.csv",
    ],
    standardized_outputs=[
        "panels_full.jsonl",
        "cue_packets_full.jsonl",
        "requests_full.jsonl",
    ],
    evidence_fields=[
        "sfm_call",
        "sfm_log2fc",
        "model_card",
        "baseline_signal",
        "reliability_signal",
        "assay_stats_positive_control_only",
    ],
    internal_signal_fields=[],
    hidden_fields=[
        "truth.real_call",
        "truth.real_label",
        "fm.correct",
        "baseline_signal.correct",
        "raw assay stats except positive-control cue",
    ],
    preflight_checks=[
        "panel_count_nonzero",
        "cue_packets_include_main_nonleakage_cues",
        "heldout_truth_hidden_from_evidence_packet",
        "baseline_signal_available_for_default_baseline_action",
    ],
    claim_boundary="dry-run perturbation substrate; not a true SFM result",
)


ScFoundationAdapter = AdapterContract(
    name="ScFoundationAdapter",
    phase="phase1",
    status="preflight_contract",
    compute_target="cayuga_or_expanse",
    specialist_model="scFoundation or scFoundation-compatible single-cell SFM",
    task_family="single_cell_state_or_perturbation_evidence",
    required_inputs=[
        "single-cell expression matrix or perturbation cell-state dataset",
        "gene vocabulary mapping compatible with the SFM tokenizer",
        "cell or perturbation metadata",
        "held-out evaluation labels kept outside evidence packets",
        "cheap baseline signal such as no-change, observed-additive, or nearest-neighbor baseline",
    ],
    standardized_outputs=[
        "phase1_panels.jsonl",
        "phase1_cue_packets.jsonl",
        "phase1_internal_signal_summaries.jsonl",
        "phase1_requests.jsonl",
    ],
    evidence_fields=[
        "sfm_call or state/effect prediction",
        "sfm_effect_score or confidence proxy",
        "model_card",
        "baseline_signal",
        "reliability_signal",
        "internal_signal_summary",
    ],
    internal_signal_fields=[
        "embedding_norm_or_distance_summary",
        "nearest_neighbor_label_distribution",
        "layer_summary_if_available",
        "ood_or_uncertainty_proxy_if_available",
        "representation_delta_between_control_and_perturbed_state_if_available",
    ],
    hidden_fields=[
        "held-out truth labels",
        "post-treatment measured DE statistics unless positive-control cue",
        "correctness flags",
        "reward and score fields",
        "manual interpretation labels not available to the LLM",
    ],
    preflight_checks=[
        "runs_on_cayuga_or_expanse_without_local_large_memory_use",
        "maps model outputs into existing action enum",
        "produces at least one internal_signal_summary field",
        "keeps held-out labels out of evidence packets",
        "supports at least no_cue, model_name_shown, confidence_shown, baseline_disagreement_shown, and misleading_internal_signal_card",
        "can be scored by the existing scorer or declares an explicit score adapter",
    ],
    claim_boundary=(
        "interface preflight only until one full Phase 1 run is scored; no "
        "claim that the LLM uses true SFM internals faithfully"
    ),
)


Evo2Adapter = AdapterContract(
    name="Evo2Adapter",
    phase="phase2",
    status="planned_internal_feature_demo",
    compute_target="cayuga_or_expanse",
    specialist_model="Evo2",
    task_family="sequence_variant_or_likelihood_evidence",
    required_inputs=["sequence windows", "variant metadata", "held-out labels or benchmark scores"],
    standardized_outputs=["phase2_sequence_packets.jsonl"],
    evidence_fields=["sequence_likelihood", "variant_effect_proxy", "model_card"],
    internal_signal_fields=["embedding_summary", "SAE_feature_summary_if_available"],
    hidden_fields=["held-out labels", "reward and score fields"],
    preflight_checks=["adapter_contract_before_compute"],
    claim_boundary="planned; not part of Phase 1 single-cell extension",
)


AlphaGenomeAdapter = AdapterContract(
    name="AlphaGenomeAdapter",
    phase="phase3",
    status="planned_black_box_stress_test",
    compute_target="cayuga_or_expanse_or_api",
    specialist_model="AlphaGenome",
    task_family="regulatory_variant_evidence",
    required_inputs=["variant records", "regulatory region metadata", "held-out labels or benchmark scores"],
    standardized_outputs=["phase3_regulatory_packets.jsonl"],
    evidence_fields=["variant_effect_score", "regulatory_track_summary", "model_card"],
    internal_signal_fields=[],
    hidden_fields=["held-out labels", "reward and score fields"],
    preflight_checks=["adapter_contract_before_compute"],
    claim_boundary="planned flagship black-box stress test; not a Phase 1 claim",
)


BoltzStructureAdapter = AdapterContract(
    name="BoltzStructureAdapter",
    phase="phase2",
    status="preflight_contract",
    compute_target="cayuga_or_expanse",
    specialist_model="Boltz-1/Boltz-2 (AlphaFold3-class structure predictor)",
    task_family="protein_structure_prediction_with_calibrated_confidence",
    required_inputs=[
        "query protein or complex sequences (FASTA)",
        "post-training-cutoff held-out targets with experimental structures (CAMEO / recent PDB)",
        "cheap baseline structure (best template/homology model by sequence identity)",
        "held-out experimental truth (monomer lDDT/TM-score, complex DockQ) kept outside evidence packets",
    ],
    standardized_outputs=[
        "phase2_panels.jsonl",
        "phase2_cue_packets.jsonl",
        "phase2_reliability_cards.jsonl",
        "phase2_requests.jsonl",
    ],
    evidence_fields=[
        "predicted_structure_summary",
        "mean_plddt and per-region plddt buckets",
        "pae / pTM / ipTM interface and global confidence",
        "regime (monomer | complex)",
        "model_card",
        "baseline_signal (template/homology model)",
        "reliability_interface (calibrated risk card)",
    ],
    internal_signal_fields=[
        "per_residue_plddt_distribution",
        "interface_pae_summary",
        "ptm_iptm_global_confidence",
        "calibrated_wrong_risk_from_heldout_calibration_set",
    ],
    hidden_fields=[
        "held-out experimental structure and lDDT/DockQ truth",
        "correctness flags",
        "reward and score fields",
        "whether the target predates the model training cutoff",
    ],
    preflight_checks=[
        "runs_on_cayuga_or_expanse_gpu",
        "uses_only_post_training_cutoff_targets_to_prevent_memorization_leakage",
        "maps structure confidence into existing action enum trust_verify_default_defer",
        "offline_calibration_gate_passes_before_any_llm_call",
        "calibration_gate_checks_plddt_risk_auroc_regime_gap_and_deterministic_policy_vs_controls",
        "supports cue arms no_signal raw_plddt_shown calibrated_risk_shown_no_recommendation calibrated_interface_shown inverted_reliability_interface_control",
        "n_targets_prespecified_by_power_argument_not_default_small",
        "held_out_truth_and_training_membership_hidden_from_evidence_packets",
    ],
    claim_boundary=(
        "interface preflight only; tests LLM routing over a validated calibrated "
        "structure-confidence signal (pLDDT/PAE). No claim that Boltz/AlphaFold "
        "internals are interpreted, that pLDDT is calibrated for all complex "
        "classes, or of general SFM trust generalization"
    ),
)


ADAPTERS = {
    adapter.name: adapter
    for adapter in (
        GEARSAdapter,
        ScFoundationAdapter,
        Evo2Adapter,
        AlphaGenomeAdapter,
        BoltzStructureAdapter,
    )
}


def get_adapter_contract(name: str) -> AdapterContract:
    try:
        return ADAPTERS[name]
    except KeyError as exc:
        raise ValueError(f"unknown adapter {name!r}; available adapters: {sorted(ADAPTERS)}") from exc


def adapter_contracts() -> dict[str, dict[str, Any]]:
    return {
        name: adapter.describe()
        for name, adapter in sorted(ADAPTERS.items())
    }


def write_adapter_contract(name: str, out: str) -> dict[str, Any]:
    payload = get_adapter_contract(name).describe()
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return payload
