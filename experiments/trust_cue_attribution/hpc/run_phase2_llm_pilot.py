"""Run the Phase 2 LLM interface pilot (Sonnet) over the prepared request set.

Uses the shared llm_runner (anthropic_messages, stdlib urllib). Resumable: skips
packet_ids already present in the output. Run from the project root with
ANTHROPIC_API_KEY in the environment (source ~/.api_keys).
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # experiments/trust_cue_attribution

from llm_runner import run_llm_episodes  # noqa: E402

REQ = "experiments/trust_cue_attribution/hpc_outputs/phase2_interface_pilot/requests_phase2_interface.jsonl"
MODEL = os.environ.get("PHASE2_MODEL", "claude-sonnet-4-6")
_TAG = "opus" if "opus" in MODEL else ("sonnet" if "sonnet" in MODEL else MODEL.replace("/", "_"))
OUT = os.environ.get(
    "PHASE2_OUT",
    f"experiments/trust_cue_attribution/hpc_outputs/phase2_interface_pilot/episodes_{_TAG}.jsonl",
)


def main() -> None:
    requests = [json.loads(line) for line in open(REQ) if line.strip()]
    done = set()
    if os.path.exists(OUT):
        done = {json.loads(line).get("packet_id") for line in open(OUT) if line.strip()}
    todo = [r for r in requests if r["packet_id"] not in done]
    print(f"requests={len(requests)} already_done={len(done)} todo={len(todo)} model={MODEL}")

    episodes = run_llm_episodes(
        todo, provider="anthropic_messages", model=MODEL,
        continue_on_error=True, delay=0.2,
    )
    with open(OUT, "a") as fh:
        for ep in episodes:
            fh.write(json.dumps(ep) + "\n")

    alleps = [json.loads(line) for line in open(OUT) if line.strip()]
    parse_err = sum(1 for e in alleps if "parse_error" in e)
    prov_err = sum(1 for e in alleps if "provider_error" in e)
    print(f"PHASE2_LLM_PILOT total_episodes={len(alleps)} parse_errors={parse_err} provider_errors={prov_err}")
    print("TRUST_CUE_PHASE2_LLM_PILOT_OK")


if __name__ == "__main__":
    main()
