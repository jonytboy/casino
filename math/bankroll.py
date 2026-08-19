"""How long a starting bank survives — the metric an ad-funded slot lives on.

Rewarded video in a coin-based slot is triggered by scarcity: the player runs
dry and is offered coins for an ad view. If the credit balance never falls, that
prompt never fires and the highest-value ad unit is never shown. So "spins until
broke" matters more to an ad-funded game than RTP does on its own.

Simulated rather than derived, because variance dominates: the mean is pulled
around by rare large wins, and the median is what a typical session actually
looks like.
"""
import pathlib
import random
import statistics
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "santa"))

from santa_exact import PAYLINES as SANTA, build, load_paytable
from slotmath.exact import line_win_multiplier
from slotmath.model import GameConfig
from slotmath.paylines import PAYLINES as PIRATE
from slotmath.simulate import spin_window

BANK, BET, CAP = 10_000, 2, 200_000


def spins_to_bust(cfg, lines, rng):
    stake = BET * len(lines)
    bank = BANK
    for n in range(1, CAP + 1):
        if bank < stake:
            return n
        bank -= stake
        w = spin_window(cfg, rng)
        for line in lines:
            bank += line_win_multiplier(cfg, tuple(w[r][row] for r, row in enumerate(line))) * BET
        sc = sum(col.count(cfg.scatter) for col in w)
        bank += cfg.scatter_pays.get(sc, 0) * stake
    return None  # never went broke


CASES = [
    ("Pirates — as shipped (103.66%)",
     GameConfig.load("pirates/config/pirates-as-shipped.json"), PIRATE),
    ("Santa — as shipped (229.60%)", build(load_paytable()), SANTA),
    ("Santa — solved (94.00%)", GameConfig.load("santa/config/santa-94.json"), SANTA),
    ("Pirates — solved (94.00%)", GameConfig.load("pirates/config/pirates-v3.json"), PIRATE),
]

print(f"bank {BANK:,} credits, {BET} per line\n")
print(f"{'game':32}{'median spins to broke':>24}{'never broke':>14}")
print("-" * 70)
for label, cfg, lines in CASES:
    rng = random.Random(99)
    runs = [spins_to_bust(cfg, lines, rng) for _ in range(120)]
    busts = [r for r in runs if r is not None]
    never = len(runs) - len(busts)
    med = f"{statistics.median(busts):,.0f}" if busts else "—"
    print(f"{label:32}{med:>24}{f'{never}/{len(runs)}':>14}")
