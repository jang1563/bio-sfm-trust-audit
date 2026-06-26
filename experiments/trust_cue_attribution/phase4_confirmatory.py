"""Phase 4 confirmatory scorer — enforcement mechanisms over a fallible specialist.

Implements, as POST-HOC policies over (records, held-out calibrated risk, free-form
LLM episodes), the three pre-registered enforcement mechanisms plus baselines, and
the pre-registered analysis (paired target-bootstrap CIs, Holm-Bonferroni).

Reward per target: net = correct - lambda * assays, with
  trust_sfm        correct iff DockQ >= CUT;          0 assays
  verify_assay     always correct;                    1 assay
  default_baseline correct iff template_baseline_correct; 0 assays
  defer            not correct;                        0 assays
(see phase2_score_episodes.outcome — reused for the LLM arms).

Mechanisms (all read the *calibrated* held-out risk = P(wrong); none train on test):
  calibrated_gate    deterministic: verify iff risk > lambda, else trust          [pre-reg #1]
  constrained_llm    free-form LLM action, masked to the gate-allowed set         [pre-reg #2]
                     (risk > lambda forbids trust_sfm -> projected to verify_assay;
                      mask the final action only, never the reasoning -- CRANE caveat)
  conformal_gate     conformal risk control: trust iff risk <= tau_hat, where     [pre-reg #3]
                     tau_hat is the largest threshold whose calibration false-accept
                     bound (n*Rhat+1)/(n+1) <= alpha (monotone loss; CRC, A&B 2024)
Baselines: trust_all, verify_all, default_all.

Corruption shapes (applied to the risk the LLM sees AND a blind gate's input):
  invert  risk -> 1-risk ;  shift  risk -> clip(risk+delta) ;  noise risk -> clip(risk+N(0,sigma))
The blind gate recomputes from corrupted risk (no LLM); the LLM arm needs cards
regenerated + a fresh run (handled by the runner, not here).
"""
from __future__ import annotations
import argparse, glob, json, os, random, sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from phase2_score_episodes import episode_action, outcome  # noqa: E402

CUT = 0.49          # DockQ >= 0.49 ("medium" CAPRI) == trust is correct
ACTIONS = ("trust_sfm", "verify_assay", "default_baseline", "defer")


# ---------- enforcement mechanisms (per-target, given risk r in [0,1]) ----------

def gate_action(r: float, lam: float) -> str:
    """Deterministic calibrated gate: verify iff risk exceeds the price, else trust."""
    return "verify_assay" if r > lam else "trust_sfm"


def allowed_set(r: float, lam: float) -> set:
    """Gate-allowed actions. Above the price the unsafe over-trust action is masked out."""
    return {"verify_assay", "default_baseline", "defer"} if r > lam else set(ACTIONS)


def constrained_action(llm_act: str, r: float, lam: float) -> str:
    """Mask the LLM's final action to the gate-allowed set (project to gate action if forbidden)."""
    return llm_act if llm_act in allowed_set(r, lam) else gate_action(r, lam)


def crc_threshold(cal: list[tuple[float, bool]], alpha: float) -> float:
    """Conformal risk control: largest tau s.t. the calibration false-accept upper bound
    (n*Rhat(tau)+1)/(n+1) <= alpha, where Rhat(tau)=mean 1[risk<=tau and wrong]. Monotone
    non-decreasing in tau, so we scan candidate thresholds ascending and keep the last valid one.
    cal = [(risk, wrong_bool)]. Returns tau_hat (trust iff risk <= tau_hat)."""
    n = len(cal)
    if n == 0:
        return 0.0
    cand = sorted({0.0} | {r for r, _ in cal} | {1.0})
    tau_hat = 0.0
    for tau in cand:
        rhat = sum(1 for r, wrong in cal if r <= tau and wrong) / n
        if (n * rhat + 1) / (n + 1) <= alpha:
            tau_hat = tau
        else:
            break
    return tau_hat


# ---------- corruption shapes ----------

def corrupt(r: float, shape: str, *, delta: float = 0.3, sigma: float = 0.3, rng=None) -> float:
    if shape == "none":
        return r
    if shape == "invert":
        return 1.0 - r
    if shape == "shift":
        return min(1.0, max(0.0, r + delta))
    if shape == "noise":
        return min(1.0, max(0.0, r + (rng.gauss(0, sigma) if rng else 0.0)))
    raise ValueError(shape)


# ---------- net reward helpers ----------

def net_of_action(act: str, target_correct: bool, template_correct: bool, lam: float) -> float:
    c, a = outcome(act, target_correct, template_correct, lam)
    return c - lam * a


def boot_ci(d1: dict, d2: dict, tids: list, rng: random.Random, draws: int = 4000):
    """Paired target-bootstrap of mean(d1 - d2): (lo, hi, two-sided p vs 0)."""
    diffs = []
    for _ in range(draws):
        samp = [rng.choice(tids) for _ in tids]
        diffs.append(sum(d1[t] - d2[t] for t in samp) / len(tids))
    diffs.sort()
    below = sum(1 for x in diffs if x < 0) / len(diffs)
    lo = diffs[int(0.025 * draws)]; hi = diffs[int(0.975 * draws)]
    return round(lo, 4), round(hi, 4), round(2 * min(below, 1 - below), 4)


def holm(pvals: dict) -> dict:
    """Holm-Bonferroni adjusted p-values for a family {name: p}."""
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(items); adj = {}; run = 0.0
    for i, (name, p) in enumerate(items):
        run = max(run, min(1.0, (m - i) * p))
        adj[name] = round(run, 4)
    return adj


# ---------- loaders ----------

def load_llm_actions(episode_glob: str) -> dict:
    """{(target_id, arm): [action,...]} from episode jsonl files (one or many seeds)."""
    d: dict = {}
    for f in sorted(glob.glob(episode_glob)):
        for line in open(f):
            if not line.strip():
                continue
            ep = json.loads(line)
            pid = ep.get("packet_id", "")
            tid = pid.split("::")[0]
            arm = ep.get("cue_condition") or (pid.split("::")[1] if "::" in pid else "?")
            d.setdefault((tid, arm), []).append(episode_action(ep))
    return d


def mean_net_llm(A: dict, arm: str, t: str, tc: bool, tmpl: bool, lam: float) -> float:
    acts = A.get((t, arm), ["defer"])
    return sum(net_of_action(a, tc, tmpl, lam) for a in acts) / len(acts)
