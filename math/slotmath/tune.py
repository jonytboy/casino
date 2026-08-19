"""Solve for reel strips that hit a target RTP.

Stochastic hill-climb over per-reel symbol counts. A move shifts one strip
position from one symbol to another on one reel; moves are kept when they
improve the objective. Deterministic given a seed.
"""
from __future__ import annotations

import random

from .exact import evaluate
from .model import GameConfig
from .strips import build_strip


def _cfg_from_counts(base: GameConfig, counts: list[dict[str, int]]) -> GameConfig:
    return GameConfig(
        name=base.name, symbols=base.symbols, wild=base.wild, scatter=base.scatter,
        paytable=base.paytable, scatter_pays=base.scatter_pays,
        scatter_spins=base.scatter_spins, rows=base.rows,
        reels=[build_strip({k: v for k, v in c.items() if v}) for c in counts],
    )


def objective(res: dict, target_rtp: float, target_trigger: tuple[float, float]) -> float:
    """Lower is better. RTP dominates; bonus trigger is a soft band."""
    cost = abs(res["rtp_total"] - target_rtp) * 100.0
    lo, hi = target_trigger
    t = res["scatter_trigger_rate"]
    if t < lo:
        cost += (lo - t) * 3000.0
    elif t > hi:
        cost += (t - hi) * 3000.0
    return cost


def tune(
    base: GameConfig,
    counts: list[dict[str, int]],
    target_rtp: float = 0.94,
    target_trigger: tuple[float, float] = (0.004, 0.012),
    mins: dict[str, int] | None = None,
    maxs: dict[str, int] | None = None,
    iterations: int = 600,
    seed: int = 20151113,
    verbose: bool = True,
):
    rng = random.Random(seed)
    mins = mins or {}
    maxs = maxs or {}
    cur = [dict(c) for c in counts]
    cur_res = evaluate(_cfg_from_counts(base, cur))
    cur_cost = objective(cur_res, target_rtp, target_trigger)

    for it in range(iterations):
        r = rng.randrange(len(cur))
        movable = [s for s in cur[r] if cur[r][s] > mins.get(s, 0)]
        # Wild stays off a reel that starts with none (keeps reels 1 and 5 wild-free).
        addable = [s for s in cur[r]
                   if cur[r][s] < maxs.get(s, 8) and not (s == base.wild and counts[r].get(s, 0) == 0)]
        if not movable or not addable:
            continue
        src, dst = rng.choice(movable), rng.choice(addable)
        if src == dst:
            continue
        cand = [dict(c) for c in cur]
        cand[r][src] -= 1
        cand[r][dst] = cand[r].get(dst, 0) + 1
        try:
            res = evaluate(_cfg_from_counts(base, cand))
        except Exception:
            continue
        cost = objective(res, target_rtp, target_trigger)
        if cost < cur_cost:
            cur, cur_res, cur_cost = cand, res, cost
            if verbose and it % 25 == 0:
                print(f"  it {it:4d}  RTP {res['rtp_total']*100:6.2f}%  "
                      f"trigger {res['scatter_trigger_rate']*100:5.3f}%  cost {cost:.4f}")
        if cur_cost < 1e-3:
            break

    return cur, _cfg_from_counts(base, cur), cur_res
