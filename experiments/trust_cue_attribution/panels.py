"""Build extended perturbation panels from local GEARS prediction + experimental-truth CSVs."""

from __future__ import annotations

import csv
import math
import random
import re
from dataclasses import dataclass
from typing import Iterable

DELTA = 0.25
RAW_COLS = ("raw_log2FC", "raw_se", "raw_q", "n_trt", "n_cntrl")


@dataclass(frozen=True)
class PanelConfig:
    n: int = 30
    min_wrong: int = 5
    min_correct: int = 5
    seed: int = 13
    delta: float = DELTA
    adapter: str = "GEARSAdapter"
    model_name: str = "GEARS"
    require_additive: bool = False


def _float(value: str | float | int | None, default: float = math.nan) -> float:
    if value in (None, ""):
        return default
    return float(value)


def _int(value: str | float | int | None, default: int = 0) -> int:
    if value in (None, ""):
        return default
    return int(float(value))


def _call_from_lfc(value: float, delta: float) -> str:
    return "effect" if abs(value) >= delta else "no_effect"


def _stratum(fm_correct: bool, fm_call: str, real_call: str) -> str:
    if fm_correct:
        return "correct_effect" if real_call == "effect" else "correct_noeffect"
    return "wrong_FN" if fm_call == "no_effect" else "wrong_FP"


def _split_perturbation(perturbation: str) -> list[str]:
    return [p for p in re.split(r"[+_]", perturbation) if p and p.lower() != "ctrl"]


def load_rows(path: str) -> list[dict]:
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def load_single_effects(marginal_csv: str, delta: float = DELTA) -> dict[tuple[str, str], float]:
    """Load measured single-perturbation effects keyed by (target, response gene)."""
    out: dict[tuple[str, str], float] = {}
    for row in load_rows(marginal_csv):
        if row.get("kind") != "single":
            continue
        if not math.isclose(_float(row.get("delta")), delta):
            continue
        out[(row["target"], row["response_id"])] = _float(row.get("log2FC"))
    return out


def additive_log2fc(perturbation: str, gene: str, single_effects: dict[tuple[str, str], float]) -> float | None:
    parts = _split_perturbation(perturbation)
    if len(parts) <= 1:
        return None
    values = [single_effects.get((p, gene)) for p in parts]
    if any(v is None for v in values):
        return None
    return float(sum(v for v in values if v is not None))


def normalize_substrate_row(row: dict, single_effects: dict[tuple[str, str], float] | None, cfg: PanelConfig) -> dict:
    perturbation = row["perturbation"]
    gene = row["gene"]
    fm_log2fc = _float(row.get("fm_log2FC", row.get("gears_log2FC")))
    fm_call = row.get("fm_call", row.get("gears_call")) or _call_from_lfc(fm_log2fc, cfg.delta)
    real_label = row.get("real_label") or ("POSITIVE" if row.get("real_call") == "effect" else "TESTED_NEGATIVE")
    real_call = row.get("real_call") or ("effect" if real_label == "POSITIVE" else "no_effect")
    fm_correct = fm_call == real_call
    add_lfc = additive_log2fc(perturbation, gene, single_effects or {})
    if add_lfc is None:
        baseline_source = "no_change"
        baseline_lfc = 0.0
    else:
        baseline_source = "observed_additive"
        baseline_lfc = add_lfc
    baseline_call = _call_from_lfc(baseline_lfc, cfg.delta)
    call_disagreement = baseline_call != fm_call
    abs_diff = abs(fm_log2fc - baseline_lfc)
    risk_label = "high_sfm_error_risk" if call_disagreement or abs_diff >= cfg.delta else "low_sfm_error_risk"
    raw = {k: _float(row.get(k)) for k in RAW_COLS[:3]}
    raw.update({k: _int(row.get(k)) for k in RAW_COLS[3:]})
    return {
        "edge_id": f"{perturbation}::{gene}",
        "gene": gene,
        "fm": {
            "model_name": cfg.model_name,
            "log2fc": fm_log2fc,
            "call": fm_call,
            "correct": fm_correct,
        },
        "truth": {
            "real_call": real_call,
            "real_label": real_label,
        },
        "baseline_signal": {
            "source": baseline_source,
            "log2fc": baseline_lfc,
            "call": baseline_call,
            "correct": baseline_call == real_call,
            "abs_fm_minus_baseline": abs_diff,
            "call_disagreement": call_disagreement,
        },
        "reliability_signal": {
            "source": "baseline_disagreement",
            "score": abs_diff + (0.5 if call_disagreement else 0.0),
            "label": risk_label,
        },
        "raw": raw,
        "stratum": _stratum(fm_correct, fm_call, real_call),
        "regime": row.get("regime", "unknown"),
    }


def build_panels_from_rows(rows: Iterable[dict], single_effects: dict[tuple[str, str], float] | None = None,
                           cfg: PanelConfig | None = None) -> list[dict]:
    cfg = cfg or PanelConfig()
    seen = set()
    edges_by_pert: dict[str, list[dict]] = {}
    for row in rows:
        key = (row.get("perturbation"), row.get("gene"))
        if key in seen:
            continue
        seen.add(key)
        if row.get("real_label") not in (None, "", "POSITIVE", "TESTED_NEGATIVE") and row.get("real_call") in (None, ""):
            continue
        edge = normalize_substrate_row(row, single_effects, cfg)
        if cfg.require_additive and edge["baseline_signal"]["source"] != "observed_additive":
            continue
        edges_by_pert.setdefault(row["perturbation"], []).append(edge)

    rng = random.Random(cfg.seed)
    panels: list[dict] = []
    for perturbation in sorted(edges_by_pert):
        edges = edges_by_pert[perturbation]
        wrong = [e for e in edges if not e["fm"]["correct"]]
        correct = [e for e in edges if e["fm"]["correct"]]
        if len(wrong) < cfg.min_wrong or len(correct) < cfg.min_correct:
            continue
        rng.shuffle(wrong)
        rng.shuffle(correct)
        n_wrong = min(len(wrong), cfg.n // 2)
        chosen = wrong[:n_wrong] + correct[: max(0, cfg.n - n_wrong)]
        rng.shuffle(chosen)
        panels.append({
            "panel_id": perturbation,
            "perturbation": perturbation,
            "adapter": cfg.adapter,
            "n_panel": len(chosen),
            "n_wrong": sum(1 for e in chosen if not e["fm"]["correct"]),
            "edges": chosen,
        })
    return panels


def build_panels(substrate_csv: str, marginal_csv: str | None = None, cfg: PanelConfig | None = None) -> list[dict]:
    cfg = cfg or PanelConfig()
    single_effects = load_single_effects(marginal_csv, cfg.delta) if marginal_csv else None
    return build_panels_from_rows(load_rows(substrate_csv), single_effects, cfg)
