"""Assemble Phase 2 calibration-gate records from Boltz-2 outputs + truth.

Joins, per target:
  - Boltz-2 confidence JSON (`confidence_<id>_model_0.json`; real fields confirmed
    on Boltz 2.2.1: complex_plddt, ptm, iptm, protein_iptm, complex_iplddt,
    confidence_score, ...),
  - a cheap template/homology baseline correctness flag,
  - held-out experimental truth (lDDT for monomers / DockQ for complexes),
into the records schema consumed by `phase2_calibration_gate`:

  {"target_id","regime","mean_plddt","iptm"|null,"template_baseline_correct",
   "truth":{"correct","quality"}}

Leakage note: these records ARE the gate's scorer-side input, so they legitimately
carry `truth`. The leakage rule (truth never visible) applies to the downstream
LLM-facing cue packets, NOT to this file.

No LLM calls. Pure stdlib.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from typing import Any, Optional


def to_plddt_0_100(value: Optional[float]) -> Optional[float]:
    """Normalize Boltz complex_plddt to a 0-100 scale (the gate's convention).

    Boltz reports complex_plddt in [0, 1]; AlphaFold-style pLDDT is [0, 100]. We
    scale [0,1] up by 100 and leave an already-0-100 value untouched, so the
    records are correct regardless of which scale the installed Boltz emits.
    (Confirm against the smoke's real confidence JSON.)
    """
    if value is None:
        return None
    v = float(value)
    return round(v * 100.0, 4) if v <= 1.5 else round(v, 4)


def parse_boltz_confidence(path: str) -> dict[str, Any]:
    with open(path) as handle:
        data = json.load(handle)
    keys = ["confidence_score", "complex_plddt", "complex_iplddt", "ptm", "iptm", "protein_iptm"]
    return {k: data.get(k) for k in keys}


def find_confidence_json(boltz_out_dir: str, target_id: str) -> Optional[str]:
    """Boltz writes <out>/boltz_results_*/predictions/<id>/confidence_<id>_model_0.json."""
    hits = glob.glob(
        os.path.join(boltz_out_dir, "**", f"confidence_{target_id}_model_0.json"),
        recursive=True,
    )
    return sorted(hits)[0] if hits else None


def assemble_record(
    *,
    target_id: str,
    regime: str,
    confidence: dict[str, Any],
    truth_correct: bool,
    truth_quality: float,
    template_baseline_correct: bool,
) -> dict[str, Any]:
    if regime not in ("monomer", "complex"):
        raise ValueError(f"regime must be monomer|complex, got {regime!r}")
    # interface confidence is only meaningful for complexes
    iptm = None
    if regime == "complex":
        iptm = confidence.get("iptm")
        if iptm is None:
            iptm = confidence.get("protein_iptm")
        iptm = None if iptm is None else round(float(iptm), 4)
    return {
        "target_id": target_id,
        "regime": regime,
        "mean_plddt": to_plddt_0_100(confidence.get("complex_plddt")),
        "iptm": iptm,
        "template_baseline_correct": bool(template_baseline_correct),
        "truth": {"correct": bool(truth_correct), "quality": round(float(truth_quality), 6)},
    }


def assemble_records(
    *,
    boltz_out_dir: str,
    targets: list[dict[str, Any]],
    truth_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (records, skipped_target_ids). A target is skipped (with a reason)
    if its confidence JSON or truth entry is missing -- never silently dropped."""
    records: list[dict[str, Any]] = []
    skipped: list[str] = []
    for target in targets:
        tid = str(target["target_id"])
        conf_path = find_confidence_json(boltz_out_dir, tid)
        truth = truth_by_id.get(tid)
        if conf_path is None:
            skipped.append(f"{tid}: no confidence JSON under {boltz_out_dir}")
            continue
        if truth is None:
            skipped.append(f"{tid}: no truth entry")
            continue
        records.append(assemble_record(
            target_id=tid,
            regime=str(target["regime"]),
            confidence=parse_boltz_confidence(conf_path),
            truth_correct=truth["correct"],
            truth_quality=truth["quality"],
            template_baseline_correct=truth.get("template_baseline_correct", False),
        ))
    return records, skipped


def _read_jsonl(path: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in open(path) if line.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boltz-out-dir", required=True, help="Boltz predict --out_dir")
    ap.add_argument("--targets", required=True, help="JSONL: {target_id, regime}")
    ap.add_argument("--truth", required=True,
                    help="JSONL: {target_id, correct, quality, template_baseline_correct}")
    ap.add_argument("--out", required=True, help="output records JSONL for the calibration gate")
    args = ap.parse_args()

    targets = _read_jsonl(args.targets)
    truth_by_id = {str(r["target_id"]): r for r in _read_jsonl(args.truth)}
    records, skipped = assemble_records(
        boltz_out_dir=args.boltz_out_dir, targets=targets, truth_by_id=truth_by_id,
    )
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as handle:
        for rec in records:
            handle.write(json.dumps(rec, sort_keys=True) + "\n")
    print(f"wrote {len(records)} records to {args.out}")
    if skipped:
        print(f"skipped {len(skipped)}:")
        for reason in skipped:
            print(f"  - {reason}")


if __name__ == "__main__":
    main()
