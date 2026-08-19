"""Build reel strips from symbol counts.

Symbols are spread as evenly as possible around the strip rather than left in
runs. Clumping matters for two reasons: adjacent duplicates look wrong in a
3-row window, and stacked scatters distort the trigger rate away from what a
naive count-based model predicts.
"""
from __future__ import annotations


def build_strip(counts: dict[str, int]) -> list[str]:
    """Distribute symbols around a strip, spacing repeats as evenly as possible."""
    total = sum(counts.values())
    if total == 0:
        return []
    # Place rarest symbols first at evenly spaced slots, then fill with commons.
    slots: list[str | None] = [None] * total
    order = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]))
    cursor = 0
    for sym, n in order:
        if n == 0:
            continue
        step = total / n
        for j in range(n):
            idx = int(round(j * step + cursor)) % total
            probe = 0
            while slots[(idx + probe) % total] is not None:
                probe += 1
                if probe > total:
                    raise RuntimeError("cannot place symbol %s" % sym)
            slots[(idx + probe) % total] = sym
        cursor += 1
    assert all(s is not None for s in slots)
    return [s for s in slots if s is not None]


def max_run(strip: list[str], symbol: str) -> int:
    """Longest circular run of `symbol` on the strip (diagnostic)."""
    n = len(strip)
    if symbol not in strip:
        return 0
    best = run = 0
    for i in range(2 * n):
        if strip[i % n] == symbol:
            run += 1
            best = max(best, run)
        else:
            run = 0
    return min(best, n)
