"""Variant 3: longer reel strips, which give the tuner finer control.

At 20 positions with one Bonus per reel the scatter is visible 3/20 of the time,
pinning the bonus trigger near 1 in 38 spins regardless of anything else. Real
slot strips run 30-100 positions for exactly this reason.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from build_config import make
from slotmath.exact import evaluate
from slotmath.tune import tune
from tune_pirates import PAY_V2, MINS

LEN = 40
OUTER = {"J": 8, "K": 8, "Q": 6, "A": 6, "Lemon": 4, "Seven": 3,
         "Star": 2, "Diamond": 2, "Wild": 0, "Bonus": 1}
INNER = {"J": 8, "K": 7, "Q": 6, "A": 6, "Lemon": 4, "Seven": 3,
         "Star": 2, "Diamond": 2, "Wild": 1, "Bonus": 1}
COUNTS40 = [OUTER, INNER, INNER, INNER, OUTER]
for c in COUNTS40:
    assert sum(c.values()) == LEN, sum(c.values())

MAXS = {"J": 12, "K": 12, "Q": 12, "A": 10, "Lemon": 8, "Seven": 6,
        "Star": 5, "Diamond": 4, "Bonus": 2, "Wild": 8}

base = make()
base = type(base)(**{**base.__dict__, "paytable": {k: dict(v) for k, v in PAY_V2.items()}})
counts, cfg, _ = tune(base, COUNTS40, target_rtp=0.94, target_trigger=(0.004, 0.010),
                      mins={**MINS, "Bonus": 1}, maxs=MAXS, iterations=2500, verbose=False)
res = evaluate(cfg, hit_rate=True)
cfg.dump("config/pirates-v3.json")
print(f"strip length      {len(cfg.reels[0])}")
print(f"RTP               {res['rtp_total']*100:.2f}%  "
      f"(lines {res['rtp_lines']*100:.2f}%, scatter {res['rtp_scatter']*100:.2f}%)")
print(f"any-win rate      {res['any_win_rate']*100:.2f}%")
print(f"net-win rate      {res['net_win_rate']*100:.2f}%")
print(f"LDW rate          {res['ldw_rate']*100:.2f}%")
print(f"bonus trigger     {res['scatter_trigger_rate']*100:.3f}%  (1 in {1/res['scatter_trigger_rate']:.0f} spins)")
print(f"max win           {res['max_win_x_bet']:.0f}x total bet")
print("wrote config/pirates-v3.json")
