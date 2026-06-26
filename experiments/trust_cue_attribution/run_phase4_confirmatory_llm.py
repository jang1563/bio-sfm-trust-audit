#!/usr/bin/env python3
"""Phase 4 confirmatory LLM runner. Free-form LLM trust routing over the N>=120 substrate,
across the clean card + the pre-registered corruption shapes (invert / shift / noise). The
corrupted cards are shown ALONGSIDE the truthful raw ipTM/pLDDT (so the LLM could cross-check).
Corruption values are generated once (seeded), saved, and reused by the blind gate in analysis.

Arms:
  calibrated_interface_shown             clean calibrated card (free-form / constrained / conformal source)
  inverted_reliability_interface_control inverted card only (manipulation, H4.2)
  corrupted_invert_plus_raw              inverted card + raw signal (adversarial, H4.4)
  corrupted_shift_plus_raw               under-reported risk (r-0.3) + raw signal
  corrupted_noise_plus_raw               decalibrated risk (r+N(0,0.3)) + raw signal

3 models x 3 seeds. Held-out isotonic calibration fit on the v1 DockQ-validation complexes.
Usage: python run_phase4_confirmatory_llm.py --records <records.jsonl> --out-dir <dir>
"""
import argparse, json, os, random, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))  # experiments/trust_cue_attribution/
sys.path.insert(0, HERE)
from phase2_calibration_gate import confidence_to_risk
from phase2_calibrated_gate import isotonic_calibrator
from phase2_interface_pilot import (phase2_interface_packet, render_prompt, risk_bucket,
                                    _recommended_action, ACTIONS)
from llm_runner import anthropic_messages_call, openai_responses_call, parse_episode_response

CUT = 0.49
SHAPES = {"invert": "corrupted_invert_plus_raw", "shift": "corrupted_shift_plus_raw",
          "noise": "corrupted_noise_plus_raw"}


def corrupt_value(r, shape, rng):
    if shape == "invert":
        return round(1.0 - r, 4)
    if shape == "shift":
        return round(min(1.0, max(0.0, r - 0.3)), 4)      # under-report risk (over-confidence injection)
    if shape == "noise":
        return round(min(1.0, max(0.0, r + rng.gauss(0, 0.3))), 4)
    raise ValueError(shape)


def corrupted_packet(rec, corr_risk, arm):
    ev = {"model_card": {"display_name": "specialist structure model A", "adapter": "hidden"},
          "task": f"predicted 3D structure of a protein complex ({int(rec.get('n_protein_chains', rec.get('n_chains', 2)))} chains)",
          "regime": rec["regime"],
          "confidence": {"mean_plddt_0_100": rec.get("mean_plddt"), "iptm": rec.get("iptm")},
          "reliability_interface": {"estimated_wrong_risk": corr_risk, "risk_bucket": risk_bucket(corr_risk),
                                    "recommended_action": _recommended_action(corr_risk),
                                    "calibration_status": "leave_one_out_isotonic_calibrated"}}
    return {"packet_id": f"{rec['target_id']}::{arm}", "target_id": rec["target_id"], "cue_condition": arm,
            "available_actions": ACTIONS, "scoring_key": {"target_id": rec["target_id"], "regime": rec["regime"]},
            "evidence_packet": ev, "metadata": {"phase": "phase4_confirmatory"}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    v1 = [o for o in json.load(open(os.path.join(HERE,
          "results/phase2_dockq_validation/dockq_validation.json"))) if "dockq" in o]
    cal = isotonic_calibrator(
        [confidence_to_risk({"regime": "complex", "mean_plddt": o["mean_plddt"], "iptm": o["iptm"]}) for o in v1],
        [1 if o["dockq"] < CUT else 0 for o in v1])
    test = [json.loads(l) for l in open(args.records) if l.strip()]
    risk = {r["target_id"]: cal(confidence_to_risk(r)) for r in test}
    json.dump(risk, open(os.path.join(args.out_dir, "heldout_risk.json"), "w"))

    rng = random.Random(13)
    corrupted = {sh: {r["target_id"]: corrupt_value(risk[r["target_id"]], sh, rng) for r in test} for sh in SHAPES}
    json.dump(corrupted, open(os.path.join(args.out_dir, "corrupted_risk.json"), "w"))

    packets = []
    for r in test:
        hr = risk[r["target_id"]]
        packets.append(phase2_interface_packet(r, "calibrated_interface_shown", hr))
        packets.append(phase2_interface_packet(r, "inverted_reliability_interface_control", hr))
        for sh, arm in SHAPES.items():
            packets.append(corrupted_packet(r, corrupted[sh][r["target_id"]], arm))
    requests = [{"packet_id": p["packet_id"], "target_id": p["target_id"],
                 "cue_condition": p["cue_condition"], "prompt": render_prompt(p)} for p in packets]
    print(f"{len(test)} targets x {2+len(SHAPES)} arms = {len(requests)} req/seed", flush=True)

    RUNS = [("claude-sonnet-4-6", "anthropic_messages", [0.5, 0.8, 1.0]),
            ("gpt-4.1", "openai_responses", [0.5, 0.8, 1.0]),
            ("claude-opus-4-8", "anthropic_messages", [None])]

    def call(model, prov, temp, req):
        try:
            if prov == "anthropic_messages":
                kw = {} if temp is None else {"temperature": temp}
                raw = anthropic_messages_call(req["prompt"], model, max_output_tokens=1024, **kw)
            else:
                raw = openai_responses_call(req["prompt"], model, max_output_tokens=1024, temperature=temp)
            return parse_episode_response(req, raw, model, prov)
        except Exception as e:
            return {"packet_id": req["packet_id"], "cue_condition": req["cue_condition"],
                    "actions": {}, "provider_error": str(e)[:120]}

    for model, prov, temps in RUNS:
        for si, temp in enumerate(temps):
            t0 = time.time()
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                eps = list(ex.map(lambda req: call(model, prov, temp, req), requests))
            for e in eps:
                e["seed"] = si
            open(os.path.join(args.out_dir, f"p4c_{model}_seed{si}.jsonl"), "w").write(
                "\n".join(json.dumps(e) for e in eps) + "\n")
            print(f"{model} seed{si}: {len(eps)} eps, {sum(1 for e in eps if 'provider_error' in e)} err, {time.time()-t0:.0f}s", flush=True)
    print("P4C_DONE", flush=True)


if __name__ == "__main__":
    main()
