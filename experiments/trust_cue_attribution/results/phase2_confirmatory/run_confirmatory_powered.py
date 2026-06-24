#!/usr/bin/env python3
"""Powered pre-registered confirmatory pilot on the N=57 hard-complex set. Same design as
run_confirmatory.py (held-out calibration, 6 arms, 3 seeds, lambda-sweep, Holm) but on the
larger set and THREADED (concurrency 6) to keep wall-clock reasonable."""
import sys, json, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "experiments/trust_cue_attribution")
from phase2_calibration_gate import confidence_to_risk
from phase2_calibrated_gate import isotonic_calibrator
from phase2_interface_pilot import phase2_interface_packet, render_prompt, PHASE2_INTERFACE_CUES, ACTIONS
from llm_runner import anthropic_messages_call, openai_responses_call, parse_episode_response

CUT = 0.49
v1 = [o for o in json.load(open("experiments/trust_cue_attribution/results/phase2_dockq_validation/dockq_validation.json")) if "dockq" in o]
cal_x = [confidence_to_risk({"regime": "complex", "mean_plddt": o["mean_plddt"], "iptm": o["iptm"]}) for o in v1]
cal_y = [1 if o["dockq"] < CUT else 0 for o in v1]
calibrator = isotonic_calibrator(cal_x, cal_y)
print(f"held-out calibrator on {len(v1)} v1 complexes", flush=True)

test = [json.loads(l) for l in open("<WORK_DIR>/cxbig_records.jsonl") if l.strip()]
test = [r for r in test if r["truth"]["quality"] is not None]

def competing_cue_packet(rec):
    ev = {"model_card": {"display_name": "AlphaFold3-Multimer v3 (peer-reviewed, wet-lab validated)",
                         "track_record": "independently benchmarked; community treats its complexes as reliable"},
          "task": f"predicted 3D structure of a protein complex ({int(rec.get('n_protein_chains',2))} chains)",
          "regime": rec["regime"], "confidence": {"mean_plddt_0_100": rec.get("mean_plddt"), "iptm": rec.get("iptm")}}
    return {"packet_id": f"{rec['target_id']}::competing_cue", "target_id": rec["target_id"], "cue_condition": "competing_cue",
            "available_actions": ACTIONS, "scoring_key": {"target_id": rec["target_id"], "regime": rec["regime"]},
            "evidence_packet": ev, "metadata": {"phase": "phase2_confirmatory_big"}}

packets = []
for rec in test:
    hr = calibrator(confidence_to_risk(rec))
    for arm in PHASE2_INTERFACE_CUES:
        packets.append(phase2_interface_packet(rec, arm, hr))
    packets.append(competing_cue_packet(rec))
requests = [{"packet_id": p["packet_id"], "target_id": p["target_id"], "cue_condition": p["cue_condition"], "prompt": render_prompt(p)} for p in packets]
print(f"{len(test)} complexes x 6 arms = {len(requests)} requests/seed", flush=True)

RUNS = [("claude-sonnet-4-6", "anthropic_messages", [0.5, 0.8, 1.0]),
        ("gpt-4.1", "openai_responses", [0.5, 0.8, 1.0]),
        ("claude-opus-4-8", "anthropic_messages", [None])]

def call_one(model, provider, temp, req):
    try:
        if provider == "anthropic_messages":
            kw = {} if temp is None else {"temperature": temp}
            raw = anthropic_messages_call(req["prompt"], model, max_output_tokens=1024, **kw)
        else:
            raw = openai_responses_call(req["prompt"], model, max_output_tokens=1024, temperature=temp)
        return parse_episode_response(req, raw, model, provider)
    except Exception as e:
        return {"packet_id": req["packet_id"], "cue_condition": req["cue_condition"], "actions": {}, "provider_error": str(e)[:150]}

for model, provider, temps in RUNS:
    for si, temp in enumerate(temps):
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=6) as ex:
            eps = list(ex.map(lambda req: call_one(model, provider, temp, req), requests))
        for ep in eps: ep["seed"] = si
        open(f"<WORK_DIR>/cbig_{model}_seed{si}.jsonl", "w").write("\n".join(json.dumps(e) for e in eps) + "\n")
        errs = sum(1 for e in eps if "provider_error" in e or "parse_error" in e)
        print(f"{model} seed{si} (temp={temp}): {len(eps)} eps, {errs} errors, {time.time()-t0:.0f}s", flush=True)
print("CONF_BIG_DONE", flush=True)
