#!/usr/bin/env python3
"""Phase 4a (2)+(3): seeded + adversarial. Arms: calibrated_interface (C1), raw_plddt,
inverted (C4 manipulation), and NEW 'corrupted_plus_raw' — a CORRUPTED (inverted) reliability
card shown ALONGSIDE the truthful raw ipTM/pLDDT, to test whether the LLM detects the
inconsistency and recovers (H4.4 via adversarial miscalibration) where the blind gate fails.
3 models x 3 seeds (Opus 1). N=57. Held-out calibration. Durable output."""
import sys, json, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "experiments/trust_cue_attribution")
from phase2_calibration_gate import confidence_to_risk
from phase2_calibrated_gate import isotonic_calibrator
from phase2_interface_pilot import phase2_interface_packet, render_prompt, risk_bucket, _recommended_action, ACTIONS
from llm_runner import anthropic_messages_call, openai_responses_call, parse_episode_response
DUR = "<WORK_DIR>"; CUT = 0.49
v1 = [o for o in json.load(open("experiments/trust_cue_attribution/results/phase2_dockq_validation/dockq_validation.json")) if "dockq" in o]
cal = isotonic_calibrator([confidence_to_risk({"regime": "complex", "mean_plddt": o["mean_plddt"], "iptm": o["iptm"]}) for o in v1], [1 if o["dockq"] < CUT else 0 for o in v1])
test = [json.loads(l) for l in open(DUR + "/cxbig_records.jsonl") if l.strip()]
risk = {r["target_id"]: cal(confidence_to_risk(r)) for r in test}
json.dump(risk, open(DUR + "/heldout_risk.json", "w"))

def corrupted_packet(rec, hr):
    corr = round(1.0 - hr, 4)  # adversarially inverted calibrated risk, shown WITH the truthful raw signal
    ev = {"model_card": {"display_name": "specialist structure model A", "adapter": "hidden"},
          "task": f"predicted 3D structure of a protein complex ({int(rec.get('n_protein_chains', 2))} chains)",
          "regime": rec["regime"],
          "confidence": {"mean_plddt_0_100": rec.get("mean_plddt"), "iptm": rec.get("iptm")},
          "reliability_interface": {"estimated_wrong_risk": corr, "risk_bucket": risk_bucket(corr),
                                    "recommended_action": _recommended_action(corr), "calibration_status": "leave_one_out_isotonic_calibrated"}}
    return {"packet_id": f"{rec['target_id']}::corrupted_plus_raw", "target_id": rec["target_id"], "cue_condition": "corrupted_plus_raw",
            "available_actions": ACTIONS, "scoring_key": {"target_id": rec["target_id"], "regime": rec["regime"]}, "evidence_packet": ev, "metadata": {"phase": "phase4a_adversarial"}}

STD = ["calibrated_interface_shown", "raw_plddt_shown", "inverted_reliability_interface_control"]
packets = []
for r in test:
    hr = risk[r["target_id"]]
    for arm in STD: packets.append(phase2_interface_packet(r, arm, hr))
    packets.append(corrupted_packet(r, hr))
requests = [{"packet_id": p["packet_id"], "target_id": p["target_id"], "cue_condition": p["cue_condition"], "prompt": render_prompt(p)} for p in packets]
print(f"{len(test)} x 4 arms = {len(requests)} req/seed", flush=True)
RUNS = [("claude-sonnet-4-6", "anthropic_messages", [0.5, 0.8, 1.0]), ("gpt-4.1", "openai_responses", [0.5, 0.8, 1.0]), ("claude-opus-4-8", "anthropic_messages", [None])]
def call(model, prov, temp, req):
    try:
        if prov == "anthropic_messages":
            kw = {} if temp is None else {"temperature": temp}
            raw = anthropic_messages_call(req["prompt"], model, max_output_tokens=1024, **kw)
        else:
            raw = openai_responses_call(req["prompt"], model, max_output_tokens=1024, temperature=temp)
        return parse_episode_response(req, raw, model, prov)
    except Exception as e:
        return {"packet_id": req["packet_id"], "cue_condition": req["cue_condition"], "actions": {}, "provider_error": str(e)[:120]}
for model, prov, temps in RUNS:
    for si, temp in enumerate(temps):
        t0 = time.time()
        with ThreadPoolExecutor(max_workers=6) as ex:
            eps = list(ex.map(lambda req: call(model, prov, temp, req), requests))
        for e in eps: e["seed"] = si
        open(f"{DUR}/p4s_{model}_seed{si}.jsonl", "w").write("\n".join(json.dumps(e) for e in eps) + "\n")
        print(f"{model} seed{si}: {len(eps)} eps, {sum(1 for e in eps if 'provider_error' in e)} err, {time.time()-t0:.0f}s", flush=True)
print("P4S_DONE", flush=True)
