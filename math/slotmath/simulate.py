"""Monte Carlo spin simulation.

This exists to cross-check `exact.py` by an independent route: it actually
spins reels and reads the 3x5 window, rather than reasoning about marginal
distributions. If the two disagree, the closed form is wrong.
"""
from __future__ import annotations

import random

from .exact import line_win_multiplier
from .model import GameConfig
from .paylines import PAYLINES


def spin_window(cfg: GameConfig, rng: random.Random) -> list[list[str]]:
    """Return the visible window as window[reel][row]."""
    window = []
    for strip in cfg.reels:
        n = len(strip)
        stop = rng.randrange(n)
        window.append([strip[(stop + r) % n] for r in range(cfg.rows)])
    return window


def evaluate_window(cfg: GameConfig, window: list[list[str]], lines=PAYLINES) -> dict:
    """Total win for one spin: line wins in bet-per-line units, scatter in total-bet units."""
    line_total = 0.0
    hits = 0
    for line in lines:
        combo = tuple(window[reel][row] for reel, row in enumerate(line))
        win = line_win_multiplier(cfg, combo)
        if win > 0:
            hits += 1
        line_total += win

    scatters = sum(col.count(cfg.scatter) for col in window)
    scatter_win = cfg.scatter_pays.get(scatters, 0.0)
    return {
        "line_win": line_total,
        "scatter_win": scatter_win,
        "scatters": scatters,
        "line_hits": hits,
        "free_spins": cfg.scatter_spins.get(scatters, 0),
    }


def simulate(cfg: GameConfig, spins: int = 1_000_000, seed: int = 12345,
             lines=PAYLINES) -> dict:
    """Run `spins` spins. RTP is total return / total staked."""
    rng = random.Random(seed)
    n_lines = len(lines)
    total_line = 0.0
    total_scatter = 0.0
    spins_with_win = 0
    triggers = 0

    for _ in range(spins):
        r = evaluate_window(cfg, spin_window(cfg, rng), lines)
        total_line += r["line_win"]
        total_scatter += r["scatter_win"]
        if r["line_hits"] or r["scatter_win"] > 0:
            spins_with_win += 1
        if r["free_spins"]:
            triggers += 1

    # Stake per spin = n_lines bet-per-line units. Scatter pays total bet,
    # so convert to the same units by multiplying by n_lines.
    staked = spins * n_lines
    returned = total_line + total_scatter * n_lines
    return {
        "rtp_total": returned / staked,
        "rtp_lines": total_line / staked,
        "rtp_scatter": (total_scatter * n_lines) / staked,
        "any_win_rate": spins_with_win / spins,
        "scatter_trigger_rate": triggers / spins,
        "spins": spins,
    }
