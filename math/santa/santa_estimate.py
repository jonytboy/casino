"""Estimate Santa Slots RTP from prizes.xml and the Construct 2 event sheet.

ASSUMPTION: the text extraction stripped prizes.xml's id/lv attributes, so the
symbol->payout mapping below is inferred from value ordering. The reel model is
NOT inferred: game.xml picks each cell with floor(random(0,14)), i.e. uniform
over 15 symbols, independently. That is the part that determines the RTP shape.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from slotmath.exact import evaluate
from slotmath.model import GameConfig

# 20 paylines read from game.xml. Line 8 duplicates line 3 in the shipped game.
SANTA_LINES = [
    (1,1,1,1,1), (2,2,2,2,2), (0,0,0,0,0), (2,1,0,1,2), (0,1,2,1,0),
    (1,2,1,2,1), (1,0,1,0,1), (0,0,0,0,0), (0,0,1,2,2), (1,0,1,2,1),
    (1,2,1,0,1), (2,1,1,1,2), (0,1,1,1,0), (2,1,2,1,2), (0,1,0,1,0),
    (1,1,2,1,1), (1,1,0,1,1), (2,2,0,2,2), (0,0,2,0,0), (2,0,0,0,2),
]

PAYTABLE = {
    "S1": {3: 5,  4: 20,  5: 100},   "S2": {3: 5,  4: 20,  5: 100},
    "S3": {3: 7,  4: 25,  5: 150},   "S4": {3: 7,  4: 25,  5: 150},
    "S5": {3: 10, 4: 30,  5: 200},   "S6": {3: 10, 4: 30,  5: 200},
    "S7": {3: 15, 4: 75,  5: 500},   "S8": {3: 15, 4: 75,  5: 500},
    "P1": {2: 5,  3: 50,  4: 100, 5: 1000},
    "P2": {2: 5,  3: 100, 4: 250, 5: 2500},
    "P3": {2: 10, 3: 150, 4: 500, 5: 5000},
    "P4": {2: 15, 3: 200, 4: 1000, 5: 5000},
}
SYMBOLS = list(PAYTABLE) + ["Blank1", "Blank2", "Bonus"]
# No wild appears on the strips; declare one that never lands so the
# substitution rule is inert rather than accidentally enabled.
ALL_SYMBOLS = SYMBOLS + ["NoWild"]
assert len(SYMBOLS) == 15, len(SYMBOLS)

# Uniform: floor(random(0,14)) means each of the 15 symbols is equally likely.
strip = list(SYMBOLS)
cfg = GameConfig(
    name="Santa Slots (uniform RNG, as shipped)", symbols=ALL_SYMBOLS,
    wild="NoWild", scatter="Bonus", paytable=PAYTABLE,
    scatter_pays={3: 3, 4: 10, 5: 100}, scatter_spins={3: 1},
    reels=[list(strip) for _ in range(5)],
)
cfg.validate()

for label, lines in (("as shipped (20 lines, incl. duplicate)", SANTA_LINES),
                     ("with duplicate line 8 removed (19)", [l for i, l in enumerate(SANTA_LINES) if i != 7])):
    r = evaluate(cfg, lines=len(lines))
    print(f"\n--- {label} ---")
    print(f"  RTP total     {r['rtp_total']*100:8.2f}%")
    print(f"    lines       {r['rtp_lines']*100:8.2f}%")
    print(f"    scatter     {r['rtp_scatter']*100:8.2f}%")
