"""Build reel strips from symbol counts, with optional stacking.

Two competing concerns decide how symbols are laid out around a strip.

*Spacing.* By default repeats are spread as evenly as possible. Adjacent
duplicates look wrong in a 3-row window, and accidental stacks distort the
scatter trigger rate away from what a count-based model predicts.

*Stacking.* Premium symbols are the exception: a large top win needs one symbol
filling all three visible rows of a reel at once, which evenly-spaced singles
can never produce. Real machines place premiums in deliberate contiguous blocks.

Stacking does not change RTP. Line wins depend only on each reel's marginal
symbol frequency, which is count/length however the symbols are arranged. What
stacking changes is the joint distribution across rows: wins become rarer but
larger, since a stacked reel makes every payline through it agree.
"""
from __future__ import annotations

from collections import Counter


def build_strip(counts: dict[str, int], stacks: dict[str, int] | None = None) -> list[str]:
    """Lay out a strip from symbol counts.

    `stacks` maps a symbol to the size of contiguous block it should appear in;
    anything unlisted is placed singly. A symbol with fewer positions than its
    stack size is stacked as large as its count allows.
    """
    stacks = stacks or {}
    blocks: list[tuple[str, int]] = []
    for sym, n in sorted(counts.items()):
        if n <= 0:
            continue
        size = min(max(1, int(stacks.get(sym, 1))), n)
        full, remainder = divmod(n, size)
        blocks.extend([(sym, size)] * full)
        if remainder:
            blocks.append((sym, remainder))

    # Greedy interleave: always take the symbol with the most blocks left that
    # is not the one just placed, so same-symbol blocks stay apart and only the
    # requested stacks are contiguous.
    pending: dict[str, list[int]] = {}
    for sym, size in blocks:
        pending.setdefault(sym, []).append(size)
    remaining = Counter({s: len(v) for s, v in pending.items()})

    ordered: list[tuple[str, int]] = []
    previous = None
    for _ in range(len(blocks)):
        options = [s for s in remaining if remaining[s] > 0 and s != previous]
        if not options:  # only the previous symbol is left; it has to repeat
            options = [s for s in remaining if remaining[s] > 0]
        pick = max(options, key=lambda s: (remaining[s], s))
        ordered.append((pick, pending[pick].pop()))
        remaining[pick] -= 1
        previous = pick

    strip: list[str] = []
    for sym, size in ordered:
        strip.extend([sym] * size)
    return strip


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
