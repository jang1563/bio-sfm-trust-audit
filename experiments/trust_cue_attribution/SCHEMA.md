# Extended Panel Schema

## Action Enum

Allowed actions:

- `trust_sfm`
- `verify_assay`
- `default_baseline`
- `defer`

## Panel JSONL

One JSON object per line.

```json
{
  "panel_id": "TSC22D1",
  "perturbation": "TSC22D1",
  "adapter": "GEARSAdapter",
  "n_panel": 30,
  "n_wrong": 10,
  "edges": [
    {
      "edge_id": "TSC22D1::MAP7D1",
      "gene": "MAP7D1",
      "fm": {
        "model_name": "GEARS",
        "log2fc": 0.04,
        "call": "no_effect",
        "correct": true
      },
      "truth": {
        "real_call": "no_effect",
        "real_label": "TESTED_NEGATIVE"
      },
      "baseline_signal": {
        "source": "no_change",
        "log2fc": 0.0,
        "call": "no_effect",
        "correct": true,
        "abs_fm_minus_baseline": 0.04,
        "call_disagreement": false
      },
      "reliability_signal": {
        "source": "baseline_disagreement",
        "score": 0.04,
        "label": "low_sfm_error_risk"
      },
      "raw": {
        "raw_log2FC": 0.02,
        "raw_se": 0.07,
        "raw_q": 0.89,
        "n_trt": 258,
        "n_cntrl": 6921
      },
      "stratum": "correct_noeffect",
      "regime": "single_seen"
    }
  ]
}
```

## Cue Packet JSONL

Cue packets remove ground-truth fields and add presentation choices.

```json
{
  "packet_id": "TSC22D1::confidence_shown",
  "panel_id": "TSC22D1",
  "cue_condition": "confidence_shown",
  "available_actions": ["trust_sfm", "verify_assay", "default_baseline", "defer"],
  "scoring_key": [{"gene_display": "MAP7D1", "gene": "MAP7D1", "edge_id": "TSC22D1::MAP7D1"}],
  "evidence_packet": {
    "model_card": {"display_name": "specialist model A"},
    "perturbation": "TSC22D1",
    "genes": [
      {
        "gene_display": "MAP7D1",
        "sfm_call": "no_effect",
        "sfm_log2fc": 0.04,
        "sfm_confidence": 0.52,
        "sfm_confidence_source": "magnitude_proxy_not_calibrated"
      }
    ]
  }
}
```

`raw_assay_stats_shown` is a leakage-aware positive-control cue condition. It
adds measured DE statistics only in that condition:

```json
{
  "gene_display": "MAP7D1",
  "sfm_call": "no_effect",
  "sfm_log2fc": 0.04,
  "assay_stats": {
    "source": "heldout_measured_de_positive_control",
    "raw_log2FC": 0.02,
    "raw_se": 0.07,
    "raw_q": 0.89,
    "n_trt": 258,
    "n_cntrl": 6921,
    "leakage_note": "measured assay statistics; positive-control cue only"
  }
}
```

Do not include measured assay stats in default SFM trust prompts. They are
answer-like evidence and should be analyzed separately from ordinary trust cues.

## Phase 1A Internal-Signal Cue Packets

Phase 1A keeps the same action enum and scorer, but adds controlled
scFoundation internal-signal cue conditions:

- `no_internal_signal`
- `scfoundation_internal_signal_shown`
- `shuffled_internal_signal_shown`

The prompt still receives only `evidence_packet`. Top-level fields such as
`scoring_key`, `metadata`, `packet_id`, and `cue_condition` are not rendered into
the prompt by `make-requests`.

When visible, the internal signal is packet-level evidence:

```json
{
  "internal_signal_summary": {
    "source": "scFoundation_official_embedding_smoke",
    "adapter": "ScFoundationAdapter",
    "signal_type": "cell_embedding_summary",
    "signal_scope": "global_three_cell_smoke_subset_not_panel_specific",
    "calibration_status": "unverified_proxy_not_calibrated",
    "embedding_shape": [3, 3072],
    "embedding_dim": 3072,
    "embedding_finite_fraction": 1.0,
    "limitations": [
      "three_cell_smoke_only",
      "not_panel_specific_yet",
      "not_a_calibrated_uncertainty",
      "does_not_contain_hidden_labels"
    ]
  }
}
```

This is an internal-signal cue audit, not a full scFoundation perturbation
prediction benchmark. A stronger true-SFM-output claim requires the actionable
prediction itself to come from a true SFM adapter.

## Phase 1B Edge-Level Internal-Signal Cue

Phase 1B moves the internal signal from packet/panel level to gene/edge level.
The proposed model-visible field is:

