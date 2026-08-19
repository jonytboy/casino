"""Check the Python model against the shipped game's own JavaScript.

The checkLine function transcribed below is lifted verbatim from
`source/game-eventsheet.txt` (Event sheets/game.xml). Comparing every possible
line against it is what proved card0 is a wild and that a line pays the first
non-wild symbol rather than the best one — two facts that moved the measured
RTP of the shipped game from a supposed 47.47% to an actual 229.60%.
"""
import sys, itertools
import pathlib
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from santa_exact import build, load_paytable
from slotmath.exact import line_win_multiplier

cfg = build(load_paytable())
pt = {int(k.replace("card","")): v for k, v in cfg.paytable.items()}

def game_js(cards):
    """Transcribed from Event sheets/game.xml, checkLine."""
    value = 0
    for i in range(len(cards) - 1, -1, -1):
        if cards[i] != 0:
            value = cards[i]
    win = 0
    if (cards[0] == 0 or cards[0] == value) and (cards[1] == 0 or cards[1] == value):
        if value in (0, 9, 10, 11):
            win = 2
        if cards[2] == 0 or cards[2] == value:
            win = 3
            if cards[3] == 0 or cards[3] == value:
                win = 4
                if cards[4] == 0 or cards[4] == value:
                    win = 5
    return float(pt.get(value, {}).get(win, 0)) if win else 0.0

n = 14
bad = 0
for combo in itertools.product(range(n), repeat=5):
    a = game_js(list(combo))
    b = line_win_multiplier(cfg, tuple(f"card{i}" for i in combo))
    if abs(a - b) > 1e-9:
        if bad < 5:
            print(f"  MISMATCH {combo}: game={a} model={b}")
        bad += 1
print(f"compared all {n**5:,} line combinations")
print("mismatches:", bad if bad else "none — the model reproduces the game exactly")
