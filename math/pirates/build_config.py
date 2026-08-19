"""Generate the Pirates Slot config from the paytable recovered from the APK."""
import sys
sys.path.insert(0, '.')
from slotmath.model import GameConfig
from slotmath.strips import build_strip

SYMBOLS = ["J", "K", "Q", "A", "Lemon", "Seven", "Star", "Diamond", "Wild", "Bonus"]

# Recovered verbatim from GameLayer.creatPayTableView() in the decompiled APK.
# Values are per payline, as multiples of bet-per-line.
PAYTABLE = {
    "J":       {2: 2,  3: 4,   4: 8,   5: 16},
    "K":       {3: 5,  4: 10,  5: 20},
    "Q":       {2: 4,  3: 8,   4: 16,  5: 32},
    "A":       {3: 10, 4: 20,  5: 40},
    "Lemon":   {3: 20, 4: 40,  5: 80},
    "Seven":   {3: 25, 4: 50,  5: 100},
    "Star":    {2: 10, 3: 30,  4: 60,  5: 120},
    "Diamond": {3: 100, 4: 200, 5: 400},
}

# Original awards free spins on 3+ Bonus (40/20/10/5 spins seen in GameLayer).
SCATTER_SPINS = {3: 10, 4: 20, 5: 40}
# Scatter cash component, as multiples of TOTAL bet.
SCATTER_PAYS = {3: 2, 4: 10, 5: 50}

# Per-reel symbol counts (20 positions each). Wild appears on reels 2-4 only.
OUTER = {"J": 4, "K": 4, "Q": 3, "A": 3, "Lemon": 2, "Seven": 1,
         "Star": 1, "Diamond": 1, "Wild": 0, "Bonus": 1}
INNER = {"J": 4, "K": 3, "Q": 3, "A": 3, "Lemon": 2, "Seven": 1,
         "Star": 1, "Diamond": 1, "Wild": 1, "Bonus": 1}
COUNTS = [OUTER, INNER, INNER, INNER, OUTER]


def make(counts_per_reel=COUNTS, name="Pirates Slot"):
    return GameConfig(
        name=name, symbols=SYMBOLS, wild="Wild", scatter="Bonus",
        paytable={k: dict(v) for k, v in PAYTABLE.items()},
        scatter_pays=dict(SCATTER_PAYS), scatter_spins=dict(SCATTER_SPINS),
        reels=[build_strip({k: v for k, v in c.items() if v}) for c in counts_per_reel],
    )


if __name__ == "__main__":
    cfg = make()
    cfg.validate()
    cfg.dump("config/pirates.json")
    print("wrote config/pirates.json")
    for i, r in enumerate(cfg.reels):
        print(f"  reel {i+1} ({len(r)}): {' '.join(r)}")