```json
{
  "genes": [
    {
      "gene_display": "MAP7D1",
      "sfm_call": "effect",
      "sfm_log2fc": 0.73,
      "edge_internal_signal_summary": {
        "source": "scFoundation_neighbor_edge_support",
        "signal_scope": "readout_gene_specific",
        "neighbor_count": 20,
        "same_readout_gene_neighbor_count": 20,
        "neighbor_embedding_distance": {
          "mean": 1.2,
          "min": 0.4,
          "max": 2.8
        },
        "neighbor_sfm_call_agreement_rate": 0.65,
        "neighbor_sfm_call_disagreement_rate": 0.35,
        "neighbor_baseline_disagreement_rate": 0.35,
        "calibration_status": "unverified_proxy_not_calibrated",
        "limitations": [
          "not_a_calibrated_uncertainty",
          "does_not_contain_hidden_labels",
          "neighbor_similarity_may_not_equal_error_risk"
        ]
      }
    }
  ]
}
```

This field must not contain held-out truth, correctness flags, target-edge raw
assay statistics, reward, or scoring keys. The first planned route is
`scfoundation_neighbor_edge_support`, which uses scFoundation embedding
neighbors plus same-readout-gene non-truth summaries. It remains a design route
until a leakage-safe edge-signal artifact is generated and scored.

The Phase 1B pre-LLM diagnostic treats
`neighbor_sfm_call_disagreement_rate` as the primary real edge-neighbor score
and compares it against random same-readout-gene and shuffled readout-gene
controls. Passing this diagnostic only means the cue is eligible for a small
LLM pilot; it does not prove faithful scFoundation interpretation.

The current Phase 1B pilot packet conditions are:

- `no_internal_signal`
- `scfoundation_edge_neighbor_signal_shown`
- `random_same_gene_neighbor_signal_shown`
- `shuffled_readout_gene_neighbor_signal_shown`

For the three signal-visible conditions, the signal is rendered per gene as
`edge_internal_signal_summary`. The random and shuffled controls preserve the
same model-visible schema so any LLM behavior change can be compared against
matched reliability-looking evidence.

## Episode JSONL

Episodes are model decisions over a cue packet.

```json
{
  "packet_id": "TSC22D1::confidence_shown",
  "model": "claude-x",
  "provider": "openai_responses",
  "cue_condition": "confidence_shown",
  "actions": {"MAP7D1": {"action": "trust_sfm", "rationale": "..."}},
  "self_reported_cues": ["confidence"],
  "raw_output": "{...}"
}
```

If a provider returns malformed JSON, keep the episode and record `parse_error`.
Missing gene actions are scored as `defer`, which makes format failures visible
instead of silently dropping them.

## Score JSON

Panel-level score rows include both rates and raw counts. The summary block uses
micro gene-weighted metrics as the primary aggregate and keeps macro-panel
metrics under `macro_panel_*` keys.

Primary score fields:

- `accuracy`: gene-weighted correctness rate in summaries; per-panel correctness rate in rows.
- `assays_per_gene`: verification action rate.
- `net_reward`: `correct - lambda * assays - defer_penalty * defers`.
- `net_reward_per_gene`: gene-normalized net reward.
- `sfm_wrong_rate`: fraction of genes where the specialist model call is wrong.
- `trust_error_rate`: fraction of genes where the action trusts a wrong SFM call.
- `verify_precision`: verified wrong-SFM genes divided by verified genes.
- `verify_recall`: verified wrong-SFM genes divided by all wrong-SFM genes.
- `default_baseline_rate`: fraction of genes using the cheap baseline action.
- `default_observed_additive_rate`: fraction of genes defaulting to an observed-additive baseline.
- `default_no_change_rate`: fraction of genes defaulting to a no-change fallback baseline.
- `default_error_rate`: fraction of genes defaulting to an incorrect baseline.
- `defer_rate`: fraction of genes with `defer`.
- `coverage_rate`: fraction of genes with a non-defer action.

Current Phase 0 default reward uses `defer_penalty = 0.0`, so defer is zero
correctness and zero cost. Future environment experiments may set a nonzero
defer penalty while retaining the same schema.

## Environment Trajectory JSONL

Trajectory records wrap the existing Phase 0 episode into an environment-shaped
record for later tool-use or training datasets.

