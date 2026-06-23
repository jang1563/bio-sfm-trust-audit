#!/usr/bin/env python3
"""CLI for the trust-cue attribution v0 harness."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import sys

from adapters import adapter_contracts, get_adapter_contract, write_adapter_contract
from baselines import run_baselines
from analysis import (
    cue_attribution_regression,
    explanation_faithfulness_gap,
    gene_level_rows,
    paired_cue_effects,
    summarize_episodes,
)
from cues import generate_cue_packets
from environment import make_episode_trajectories, make_policy_trajectories, summarize_trajectories
from episodes import make_policy_episode_records, make_request_records, score_episode_records
from io_utils import read_jsonl, write_jsonl
from llm_runner import iter_llm_episodes
from panels import PanelConfig, build_panels
from pilot_selection import DEFAULT_MAIN_CUES, filter_requests, pilot_manifest, select_stratified_panels, write_manifest
from preferences import make_preference_pairs, summarize_preference_pairs
from routers import evaluate_model_router
from features import summarize_feature_rows, trajectory_feature_rows
from freeze import build_phase0a_freeze, build_phase0b_freeze
from phase1_env import write_scfoundation_inference_env_report
from phase1_inventory import write_scfoundation_input_inventory
from phase1_probe import write_scfoundation_feasibility
from phase1_scfoundation_smoke import run_scfoundation_smoke
from phase1a_panel_signals import run_phase1a_panel_scfoundation_signals
from phase1a_review import write_phase1a_review
from phase1a_signal_granularity import write_phase1a_signal_granularity
from phase1a_signal_packets import write_phase1a_signal_packets
from phase1a_signal_validity import (
    selected_panels_from_manifest,
    write_phase1a_signal_validity,
)
from phase1b_edge_signal_design import write_phase1b_edge_signal_design
from phase1b_neighbor_signals import (
    run_phase1b_embedding_pool,
    write_phase1b_neighbor_signal_diagnostic,
)
from phase1b_review import write_phase1b_review
from phase1b_signal_packets import write_phase1b_signal_packets
from phase1c_reliability_interface import (
    generate_phase1c_interface_packets,
    phase1c_interface_manifest,
    write_phase1c_design,
    write_phase1c_offline_gate,
)
from phase1c_specialist_metric_check import run as run_specialist_metric_check
from phase2_calibration_gate import write_phase2_calibration_gate
from robustness import build_phase0b_robustness


def _cmd_build_panels(args: argparse.Namespace) -> int:
    panels = build_panels(
        args.substrate,
        marginal_csv=args.marginal,
        cfg=PanelConfig(
            n=args.n,
            min_wrong=args.min_wrong,
            min_correct=args.min_correct,
            seed=args.seed,
            require_additive=args.require_additive,
        ),
    )
    write_jsonl(panels, args.out)
    print(f"wrote {len(panels)} panels to {args.out}")
    return 0


def _cmd_cue_packets(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    packets = generate_cue_packets(panels)
    write_jsonl(packets, args.out)
    print(f"wrote {len(packets)} cue packets to {args.out}")
    return 0


def _cmd_baselines(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    res = run_baselines(panels, seed=args.seed)
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0


def _cmd_make_requests(args: argparse.Namespace) -> int:
    packets = read_jsonl(args.packets)
    template = open(args.template).read()
    records = make_request_records(packets, template, model=args.model)
    write_jsonl(records, args.out)
    print(f"wrote {len(records)} request records to {args.out}")
    return 0


def _cmd_filter_requests(args: argparse.Namespace) -> int:
    requests = read_jsonl(args.requests)
    cues = args.cues.split(",") if args.cues else DEFAULT_MAIN_CUES
    panel_ids = sorted({row["panel_id"] for row in requests})
    records = filter_requests(requests, panel_ids, cues)
    write_jsonl(records, args.out)
    counts = Counter(row.get("cue_condition") for row in records)
    summary = {
        "source": args.requests,
        "out": args.out,
        "n_input_requests": len(requests),
        "n_requests": len(records),
        "n_panels": len({row["panel_id"] for row in records}),
        "cue_conditions": cues,
        "cue_counts": dict(sorted(counts.items())),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def _cmd_score_episodes(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    packets = read_jsonl(args.packets)
    episodes = read_jsonl(args.episodes)
    result = score_episode_records(panels, packets, episodes, lam=args.lam, defer_penalty=args.defer_penalty)
    if args.out:
        with open(args.out, "w") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"wrote episode scores to {args.out}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _cmd_simulate_episodes(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    packets = read_jsonl(args.packets)
    episodes = make_policy_episode_records(panels, packets, args.policy)
    write_jsonl(episodes, args.out)
    print(f"wrote {len(episodes)} synthetic episodes to {args.out}")
    return 0


def _cmd_simulate_trajectories(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    packets = read_jsonl(args.packets)
    trajectories = make_policy_trajectories(
        panels,
        packets,
        args.policy,
        lam=args.lam,
        defer_penalty=args.defer_penalty,
        tool_call_cost=args.tool_call_cost,
    )
    write_jsonl(trajectories, args.out)
    print(f"wrote {len(trajectories)} environment trajectories to {args.out}")
    return 0


def _cmd_episodes_to_trajectories(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    packets = read_jsonl(args.packets)
    episodes = read_jsonl(args.episodes)
    trajectories = make_episode_trajectories(
        panels,
        packets,
        episodes,
        lam=args.lam,
        defer_penalty=args.defer_penalty,
        tool_call_cost=args.tool_call_cost,
        include_raw_output=args.include_raw_output,
    )
    write_jsonl(trajectories, args.out)
    print(f"wrote {len(trajectories)} LLM episode trajectories to {args.out}")
    return 0


def _cmd_summarize_trajectories(args: argparse.Namespace) -> int:
    trajectories = read_jsonl(args.trajectories)
    result = summarize_trajectories(trajectories)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"wrote trajectory summary to {args.out}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _cmd_trajectory_features(args: argparse.Namespace) -> int:
    trajectories = []
    for path in args.trajectories:
        trajectories.extend(read_jsonl(path))
    rows = trajectory_feature_rows(trajectories)
    write_jsonl(rows, args.out)
    print(f"wrote {len(rows)} trajectory feature rows to {args.out}")
    if args.summary_out:
        os.makedirs(os.path.dirname(args.summary_out) or ".", exist_ok=True)
        with open(args.summary_out, "w") as handle:
            json.dump(summarize_feature_rows(rows), handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"wrote trajectory feature summary to {args.summary_out}")
    return 0


def _cmd_trajectory_preferences(args: argparse.Namespace) -> int:
    trajectories = []
    for path in args.trajectories:
        trajectories.extend(read_jsonl(path))
    pairs = make_preference_pairs(
        trajectories,
        min_reward_delta=args.min_reward_delta,
        include_ties=args.include_ties,
    )
    write_jsonl(pairs, args.out)
    print(f"wrote {len(pairs)} trajectory preference pairs to {args.out}")
    if args.summary_out:
        os.makedirs(os.path.dirname(args.summary_out) or ".", exist_ok=True)
        with open(args.summary_out, "w") as handle:
            json.dump(summarize_preference_pairs(pairs), handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"wrote trajectory preference summary to {args.summary_out}")
    return 0


def _cmd_evaluate_router(args: argparse.Namespace) -> int:
    trajectories = []
    for path in args.trajectories:
        trajectories.extend(read_jsonl(path))
    result = evaluate_model_router(
        trajectories,
        feature_field=args.feature_field,
        group_field=args.group_field,
    )
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"wrote router evaluation to {args.out}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _cmd_run_llm_episodes(args: argparse.Namespace) -> int:
    requests = read_jsonl(args.requests)
    if args.offset:
        requests = requests[args.offset:]
    done = set()
    if args.resume and os.path.exists(args.out):
        done = {row["packet_id"] for row in read_jsonl(args.out) if "packet_id" in row}
        requests = [row for row in requests if row.get("packet_id") not in done]

    mode = "a" if args.resume and os.path.exists(args.out) else "w"
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    count = 0
    with open(args.out, mode) as handle:
        for episode in iter_llm_episodes(
            requests,
            provider=args.provider,
            model=args.model,
            limit=args.limit,
            delay=args.delay,
            strict=args.strict,
            continue_on_error=args.continue_on_error,
            timeout=args.timeout,
            max_output_tokens=args.max_output_tokens,
            temperature=args.temperature,
        ):
            handle.write(json.dumps(episode, sort_keys=True) + "\n")
            handle.flush()
            count += 1
            if args.progress_every and count % args.progress_every == 0:
                print(f"progress: wrote {count} episodes; latest packet_id={episode.get('packet_id')}", flush=True)
    skipped = f"; skipped {len(done)} existing episodes" if done else ""
    print(f"wrote {count} LLM episodes to {args.out}{skipped}")
    return 0


def _cmd_analyze_episodes(args: argparse.Namespace) -> int:
    episodes = read_jsonl(args.episodes)
    result = summarize_episodes(episodes)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"wrote episode analysis to {args.out}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _cmd_paired_cue_effects(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    packets = read_jsonl(args.packets)
    episodes = read_jsonl(args.episodes)
    rows = gene_level_rows(panels, packets, episodes, lam=args.lam, defer_penalty=args.defer_penalty)
    result = paired_cue_effects(rows, baseline_cue=args.baseline_cue)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"wrote paired cue effects to {args.out}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _cmd_cue_attribution(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    packets = read_jsonl(args.packets)
    episodes = read_jsonl(args.episodes)
    rows = gene_level_rows(panels, packets, episodes, lam=args.lam)
    result = cue_attribution_regression(rows, baseline_cue=args.baseline_cue)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"wrote cue attribution to {args.out}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _cmd_explanation_faithfulness(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    packets = read_jsonl(args.packets)
    episodes = read_jsonl(args.episodes)
    rows = gene_level_rows(panels, packets, episodes, lam=args.lam)
    result = explanation_faithfulness_gap(episodes, rows, baseline_cue=args.baseline_cue)
    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"wrote explanation faithfulness to {args.out}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _cmd_select_pilot_requests(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    requests = read_jsonl(args.requests)
    cues = args.cues.split(",") if args.cues else DEFAULT_MAIN_CUES
    panel_ids, selected = select_stratified_panels(panels, n_panels=args.n_panels, seed=args.seed)
    subset = filter_requests(requests, panel_ids, cues)
    write_jsonl(subset, args.out)
    if args.manifest:
        write_manifest(pilot_manifest(selected, cues, subset), args.manifest)
    print(f"wrote {len(subset)} pilot requests from {len(panel_ids)} panels to {args.out}")
    if args.manifest:
        print(f"wrote pilot manifest to {args.manifest}")
    return 0


def _cmd_freeze_phase0a(args: argparse.Namespace) -> int:
    result = build_phase0a_freeze(
        input_dir=args.input_dir,
        out_dir=args.out_dir,
        strict_counts=not args.allow_count_mismatch,
    )
    print(f"wrote Phase 0A manifest to {os.path.join(args.out_dir, 'manifest.json')}")
    print(f"wrote Phase 0A summary to {os.path.join(args.out_dir, 'summary.json')}")
    print(json.dumps(result["summary"]["sanity_checks"], indent=2, sort_keys=True))
    return 0


def _cmd_freeze_phase0b(args: argparse.Namespace) -> int:
    result = build_phase0b_freeze(
        input_dir=args.input_dir,
        out_dir=args.out_dir,
        strict_counts=not args.allow_count_mismatch,
    )
    print(f"wrote Phase 0B manifest to {os.path.join(args.out_dir, 'manifest.json')}")
    print(f"wrote Phase 0B summary to {os.path.join(args.out_dir, 'summary.json')}")
    print(json.dumps(result["summary"]["sanity_checks"], indent=2, sort_keys=True))
    return 0


def _cmd_phase0b_robustness(args: argparse.Namespace) -> int:
    result = build_phase0b_robustness(
        input_dir=args.input_dir,
        out=args.out,
        n_boot=args.n_boot,
        seed=args.seed,
        lam=args.lam,
        alpha=args.alpha,
    )
    if args.out:
        print(f"wrote Phase 0B robustness summary to {args.out}")
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def _cmd_adapter_contract(args: argparse.Namespace) -> int:
    if args.adapter == "all":
        payload = adapter_contracts()
        if args.out:
            os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
            with open(args.out, "w") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
            print(f"wrote adapter contracts to {args.out}")
        else:
            print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    payload = write_adapter_contract(args.adapter, args.out) if args.out else get_adapter_contract(args.adapter).describe()
    if args.out:
        print(f"wrote {args.adapter} contract to {args.out}")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _cmd_phase1_preflight(args: argparse.Namespace) -> int:
    payload = write_adapter_contract("ScFoundationAdapter", args.out)
    print(f"wrote Phase 1 scFoundation preflight contract to {args.out}")
    print(json.dumps({
        "adapter": payload["name"],
        "status": payload["status"],
        "compute_target": payload["compute_target"],
        "required_preflight_checks": payload["preflight_checks"],
        "claim_boundary": payload["claim_boundary"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1_feasibility(args: argparse.Namespace) -> int:
    report = write_scfoundation_feasibility(
        args.out,
        scfoundation_dir=args.scfoundation_dir,
        checkpoint=args.checkpoint,
        input_data=args.input_data,
        gene_index=args.gene_index,
        output_dir=args.output_dir,
    )
    print(f"wrote Phase 1 scFoundation feasibility report to {args.out}")
    print(json.dumps({
        "adapter": report["adapter"],
        "status": report["status"],
        "missing_required": [
            row["label"]
            for row in report["path_checks"]
            if row["required"] and not row["ready"]
        ],
        "claim_boundary": report["claim_boundary"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1_input_inventory(args: argparse.Namespace) -> int:
    report = write_scfoundation_input_inventory(
        args.out,
        input_data=args.input_data,
        gene_index=args.gene_index,
        min_overlap=args.min_overlap,
        sample_gene_count=args.sample_gene_count,
    )
    print(f"wrote Phase 1 scFoundation input inventory to {args.out}")
    print(json.dumps({
        "adapter": report["adapter"],
        "status": report["status"],
        "input_gene_count": report["gene_overlap"]["input_gene_count"],
        "vocabulary_gene_count": report["gene_overlap"]["vocabulary_gene_count"],
        "overlap_count": report["gene_overlap"]["overlap_count"],
        "claim_boundary": report["claim_boundary"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1_inference_env(args: argparse.Namespace) -> int:
    report = write_scfoundation_inference_env_report(
        args.out,
        scfoundation_dir=args.scfoundation_dir,
        checkpoint=args.checkpoint,
        require_cuda=not args.allow_no_cuda,
        check_scfoundation_import=not args.skip_scfoundation_import,
    )
    print(f"wrote Phase 1 scFoundation inference environment report to {args.out}")
    print(json.dumps({
        "adapter": report["adapter"],
        "status": report["status"],
        "python": report["python"]["executable"],
        "cuda_available": report["torch"].get("cuda_available"),
        "cuda_device_count": report["torch"].get("cuda_device_count"),
        "scfoundation_import_ok": report["scfoundation_import"].get("ok"),
        "claim_boundary": report["claim_boundary"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1_scfoundation_smoke(args: argparse.Namespace) -> int:
    report = run_scfoundation_smoke(
        scfoundation_dir=args.scfoundation_dir,
        input_data=args.input_data,
        out_dir=args.out_dir,
        report_out=args.report_out,
        n_cells=args.n_cells,
        task_name=args.task_name,
        pre_normalized=args.pre_normalized,
        tgthighres=args.tgthighres,
        timeout=args.timeout,
    )
    print(f"wrote Phase 1 scFoundation smoke report to {args.report_out}")
    print(json.dumps({
        "adapter": report["adapter"],
        "status": report["status"],
        "embedding_shape": report.get("embedding_summary", {}).get("shape"),
        "claim_boundary": report["claim_boundary"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1a_signal_packets(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    manifest = write_phase1a_signal_packets(
        panels=panels,
        smoke_report=args.scfoundation_smoke_report,
        panel_signal_report=args.panel_signal_report,
        out=args.out,
        manifest_out=args.manifest_out,
        n_panels=args.n_panels,
        seed=args.seed,
    )
    print(f"wrote Phase 1A signal packets to {args.out}")
    if args.manifest_out:
        print(f"wrote Phase 1A signal packet manifest to {args.manifest_out}")
    print(json.dumps({
        "status": manifest["status"],
        "n_panels": manifest["n_panels"],
        "n_packets": manifest["n_packets"],
        "cue_counts": manifest["cue_counts"],
        "claim_boundary": manifest["claim_boundary"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1a_panel_signals(args: argparse.Namespace) -> int:
    report = run_phase1a_panel_scfoundation_signals(
        scfoundation_dir=args.scfoundation_dir,
        input_data=args.input_data,
        phase1a_manifest=args.phase1a_manifest,
        out_dir=args.out_dir,
        report_out=args.report_out,
        max_cells_per_panel=args.max_cells_per_panel,
        max_control_cells=args.max_control_cells,
        perturbation_col=args.perturbation_col,
        control_label=args.control_label,
        use_layer=args.use_layer,
        task_name=args.task_name,
        pre_normalized=args.pre_normalized,
        tgthighres=args.tgthighres,
        seed=args.seed,
        timeout=args.timeout,
    )
    print(f"wrote Phase 1A panel-specific scFoundation signal report to {args.report_out}")
    print(json.dumps({
        "adapter": report["adapter"],
        "status": report["status"],
        "subset_shape": report.get("subset", {}).get("subset_shape"),
        "embedding_shape": report.get("embedding_summary", {}).get("shape"),
        "panel_count": report.get("panel_signals", {}).get("panel_count"),
        "claim_boundary": report["claim_boundary"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1a_review(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    packets = read_jsonl(args.packets)
    episodes = read_jsonl(args.episodes)
    with open(args.panel_signal_report) as handle:
        panel_signal_report = json.load(handle)
    review = write_phase1a_review(
        panels=panels,
        packets=packets,
        episodes=episodes,
        panel_signal_report=panel_signal_report,
        out=args.out,
        lam=args.lam,
        baseline_cue=args.baseline_cue,
    )
    print(f"wrote Phase 1A signal pilot review to {args.out}")
    print(json.dumps({
        "status": review["status"],
        "episodes": review["scope"]["episodes"],
        "recommendation": review["recommendation"],
        "specificity": review["specificity"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1a_signal_validity(args: argparse.Namespace) -> int:
    with open(args.manifest) as handle:
        manifest = json.load(handle)
    with open(args.panel_signal_report) as handle:
        panel_signal_report = json.load(handle)
    report = write_phase1a_signal_validity(
        selected_panels=selected_panels_from_manifest(manifest),
        panel_signal_report=panel_signal_report,
        out=args.out,
    )
    print(f"wrote Phase 1A signal validity report to {args.out}")
    print(json.dumps({
        "status": report["status"],
        "matched_panels": report["scope"]["matched_panels"],
        "decision": report["decision"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1a_signal_granularity(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    with open(args.manifest) as handle:
        manifest = json.load(handle)
    with open(args.panel_signal_report) as handle:
        panel_signal_report = json.load(handle)
    report = write_phase1a_signal_granularity(
        panels=panels,
        manifest=manifest,
        panel_signal_report=panel_signal_report,
        out=args.out,
    )
    print(f"wrote Phase 1A signal granularity report to {args.out}")
    print(json.dumps({
        "status": report["status"],
        "edge_rows": report["scope"]["edge_rows"],
        "mixed_panel_fraction": report["decision"]["mixed_panel_fraction"],
        "decision": report["decision"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1b_edge_signal_design(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    with open(args.manifest) as handle:
        manifest = json.load(handle)
    report = write_phase1b_edge_signal_design(
        panels=panels,
        manifest=manifest,
        out=args.out,
    )
    print(f"wrote Phase 1B edge-signal design report to {args.out}")
    print(json.dumps({
        "status": report["status"],
        "selected_edges": report["scope"]["selected_edges"],
        "recommended_route": report["recommended_route"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1b_embedding_pool(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    report = run_phase1b_embedding_pool(
        scfoundation_dir=args.scfoundation_dir,
        input_data=args.input_data,
        panels=panels,
        out_dir=args.out_dir,
        pool_out=args.pool_out,
        report_out=args.report_out,
        max_cells_per_panel=args.max_cells_per_panel,
        max_control_cells=args.max_control_cells,
        perturbation_col=args.perturbation_col,
        control_label=args.control_label,
        use_layer=args.use_layer,
        task_name=args.task_name,
        pre_normalized=args.pre_normalized,
        tgthighres=args.tgthighres,
        seed=args.seed,
        timeout=args.timeout,
    )
    print(f"wrote Phase 1B scFoundation embedding pool report to {args.report_out}")
    print(json.dumps({
        "adapter": report["adapter"],
        "status": report["status"],
        "subset_shape": report.get("subset", {}).get("subset_shape"),
        "embedding_shape": report.get("embedding_summary", {}).get("shape"),
        "pool_summary": report.get("pool_summary"),
        "claim_boundary": report["claim_boundary"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1b_neighbor_signals(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    with open(args.manifest) as handle:
        manifest = json.load(handle)
    with open(args.embedding_pool) as handle:
        embedding_pool = json.load(handle)
    report = write_phase1b_neighbor_signal_diagnostic(
        panels=panels,
        manifest=manifest,
        embedding_pool=embedding_pool,
        out=args.out,
        k_neighbors=args.k_neighbors,
        seed=args.seed,
    )
    print(f"wrote Phase 1B edge-neighbor signal diagnostic to {args.out}")
    print(json.dumps({
        "status": report["status"],
        "scope": report["scope"],
        "decision": report["decision"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1b_signal_packets(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    cues = args.cues.split(",") if args.cues else None
    manifest = write_phase1b_signal_packets(
        panels=panels,
        neighbor_report=args.neighbor_report,
        out=args.out,
        manifest_out=args.manifest_out,
        cue_conditions=cues,
    )
    print(f"wrote Phase 1B signal packets to {args.out}")
    if args.manifest_out:
        print(f"wrote Phase 1B signal packet manifest to {args.manifest_out}")
    print(json.dumps({
        "status": manifest["status"],
        "n_panels": manifest["n_panels"],
        "n_packets": manifest["n_packets"],
        "cue_counts": manifest["cue_counts"],
        "model_visible_leakage_passed": manifest["model_visible_leakage_check"]["passed"],
        "claim_boundary": manifest["claim_boundary"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1b_review(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    packets = read_jsonl(args.packets)
    episodes = read_jsonl(args.episodes)
    with open(args.neighbor_report) as handle:
        neighbor_report = json.load(handle)
    review = write_phase1b_review(
        panels=panels,
        packets=packets,
        episodes=episodes,
        neighbor_report=neighbor_report,
        out=args.out,
        lam=args.lam,
        baseline_cue=args.baseline_cue,
    )
    print(f"wrote Phase 1B signal pilot review to {args.out}")
    print(json.dumps({
        "status": review["status"],
        "episodes": review["scope"]["episodes"],
        "recommendation": review["recommendation"],
        "specificity": review["specificity"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1c_offline_gate(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    with open(args.neighbor_report) as handle:
        neighbor_report = json.load(handle)
    with open(args.phase1b_summary) as handle:
        phase1b_summary = json.load(handle)
    design = write_phase1c_design(
        panels_path=args.panels,
        neighbor_report_path=args.neighbor_report,
        phase1b_summary_path=args.phase1b_summary,
        out=args.design_out,
    )
    gate = write_phase1c_offline_gate(
        panels=panels,
        neighbor_report=neighbor_report,
        phase1b_summary=phase1b_summary,
        out=args.out,
    )
    print(f"wrote Phase 1C reliability-interface design to {args.design_out}")
    print(f"wrote Phase 1C offline gate to {args.out}")
    print(json.dumps({
        "design_status": design["status"],
        "gate_status": gate["status"],
        "scope": gate["scope"],
        "decision": gate["decision"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1c_specialist_metric_check(args: argparse.Namespace) -> int:
    result = run_specialist_metric_check(args.panels, args.out)
    print(f"wrote Phase 1C specialist metric check to {args.out}")
    print(json.dumps({
        "verdict_short": result["verdict"]["short"],
        "phase1c_12_gears_minus_additive_auroc": result["verdict"].get("phase1c_12_gears_minus_additive_auroc"),
        "observed_additive_gears_minus_additive_auroc": result["verdict"].get("observed_additive_gears_minus_additive_auroc"),
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase2_calibration_gate(args: argparse.Namespace) -> int:
    records = read_jsonl(args.records)
    gate = write_phase2_calibration_gate(records, args.out, lam=args.lam)
    print(f"wrote Phase 2 calibration gate to {args.out}")
    print(json.dumps({
        "decision": gate["decision"],
        "scope": gate["scope"],
        "wrong_risk_auroc": gate["signal_validity"]["wrong_risk_auroc"],
        "margins": gate["margins"],
    }, indent=2, sort_keys=True))
    return 0


def _cmd_phase1c_interface_requests(args: argparse.Namespace) -> int:
    panels = read_jsonl(args.panels)
    with open(args.neighbor_report) as handle:
        neighbor_report = json.load(handle)
    with open(args.offline_gate) as handle:
        offline_gate = json.load(handle)
    cues = args.cues.split(",") if args.cues else None
    packets = generate_phase1c_interface_packets(
        panels,
        neighbor_report,
        offline_gate,
        cue_conditions=cues,
    )
    write_jsonl(packets, args.packets_out)
    template = open(args.template).read()
    requests = make_request_records(packets, template, model=args.model)
    write_jsonl(requests, args.requests_out)
    manifest = phase1c_interface_manifest(
        packets=packets,
        requests=requests,
        neighbor_report=args.neighbor_report,
        offline_gate=args.offline_gate,
        packet_out=args.packets_out,
        request_out=args.requests_out,
    )
    if args.manifest_out:
        os.makedirs(os.path.dirname(args.manifest_out) or ".", exist_ok=True)
        with open(args.manifest_out, "w") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(f"wrote Phase 1C interface request manifest to {args.manifest_out}")
    print(f"wrote Phase 1C interface packets to {args.packets_out}")
    print(f"wrote Phase 1C interface requests to {args.requests_out}")
    print(json.dumps({
        "status": manifest["status"],
        "n_panels": manifest["n_panels"],
        "n_packets": manifest["n_packets"],
        "n_requests": manifest["n_requests"],
        "cue_counts": manifest["cue_counts"],
        "model_visible_leakage_passed": manifest["model_visible_leakage_check"]["passed"],
        "claim_boundary": manifest["claim_boundary"],
    }, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(required=True)

    p = sub.add_parser("build-panels")
    p.add_argument("--substrate", required=True)
    p.add_argument("--marginal")
    p.add_argument("--out", required=True)
    p.add_argument("--n", type=int, default=30)
    p.add_argument("--min-wrong", type=int, default=5)
    p.add_argument("--min-correct", type=int, default=5)
    p.add_argument("--seed", type=int, default=13)
    p.add_argument("--require-additive", action="store_true",
                   help="keep only edges with observed-additive baseline coverage; useful for combo-only signal checks")
    p.set_defaults(func=_cmd_build_panels)

    p = sub.add_parser("cue-packets")
    p.add_argument("--panels", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=_cmd_cue_packets)

    p = sub.add_parser("baselines")
    p.add_argument("--panels", required=True)
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(func=_cmd_baselines)

    p = sub.add_parser("make-requests")
    p.add_argument("--packets", required=True)
    p.add_argument("--template", default="experiments/trust_cue_attribution/prompts/decision_prompt.md")
    p.add_argument("--model", default="unset")
    p.add_argument("--out", required=True)
    p.set_defaults(func=_cmd_make_requests)

    p = sub.add_parser("filter-requests")
    p.add_argument("--requests", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--cues",
                   help="comma-separated cue conditions; defaults to the six non-leakage main cues")
    p.set_defaults(func=_cmd_filter_requests)

    p = sub.add_parser("score-episodes")
    p.add_argument("--panels", required=True)
    p.add_argument("--packets", required=True)
    p.add_argument("--episodes", required=True)
    p.add_argument("--lam", type=float, default=0.5)
    p.add_argument("--defer-penalty", type=float, default=0.0)
    p.add_argument("--out")
    p.set_defaults(func=_cmd_score_episodes)

    p = sub.add_parser("simulate-episodes")
    p.add_argument("--panels", required=True)
    p.add_argument("--packets", required=True)
    p.add_argument("--policy", default="signal_gated_verify")
    p.add_argument("--out", required=True)
    p.set_defaults(func=_cmd_simulate_episodes)

    p = sub.add_parser("simulate-trajectories")
    p.add_argument("--panels", required=True)
    p.add_argument("--packets", required=True)
    p.add_argument("--policy", default="signal_gated_verify")
    p.add_argument("--lam", type=float, default=0.5)
    p.add_argument("--defer-penalty", type=float, default=0.0)
    p.add_argument("--tool-call-cost", type=float, default=0.0)
    p.add_argument("--out", required=True)
    p.set_defaults(func=_cmd_simulate_trajectories)

    p = sub.add_parser("episodes-to-trajectories")
    p.add_argument("--panels", required=True)
    p.add_argument("--packets", required=True)
    p.add_argument("--episodes", required=True)
    p.add_argument("--lam", type=float, default=0.5)
    p.add_argument("--defer-penalty", type=float, default=0.0)
    p.add_argument("--tool-call-cost", type=float, default=0.0)
    p.add_argument("--include-raw-output", action="store_true")
    p.add_argument("--out", required=True)
    p.set_defaults(func=_cmd_episodes_to_trajectories)

    p = sub.add_parser("summarize-trajectories")
    p.add_argument("--trajectories", required=True)
    p.add_argument("--out")
    p.set_defaults(func=_cmd_summarize_trajectories)

    p = sub.add_parser("trajectory-features")
    p.add_argument("--trajectories", nargs="+", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--summary-out")
    p.set_defaults(func=_cmd_trajectory_features)

    p = sub.add_parser("trajectory-preferences")
    p.add_argument("--trajectories", nargs="+", required=True)
    p.add_argument("--min-reward-delta", type=float, default=0.0)
    p.add_argument("--include-ties", action="store_true")
    p.add_argument("--out", required=True)
    p.add_argument("--summary-out")
    p.set_defaults(func=_cmd_trajectory_preferences)

    p = sub.add_parser("evaluate-router")
    p.add_argument("--trajectories", nargs="+", required=True)
    p.add_argument("--feature-field", default="cue_condition")
    p.add_argument("--group-field", default="panel_id")
    p.add_argument("--out")
    p.set_defaults(func=_cmd_evaluate_router)

    p = sub.add_parser("run-llm-episodes")
    p.add_argument("--requests", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--provider", choices=["mock_defer", "openai_responses", "anthropic_messages"], default="mock_defer")
    p.add_argument("--model", required=True)
    p.add_argument("--limit", type=int)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--delay", type=float, default=0.0)
    p.add_argument("--timeout", type=float, default=120.0)
    p.add_argument("--max-output-tokens", type=int, default=4096)
    p.add_argument("--temperature", type=float)
    p.add_argument("--resume", action="store_true",
                   help="append to an existing episode file and skip completed packet_id values")
    p.add_argument("--progress-every", type=int, default=1,
                   help="print progress after this many newly written episodes; use 0 to disable")
    p.add_argument("--strict", action="store_true",
                   help="fail if a provider response is not valid episode JSON")
    p.add_argument("--continue-on-error", action="store_true",
                   help="write an error episode instead of stopping on provider failures")
    p.set_defaults(func=_cmd_run_llm_episodes)

    p = sub.add_parser("analyze-episodes")
    p.add_argument("--episodes", required=True)
    p.add_argument("--out")
    p.set_defaults(func=_cmd_analyze_episodes)

    p = sub.add_parser("paired-cue-effects")
    p.add_argument("--panels", required=True)
    p.add_argument("--packets", required=True)
    p.add_argument("--episodes", required=True)
    p.add_argument("--lam", type=float, default=0.5)
    p.add_argument("--defer-penalty", type=float, default=0.0)
    p.add_argument("--baseline-cue", default="no_cue")
    p.add_argument("--out")
    p.set_defaults(func=_cmd_paired_cue_effects)

    p = sub.add_parser("cue-attribution")
    p.add_argument("--panels", required=True)
    p.add_argument("--packets", required=True)
    p.add_argument("--episodes", required=True)
    p.add_argument("--lam", type=float, default=0.5)
    p.add_argument("--baseline-cue", default="no_cue")
    p.add_argument("--out")
    p.set_defaults(func=_cmd_cue_attribution)

    p = sub.add_parser("explanation-faithfulness")
    p.add_argument("--panels", required=True)
    p.add_argument("--packets", required=True)
    p.add_argument("--episodes", required=True)
    p.add_argument("--lam", type=float, default=0.5)
    p.add_argument("--baseline-cue", default="no_cue")
    p.add_argument("--out")
    p.set_defaults(func=_cmd_explanation_faithfulness)

    p = sub.add_parser("select-pilot-requests")
    p.add_argument("--panels", required=True)
    p.add_argument("--requests", required=True)
    p.add_argument("--n-panels", type=int, default=12)
    p.add_argument("--seed", type=int, default=19)
    p.add_argument("--cues",
                   help="comma-separated cue conditions; defaults to the six non-leakage main cues")
    p.add_argument("--out", required=True)
    p.add_argument("--manifest")
    p.set_defaults(func=_cmd_select_pilot_requests)

    p = sub.add_parser("freeze-phase0a")
    p.add_argument("--input-dir", default="experiments/trust_cue_attribution/hpc_outputs/phase0_smoke")
    p.add_argument("--out-dir", default="experiments/trust_cue_attribution/results/phase0a_freeze")
    p.add_argument("--allow-count-mismatch", action="store_true",
                   help="write freeze artifacts even if Phase 0A count/cue/balance checks do not match the canonical pilot")
    p.set_defaults(func=_cmd_freeze_phase0a)

    p = sub.add_parser("freeze-phase0b")
    p.add_argument("--input-dir", default="experiments/trust_cue_attribution/hpc_outputs/phase0_smoke")
    p.add_argument("--out-dir", default="experiments/trust_cue_attribution/results/phase0b_freeze")
    p.add_argument("--allow-count-mismatch", action="store_true",
                   help="write freeze artifacts even if Phase 0B count/cue/integrity checks do not match the canonical full run")
    p.set_defaults(func=_cmd_freeze_phase0b)

    p = sub.add_parser("phase0b-robustness")
    p.add_argument("--input-dir", default="experiments/trust_cue_attribution/hpc_outputs/phase0_smoke")
    p.add_argument("--out", default="experiments/trust_cue_attribution/results/phase0b_robustness/summary.json")
    p.add_argument("--n-boot", type=int, default=1000)
    p.add_argument("--seed", type=int, default=13)
    p.add_argument("--lam", type=float, default=0.5)
    p.add_argument("--alpha", type=float, default=0.05)
    p.set_defaults(func=_cmd_phase0b_robustness)

    p = sub.add_parser("adapter-contract")
    p.add_argument("--adapter", default="all",
                   help="adapter name or 'all'")
    p.add_argument("--out")
    p.set_defaults(func=_cmd_adapter_contract)

    p = sub.add_parser("phase1-preflight")
    p.add_argument("--out", default="experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_contract.json")
    p.set_defaults(func=_cmd_phase1_preflight)

    p = sub.add_parser("phase1-feasibility")
    p.add_argument("--scfoundation-dir", default=os.environ.get("SCFOUNDATION_DIR"))
    p.add_argument("--checkpoint", default=os.environ.get("SCFOUNDATION_CHECKPOINT"))
    p.add_argument("--input-data", default=os.environ.get("PHASE1_INPUT_DATA"))
    p.add_argument("--gene-index", default=os.environ.get("SCFOUNDATION_GENE_INDEX"))
    p.add_argument("--output-dir", default=os.environ.get("PHASE1_OUTPUT_DIR"))
    p.add_argument("--out", default="experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_feasibility.json")
    p.set_defaults(func=_cmd_phase1_feasibility)

    p = sub.add_parser("phase1-input-inventory")
    p.add_argument("--input-data", default=os.environ.get("PHASE1_INPUT_DATA"), required=os.environ.get("PHASE1_INPUT_DATA") is None)
    p.add_argument("--gene-index", default=os.environ.get("SCFOUNDATION_GENE_INDEX"), required=os.environ.get("SCFOUNDATION_GENE_INDEX") is None)
    p.add_argument("--min-overlap", type=int, default=500)
    p.add_argument("--sample-gene-count", type=int, default=12)
    p.add_argument("--out", default="experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_input_inventory.json")
    p.set_defaults(func=_cmd_phase1_input_inventory)

    p = sub.add_parser("phase1-inference-env")
    p.add_argument("--scfoundation-dir", default=os.environ.get("SCFOUNDATION_DIR"))
    p.add_argument("--checkpoint", default=os.environ.get("SCFOUNDATION_CHECKPOINT"))
    p.add_argument("--allow-no-cuda", action="store_true",
                   help="do not require torch.cuda to be visible; useful for login-node diagnostics only")
    p.add_argument("--skip-scfoundation-import", action="store_true",
                   help="skip importing scFoundation model/load.py")
    p.add_argument("--out", default="experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_inference_env.json")
    p.set_defaults(func=_cmd_phase1_inference_env)

    p = sub.add_parser("phase1-scfoundation-smoke")
    p.add_argument("--scfoundation-dir", default=os.environ.get("SCFOUNDATION_DIR"), required=os.environ.get("SCFOUNDATION_DIR") is None)
    p.add_argument("--input-data", default=os.environ.get("PHASE1_INPUT_DATA"), required=os.environ.get("PHASE1_INPUT_DATA") is None)
    p.add_argument("--out-dir", default=os.environ.get("PHASE1_OUTPUT_DIR", "experiments/trust_cue_attribution/hpc_outputs/phase1_scfoundation_smoke"))
    p.add_argument("--report-out", default="experiments/trust_cue_attribution/hpc_outputs/phase1_preflight/scfoundation_smoke_report.json")
    p.add_argument("--n-cells", type=int, default=3)
    p.add_argument("--task-name", default="phase1_smoke")
    p.add_argument("--pre-normalized", choices=["F", "T", "A"], default="F")
    p.add_argument("--tgthighres", default="t4")
    p.add_argument("--timeout", type=int, default=1200)
    p.set_defaults(func=_cmd_phase1_scfoundation_smoke)

    p = sub.add_parser("phase1a-signal-packets")
    p.add_argument("--panels", required=True)
    p.add_argument("--scfoundation-smoke-report",
                   default="experiments/trust_cue_attribution/results/phase1_preflight/scfoundation_smoke_report.json")
    p.add_argument("--panel-signal-report",
                   help="optional Phase 1A panel-specific signal report; when provided, it replaces the global smoke summary")
    p.add_argument("--out", default="experiments/trust_cue_attribution/hpc_outputs/phase1a_signal_pilot/phase1a_signal_packets.jsonl")
    p.add_argument("--manifest-out", default="experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json")
    p.add_argument("--n-panels", type=int, default=12)
    p.add_argument("--seed", type=int, default=23)
    p.set_defaults(func=_cmd_phase1a_signal_packets)

    p = sub.add_parser("phase1a-panel-signals")
    p.add_argument("--scfoundation-dir", default=os.environ.get("SCFOUNDATION_DIR"), required=os.environ.get("SCFOUNDATION_DIR") is None)
    p.add_argument("--input-data", required=True)
    p.add_argument("--phase1a-manifest", default="experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json")
    p.add_argument("--out-dir", default=os.environ.get("PHASE1A_PANEL_SIGNAL_OUTPUT_DIR", "experiments/trust_cue_attribution/hpc_outputs/phase1a_panel_signals"))
    p.add_argument("--report-out", default="experiments/trust_cue_attribution/hpc_outputs/phase1a_panel_signals/panel_signal_report.json")
    p.add_argument("--max-cells-per-panel", type=int, default=16)
    p.add_argument("--max-control-cells", type=int, default=64)
    p.add_argument("--perturbation-col", default="perturbation_name")
    p.add_argument("--control-label", default="control")
    p.add_argument("--use-layer", default="counts")
    p.add_argument("--task-name", default="phase1a_panel_signal")
    p.add_argument("--pre-normalized", choices=["F", "T", "A"], default="F")
    p.add_argument("--tgthighres", default="t4")
    p.add_argument("--seed", type=int, default=37)
    p.add_argument("--timeout", type=int, default=3600)
    p.set_defaults(func=_cmd_phase1a_panel_signals)

    p = sub.add_parser("phase1a-review")
    p.add_argument("--panels", required=True)
    p.add_argument("--packets", required=True)
    p.add_argument("--episodes", required=True)
    p.add_argument("--panel-signal-report", required=True)
    p.add_argument("--lam", type=float, default=0.5)
    p.add_argument("--baseline-cue", default="no_internal_signal")
    p.add_argument("--out", default="experiments/trust_cue_attribution/results/phase1a_signal_pilot/review.json")
    p.set_defaults(func=_cmd_phase1a_review)

    p = sub.add_parser("phase1a-signal-validity")
    p.add_argument("--manifest", default="experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json")
    p.add_argument("--panel-signal-report", default="experiments/trust_cue_attribution/results/phase1a_panel_signals/panel_signal_report.json")
    p.add_argument("--out", default="experiments/trust_cue_attribution/results/phase1a_signal_pilot/signal_validity.json")
    p.set_defaults(func=_cmd_phase1a_signal_validity)

    p = sub.add_parser("phase1a-signal-granularity")
    p.add_argument("--panels", default="experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl")
    p.add_argument("--manifest", default="experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json")
    p.add_argument("--panel-signal-report", default="experiments/trust_cue_attribution/results/phase1a_panel_signals/panel_signal_report.json")
    p.add_argument("--out", default="experiments/trust_cue_attribution/results/phase1a_signal_pilot/signal_granularity.json")
    p.set_defaults(func=_cmd_phase1a_signal_granularity)

    p = sub.add_parser("phase1b-edge-signal-design")
    p.add_argument("--panels", default="experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl")
    p.add_argument("--manifest", default="experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json")
    p.add_argument("--out", default="experiments/trust_cue_attribution/results/phase1b_edge_signal_design/design.json")
    p.set_defaults(func=_cmd_phase1b_edge_signal_design)

    p = sub.add_parser("phase1b-embedding-pool")
    p.add_argument("--scfoundation-dir", default=os.environ.get("SCFOUNDATION_DIR"), required=os.environ.get("SCFOUNDATION_DIR") is None)
    p.add_argument("--input-data", required=True)
    p.add_argument("--panels", default="experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl")
    p.add_argument("--out-dir", default=os.environ.get("PHASE1B_OUTPUT_DIR", "experiments/trust_cue_attribution/hpc_outputs/phase1b_edge_neighbor"))
    p.add_argument("--pool-out", default="experiments/trust_cue_attribution/hpc_outputs/phase1b_edge_neighbor/embedding_pool.json")
    p.add_argument("--report-out", default="experiments/trust_cue_attribution/hpc_outputs/phase1b_edge_neighbor/embedding_pool_report.json")
    p.add_argument("--max-cells-per-panel", type=int, default=12)
    p.add_argument("--max-control-cells", type=int, default=128)
    p.add_argument("--perturbation-col", default="perturbation_name")
    p.add_argument("--control-label", default="control")
    p.add_argument("--use-layer", default="counts")
    p.add_argument("--task-name", default="phase1b_embedding_pool")
    p.add_argument("--pre-normalized", choices=["F", "T", "A"], default="F")
    p.add_argument("--tgthighres", default="t4")
    p.add_argument("--seed", type=int, default=41)
    p.add_argument("--timeout", type=int, default=7200)
    p.set_defaults(func=_cmd_phase1b_embedding_pool)

    p = sub.add_parser("phase1b-neighbor-signals")
    p.add_argument("--panels", default="experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl")
    p.add_argument("--manifest", default="experiments/trust_cue_attribution/results/phase1a_signal_pilot/manifest.json")
    p.add_argument("--embedding-pool", default="experiments/trust_cue_attribution/hpc_outputs/phase1b_edge_neighbor/embedding_pool.json")
    p.add_argument("--out", default="experiments/trust_cue_attribution/results/phase1b_edge_neighbor/neighbor_signal_report.json")
    p.add_argument("--k-neighbors", type=int, default=10)
    p.add_argument("--seed", type=int, default=41)
    p.set_defaults(func=_cmd_phase1b_neighbor_signals)

    p = sub.add_parser("phase1b-signal-packets")
    p.add_argument("--panels", default="experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl")
    p.add_argument("--neighbor-report", default="experiments/trust_cue_attribution/results/phase1b_edge_neighbor/neighbor_signal_report.json")
    p.add_argument("--out", default="experiments/trust_cue_attribution/hpc_outputs/phase1b_signal_pilot/phase1b_signal_packets.jsonl")
    p.add_argument("--manifest-out", default="experiments/trust_cue_attribution/results/phase1b_signal_pilot/manifest.json")
    p.add_argument("--cues",
                   help="comma-separated Phase 1B cue conditions; defaults to no signal, real edge neighbor, random same-gene, and shuffled readout-gene controls")
    p.set_defaults(func=_cmd_phase1b_signal_packets)

    p = sub.add_parser("phase1b-review")
    p.add_argument("--panels", default="experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl")
    p.add_argument("--packets", default="experiments/trust_cue_attribution/hpc_outputs/phase1b_signal_pilot/phase1b_signal_packets.jsonl")
    p.add_argument("--episodes", default="experiments/trust_cue_attribution/hpc_outputs/phase1b_signal_pilot/llm_claude-sonnet-4-6_phase1b_signal_pilot_episodes.jsonl")
    p.add_argument("--neighbor-report", default="experiments/trust_cue_attribution/results/phase1b_edge_neighbor/neighbor_signal_report.json")
    p.add_argument("--out", default="experiments/trust_cue_attribution/results/phase1b_signal_pilot/review.json")
    p.add_argument("--lam", type=float, default=0.5)
    p.add_argument("--baseline-cue", default="no_internal_signal")
    p.set_defaults(func=_cmd_phase1b_review)

    p = sub.add_parser("phase1c-offline-gate")
    p.add_argument("--panels", default="experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl")
    p.add_argument("--neighbor-report", default="experiments/trust_cue_attribution/results/phase1b_edge_neighbor/neighbor_signal_report.json")
    p.add_argument("--phase1b-summary", default="experiments/trust_cue_attribution/results/phase1b_signal_pilot/summary.json")
    p.add_argument("--design-out", default="experiments/trust_cue_attribution/results/phase1c_reliability_interface/design.json")
    p.add_argument("--out", default="experiments/trust_cue_attribution/results/phase1c_reliability_interface/offline_gate.json")
    p.set_defaults(func=_cmd_phase1c_offline_gate)

    p = sub.add_parser("phase1c-interface-requests")
    p.add_argument("--panels", default="experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl")
    p.add_argument("--neighbor-report", default="experiments/trust_cue_attribution/results/phase1b_edge_neighbor/neighbor_signal_report.json")
    p.add_argument("--offline-gate", default="experiments/trust_cue_attribution/results/phase1c_reliability_interface/offline_gate.json")
    p.add_argument("--template", default="experiments/trust_cue_attribution/prompts/decision_prompt.md")
    p.add_argument("--model", default="claude-sonnet-4-6")
    p.add_argument("--packets-out", default="experiments/trust_cue_attribution/hpc_outputs/phase1c_interface_pilot/phase1c_interface_packets.jsonl")
    p.add_argument("--requests-out", default="experiments/trust_cue_attribution/hpc_outputs/phase1c_interface_pilot/requests_phase1c_interface.jsonl")
    p.add_argument("--manifest-out", default="experiments/trust_cue_attribution/results/phase1c_reliability_interface/interface_request_manifest.json")
    p.add_argument("--cues",
                   help="comma-separated Phase 1C cue conditions; defaults to base, edge-neighbor, calibrated interface, and inverted-control interface")
    p.set_defaults(func=_cmd_phase1c_interface_requests)

    p = sub.add_parser("phase1c-specialist-metric-check")
    p.add_argument("--panels", default="experiments/trust_cue_attribution/hpc_outputs/phase0_smoke/panels_full.jsonl")
    p.add_argument("--out", default="experiments/trust_cue_attribution/results/phase1c_reliability_interface/specialist_metric_check.json")
    p.set_defaults(func=_cmd_phase1c_specialist_metric_check)

    p = sub.add_parser("phase2-calibration-gate")
    p.add_argument("--records", required=True)
    p.add_argument("--out", default="experiments/trust_cue_attribution/results/phase2_preflight/calibration_gate.json")
    p.add_argument("--lam", type=float, default=0.5)
    p.set_defaults(func=_cmd_phase2_calibration_gate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
