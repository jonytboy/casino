"""Exact (closed-form) RTP evaluation.

With 20-position strips the game is small enough to solve exactly rather than
estimate, so these figures carry no sampling error.

Two independent parts:

  * Line wins - a payline takes one row per reel, and the marginal symbol
    distribution on a reel is identical for every row, so all 30 paylines share
    one expectation. The win for a given 5-symbol combination is fixed by the
    paytable, so we precompute the full |S|^5 win tensor once and reduce each
    evaluation to a tensor contraction against the per-reel probabilities.

  * Scatter wins - pay on symbol COUNT anywhere in the 3x5 window, so they
    depend on the whole visible window. We build the per-reel distribution of
    scatter count across all stops, then convolve across the five reels.
"""
from __future__ import annotations

from itertools import product

import numpy as np

from .model import GameConfig
from .paylines import PAYLINES

_TENSOR_CACHE: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}


def line_win_multiplier(cfg: GameConfig, combo: tuple[str, ...]) -> float:
    """Best left-to-right win for one payline, as a multiple of bet-per-line.

    A run counts from reel 1 and accepts the symbol itself or a wild. The line
    pays the highest-value symbol it qualifies for, which matters when wilds
    could complete more than one symbol.
    """
    if cfg.rule == "leftmost_nonwild":
        # Santa Slots: the line pays the first non-wild symbol on it, whatever
        # that symbol is worth -- not the most valuable symbol the wilds could
        # complete. An all-wild line pays the wild's own row.
        value = cfg.wild
        for c in combo:
            if c != cfg.wild:
                value = c
                break
        run = 0
        for c in combo:
            if c == value or c == cfg.wild:
                run += 1
            else:
                break
        return cfg.paytable.get(value, {}).get(run, 0.0) if run >= 2 else 0.0

    best = 0.0
    for sym in cfg.paying_symbols:
        run = 0
        for c in combo:
            if c == sym or c == cfg.wild:
                run += 1
            else:
                break
        if run >= 2:
            best = max(best, cfg.paytable.get(sym, {}).get(run, 0.0))
    return best


def _win_tensor(cfg: GameConfig) -> tuple[np.ndarray, np.ndarray]:
    """Win tensor over all |S|^5 symbol combinations, and its boolean hit mask.

    Depends only on symbols/paytable/wild, so it is cached across the many
    evaluations a tuning run performs.
    """
    key = (
        tuple(cfg.symbols), cfg.wild, cfg.scatter, cfg.rule,
        tuple((s, tuple(sorted(t.items()))) for s, t in sorted(cfg.paytable.items())),
    )
    hit = _TENSOR_CACHE.get(key)
    if hit is None:
        n = len(cfg.symbols)
        W = np.zeros((n,) * 5, dtype=np.float64)
        for idx in product(range(n), repeat=5):
            W[idx] = line_win_multiplier(cfg, tuple(cfg.symbols[i] for i in idx))
        _TENSOR_CACHE[key] = hit = (W, (W > 0).astype(np.float64))
    return hit


def line_stats(cfg: GameConfig) -> dict:
    """Exact expectation, variance and hit rate of a single payline."""
    W, H = _win_tensor(cfg)
    probs = [
        np.array([cfg.symbol_probs(i)[s] for s in cfg.symbols], dtype=np.float64)
        for i in range(5)
    ]
    sub = "ijklm,i,j,k,l,m->"
    ev = float(np.einsum(sub, W, *probs))
    ev2 = float(np.einsum(sub, W * W, *probs))
    hit = float(np.einsum(sub, H, *probs))
    return {"ev": ev, "var": ev2 - ev * ev, "hit_rate": hit}


def scatter_count_dist(cfg: GameConfig) -> dict[int, float]:
    """Exact distribution of scatter symbols visible in the 3x5 window.

    Computed over the full window rather than from symbol counts, so stacked or
    adjacent scatters on a strip are accounted for correctly.
    """
    dist = {0: 1.0}
    for strip in cfg.reels:
        n = len(strip)
        per_reel: dict[int, float] = {}
        for stop in range(n):
            k = sum(1 for r in range(cfg.rows) if strip[(stop + r) % n] == cfg.scatter)
            per_reel[k] = per_reel.get(k, 0.0) + 1.0 / n
        merged: dict[int, float] = {}
        for a, pa in dist.items():
            for b, pb in per_reel.items():
                merged[a + b] = merged.get(a + b, 0.0) + pa * pb
        dist = merged
    return dist