```json
{
  "trajectory_id": "TSC22D1::confidence_shown::policy::signal_gated_verify",
  "packet_id": "TSC22D1::confidence_shown",
  "panel_id": "TSC22D1",
  "cue_condition": "confidence_shown",
  "model": "policy::signal_gated_verify",
  "observation": {
    "packet_id": "TSC22D1::confidence_shown",
    "panel_id": "TSC22D1",
    "cue_condition": "confidence_shown",
    "available_actions": ["trust_sfm", "verify_assay", "default_baseline", "defer"],
    "evidence_packet": {}
  },
  "tool_calls": [
    {
      "step": 0,
      "tool_name": "estimate_assay_cost",
      "inputs": {},
      "outputs": {"verify_assay_cost": 1.0, "lambda": 0.5},
      "metadata": {}
    }
  ],
  "actions": {"MAP7D1": {"action": "trust_sfm", "rationale": "..."}},
  "score": {},
  "reward": 20.5,
  "reward_per_gene": 0.68,
  "metadata": {"policy_name": "signal_gated_verify"}
}
```

`observation` and `tool_calls` must not expose held-out truth or correctness
labels. Hidden truth is used only after final actions are submitted, inside
`score` and reward fields.

Completed LLM episodes can be converted to the same trajectory format. In that
case, `metadata` preserves fields such as `provider`, `self_reported_cues`,
`parse_error`, `provider_error`, and token `usage` when present. `raw_output` is
excluded by default and should only be included for provider-debugging datasets.

## Trajectory Feature Row JSONL

Feature rows are derived from trajectory `observation` fields only. They are
intended for router baselines and must not use held-out truth, correctness
labels, score fields, or reward fields as model-visible inputs.

Example fields:

- `n_genes`
- `cue_condition`
- `model_name_visible`
- `anonymized_gene_rate`
- `sfm_effect_rate`
- `sfm_abs_log2fc_mean`
- `sfm_abs_log2fc_max`
- `confidence_present_rate`
- `confidence_mean`
- `baseline_present_rate`
- `baseline_call_disagreement_rate`
- `baseline_abs_diff_mean`
- `baseline_observed_additive_rate`
- `reliability_present_rate`
- `reliability_high_risk_rate`
- `assay_stats_present_rate`
- `internal_signal_present`
- `internal_signal_embedding_dim`
- `internal_signal_finite_fraction`
- `internal_signal_scope`
- `feature_signature`

The feature row may also include `model`, `reward`, `reward_per_gene`, and
`score` for offline analysis, but those are label-side fields and should not be
used as router inputs.

## Preference Pair JSONL

Preference pairs compare two or more trajectories for the same `packet_id`.
The trajectory with the higher reward is marked `chosen`; the lower reward one
is marked `rejected`.

```json
{
  "pair_id": "TSC22D1::confidence_shown::claude-a>>claude-b::0",
  "packet_id": "TSC22D1::confidence_shown",
  "panel_id": "TSC22D1",
  "cue_condition": "confidence_shown",
  "preference_source": "trajectory_reward",
  "reward_delta": 1.5,
  "same_observation": true,
  "reward_config": {"lambda": 0.5, "defer_penalty": 0.0, "tool_call_cost": 0.0},
  "observation": {},
  "chosen": {
    "trajectory_id": "...",
    "model": "claude-a",
    "actions": {},
    "reward": 20.0,
    "score": {},
    "metadata": {}
  },
  "rejected": {
    "trajectory_id": "...",
    "model": "claude-b",
    "actions": {},
    "reward": 18.5,
    "score": {},
    "metadata": {}
  }
}
```

The `observation` is the model-visible input. `score`, `reward`, and
`reward_delta` are label-side fields derived after scoring and should not be
included inside the prompt when using these pairs for training.

## Adapter Contract JSON

Adapter contracts define how model-specific outputs enter the standardized
trust-cue benchmark. They are preflight artifacts, not model results.

Phase 1 scFoundation preflight artifact:

```text
experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_contract.json
```

Required contract fields:

- `name`: adapter name, for example `ScFoundationAdapter`.
- `phase`: project phase, for example `phase1`.
- `compute_target`: where the model should run; Phase 1 SFM compute should use
  Cayuga or Expanse.
- `required_inputs`: model-specific input artifacts needed before inference.
- `standardized_outputs`: JSONL artifacts the adapter must produce.
- `evidence_fields`: model-visible fields allowed in cue packets.
- `internal_signal_fields`: representation or internal-signal summaries exposed
  through standardized evidence packets.
- `hidden_fields`: fields that must not enter model-visible prompts.
- `preflight_checks`: checks that must pass before any Phase 1 claim.
- `claim_boundary`: explicit non-overclaim language for the adapter state.

For Phase 1, the key schema requirement is that a true single-cell SFM can be
wrapped into the same action/reward interface:

```text
specialist model output -> adapter -> standardized evidence packet -> LLM action -> score/reward
```

The evaluator should not need to know whether the evidence packet came from
GEARS, scFoundation, Geneformer/scGPT, Evo2, or AlphaGenome. Model-specific
logic belongs inside adapters. Trust-routing logic belongs in the shared
evaluator, scorer, cue attribution, and robustness layers.
