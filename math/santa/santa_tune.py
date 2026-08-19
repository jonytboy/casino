"""Solve Santa Slots reel strips for a target RTP.

The shipped game has no reel strips at all: every cell is an independent
uniform draw, so its 47.47% return was implied by the paytable rather than
chosen. This introduces strips and solves their composition.

The paytable is left exactly as shipped (including card12's reversed values) so
the game keeps its identity; only symbol frequency changes.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from santa_exact import PAYLINES, build, load_paytable
from slotmath.exact import evaluate
from slotmath.tune import tune

LEN = 40
PREMIUM = ["card0", "card11", "card10", "card9"]   # pay from 2 of a kind
MID = ["card7", "card8", "card5", "card6"]
LOW = ["card1", "card2", "card3", "card4"]
ODD = ["card12"]
BLANK = ["card13"]

# Premiums must stay rare or the reels read as a jackpot machine; blanks give
# the tuner somewhere to dump probability mass.
START = {**{s: 1 for s in PREMIUM}, "card0": 3, **{s: 3 for s in MID},
         **{s: 4 for s in LOW}, "card12": 2, "card13": 6}
START["card13"] = LEN - sum(v for k, v in START.items() if k != "card13")
assert sum(START.values()) == LEN, sum(START.values())

# Premiums stay rare; the cheap symbols are allowed to dominate the strip,
# which is what produces frequent small wins without moving RTP much. card13
# keeps a floor so the blank still appears on screen.
# card0 carries the 5000x top award. Fix it at exactly 3 per reel and stack
# those three contiguously, so one stop can fill a whole reel with it -- which
# is the only way many paylines can pay the top award at once.
STACKS = {"card0": 3}
MINS = {"card0": 3, **{s: 1 for s in PREMIUM if s != "card0"}, **{s: 1 for s in MID},
        **{s: 2 for s in LOW}, "card12": 1, "card13": 1}
MAXS = {"card0": 3, "card11": 2, "card10": 3, "card9": 3,
        **{s: 5 for s in MID}, **{s: 14 for s in LOW},
        "card12": 3, "card13": 6}

base = build(load_paytable())
counts = [dict(START) for _ in range(5)]

print(f"target 94% RTP, {LEN}-position strips, premiums capped rare")
# Per-line hit rate is the cheap in-loop proxy for how often the game pays at
# all; the true any-win figure is enumerated below.
counts, cfg, _ = tune(base, counts, target_rtp=0.94,
                      target_trigger=(0.0, 1.0),   # no scatter in this game
                      target_line_hit=(0.050, 0.070), stacks=STACKS,
                      mins=MINS, maxs=MAXS, iterations=4000, verbose=False)

before = evaluate(base, lines=PAYLINES, hit_rate=True)
print("\nenumerating 102,400,000 windows for exact stats (slow)...")
after = evaluate(cfg, lines=PAYLINES, hit_rate=True, max_windows=None)

print(f"\n{'metric':26} {'as shipped':>14} {'solved':>14}")
print("-" * 56)
for label, key, unit in [("RTP", "rtp_total", "%"), ("any-win rate", "any_win_rate", "%"),
                         ("net-win rate", "net_win_rate", "%"), ("LDW rate", "ldw_rate", "%"),
                         ("max win (x total bet)", "max_win_x_bet", "x")]:
    a, b = before[key], after[key]
    if unit == "%":
        print(f"{label:26} {a*100:13.2f}% {b*100:13.2f}%")
    else:
        print(f"{label:26} {a:13.0f}x {b:13.0f}x")

print("\nsolved counts per reel (40 positions):")
for i, c in enumerate(counts):
    print(f"  reel {i+1}: " + "  ".join(f"{k.replace('card','c')}:{v}" for k, v in sorted(
        c.items(), key=lambda kv: int(kv[0][4:])) if v))

cfg.dump(pathlib.Path(__file__).resolve().parent / "config" / "santa-94.json")
print("\nwrote config/santa-94.json")