def evaluate(cfg: GameConfig, lines=PAYLINES, hit_rate: bool = False,
             max_windows: int | None = 8_000_000) -> dict:
    """Full exact evaluation. RTP is returned as a fraction (0.94 = 94%).

    `lines` is the payline list, not a count. It must be the list, because the
    enumerated statistics below depend on which cells each line reads, not just
    how many lines there are. RTP happens to be invariant to the line count --
    every line shares one expectation and the stake scales with them -- so
    passing the wrong lines still yields the right RTP, which makes that the one
    figure incapable of catching a mistake here.
    """
    if isinstance(lines, int):
        raise TypeError("evaluate(lines=...) takes the payline list, not a count")
    ls = line_stats(cfg)

    # Total bet = lines * bet_per_line, and every line shares one expectation,
    # so total line RTP equals the single-line expectation in bet-per-line units.
    n_lines = len(lines)
    rtp_lines = ls["ev"]

    dist = scatter_count_dist(cfg)
    rtp_scatter = sum(p * cfg.scatter_pays.get(k, 0.0) for k, p in dist.items())
    scatter_trigger = sum(p for k, p in dist.items() if k in cfg.scatter_spins)

    # Line wins across `lines` paylines are identically distributed but not
    # independent, so per-line variance is reported as the volatility proxy.
    return {
        "rtp_total": rtp_lines + rtp_scatter,
        "rtp_lines": rtp_lines,
        "rtp_scatter": rtp_scatter,
        "line_hit_rate": ls["hit_rate"],
        "line_variance": ls["var"],
        "volatility_index": ls["var"] ** 0.5,
        "scatter_trigger_rate": scatter_trigger,
        "scatter_dist": dist,
        "lines": n_lines,
        **(exact_spin_stats(cfg, lines, max_windows=max_windows) if hit_rate else {}),
    }


def exact_spin_stats(cfg: GameConfig, lines=PAYLINES,
                     max_windows: int | None = 8_000_000) -> dict:
    """Exact spin-outcome statistics by enumerating every reel-stop combination.

    Hit rate cannot be derived from per-line probabilities the way RTP can:
    paylines overlap on the same 15 visible symbols, so treating them as
    independent overstates it badly. RTP is a mean and is unaffected by that
    correlation; hit rate and the win distribution are not. With 20-position
    strips there are only 20^5 = 3.2M windows, so we enumerate them in chunks
    over reel 1's stop.

    Also reports the rate of wins that return less than the amount staked. Those
    "losses disguised as wins" are counted as wins by hit-rate figures while
    leaving the player down on the spin, so a headline hit rate is misleading
    without them.
    """
    n_windows = 1
    for strip in cfg.reels:
        n_windows *= len(strip)
    if max_windows is not None and n_windows > max_windows:
        raise ValueError(
            f"{n_windows:,} windows exceeds max_windows={max_windows:,}. "
            "Enumeration cost grows as (strip length)^5; pass max_windows=None to "
            "force it, or use simulate() for an estimate.")

    W, _ = _win_tensor(cfg)
    n_sym = len(cfg.symbols)
    sym_index = {s: i for i, s in enumerate(cfg.symbols)}
    Wflat = W.ravel()
    n_lines = len(lines)
    stake = float(n_lines)  # in bet-per-line units

    idx, scat = [], []
    for strip in cfg.reels:
        n = len(strip)
        idx.append(np.array(
            [[sym_index[strip[(stop + r) % n]] for r in range(cfg.rows)] for stop in range(n)],
            dtype=np.int64))
        scat.append(np.array(
            [sum(1 for r in range(cfg.rows) if strip[(stop + r) % n] == cfg.scatter)
             for stop in range(n)], dtype=np.int64))

    sizes = [len(s) for s in cfg.reels]
    grid = np.meshgrid(*[np.arange(s) for s in sizes[1:]], indexing="ij")
    stops = [g.ravel() for g in grid]
    chunk = stops[0].size

    max_scat = sum(cfg.rows for _ in cfg.reels)
    scat_pay = np.zeros(max_scat + 1)
    for k, v in cfg.scatter_pays.items():
        if k <= max_scat:
            scat_pay[k] = v
    tail_scat = scat[1][stops[0]] + scat[2][stops[1]] + scat[3][stops[2]] + scat[4][stops[3]]

    total_windows = sizes[0] * chunk
    sum_win = 0.0
    n_any = n_ldw = n_real = 0
    biggest = 0.0
    for s0 in range(sizes[0]):
        win = np.zeros(chunk, dtype=np.float64)
        for line in lines:
            flat = np.full(chunk, idx[0][s0, line[0]], dtype=np.int64)
            for reel in range(1, 5):
                flat = flat * n_sym + idx[reel][stops[reel - 1], line[reel]]
            win += Wflat[flat]
        # Scatter pays a multiple of TOTAL bet, so scale into bet-per-line units.
        win += scat_pay[tail_scat + scat[0][s0]] * n_lines
        sum_win += float(win.sum())
        n_any += int((win > 0).sum())
        n_ldw += int(((win > 0) & (win < stake)).sum())
        n_real += int((win >= stake).sum())
        biggest = max(biggest, float(win.max()))

    return {
        "any_win_rate": n_any / total_windows,
        "ldw_rate": n_ldw / total_windows,
        "net_win_rate": n_real / total_windows,
        "rtp_enumerated": sum_win / (total_windows * stake),
        "max_win_x_bet": biggest / stake,
        "windows": total_windows,
    }


# Backwards-compatible alias.
def exact_hit_rate(cfg: GameConfig, lines=PAYLINES) -> dict:
    return exact_spin_stats(cfg, lines)
