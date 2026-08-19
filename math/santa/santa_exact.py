"""Exact RTP for Santa Slots, read from the shipped Construct 2 project.

Everything here is read from source, not inferred:

  * paytable  - Files/prizes.xml (card id + lv -> payout, multiple of line bet)
  * paylines  - Event sheets/game.xml, 20 calls to "checkLine" over Array.At(reel,row)
  * reels     - game.xml fills each cell with floor(random(0,14)), i.e. uniform
                over 14 symbols (ids 0-13), independently per cell

There are no reel strips, so symbol frequency is uniform and the RTP falls out
of the paytable alone. That is the core defect: the payout percentage was never
chosen, only implied.
"""
import pathlib
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from slotmath.exact import evaluate
from slotmath.model import GameConfig

HERE = pathlib.Path(__file__).resolve().parent

# 20 paylines from game.xml. Index 7 (line 8) duplicates index 2 (line 3).
PAYLINES = [
    (1,1,1,1,1), (2,2,2,2,2), (0,0,0,0,0), (2,1,0,1,2), (0,1,2,1,0),
    (1,2,1,2,1), (1,0,1,0,1), (0,0,0,0,0), (0,0,1,2,2), (1,0,1,2,1),
    (1,2,1,0,1), (2,1,1,1,2), (0,1,1,1,0), (2,1,2,1,2), (0,1,0,1,0),
    (1,1,2,1,1), (1,1,0,1,1), (2,2,0,2,2), (0,0,2,0,0), (2,0,0,0,2),
]

# floor(random(0,14)) yields integers 0..13: fourteen equally likely symbols.
N_SYMBOLS = 14


def load_paytable(path=HERE / "source" / "prizes.xml"):
    table: dict[str, dict[int, float]] = {}
    for card in ET.parse(path).getroot().findall("card"):
        table.setdefault(f"card{card.get('id')}", {})[int(card.get("lv"))] = float(card.text)
    return table


def build(paytable) -> GameConfig:
    symbols = [f"card{i}" for i in range(N_SYMBOLS)]
    # No wild appears anywhere in the project; declare one that never lands so
    # the substitution rule stays inert.
    return GameConfig(
        name="Santa Slots", symbols=symbols + ["NoWild"], wild="NoWild",
        scatter="NoScatter" if False else f"card{N_SYMBOLS - 1}",
        paytable={k: v for k, v in paytable.items()},
        scatter_pays={}, scatter_spins={},
        reels=[list(symbols) for _ in range(5)],
    )


def show(label, cfg, lines):
    r = evaluate(cfg, lines=lines, hit_rate=True)
    print(f"\n--- {label} ---")
    print(f"  RTP                 {r['rtp_total']*100:8.2f}%")
    print(f"    (enumerated check {r['rtp_enumerated']*100:8.2f}%)")
    print(f"  any-win rate        {r['any_win_rate']*100:8.2f}%")
    print(f"  net-win rate        {r['net_win_rate']*100:8.2f}%   (returns at least the stake)")
    print(f"  LDW rate            {r['ldw_rate']*100:8.2f}%   (pays out, but less than staked)")
    print(f"  max win             {r['max_win_x_bet']:8.0f}x total bet")
    return r


if __name__ == "__main__":
    pt = load_paytable()
    show("as shipped", build(pt), PAYLINES)

    # card 12 reads 3oak=100, 4oak=10, 5oak=3 - strictly decreasing, so a better
    # outcome pays less. Treat it as a reversed data entry and check the cost.
    fixed = {k: dict(v) for k, v in pt.items()}
    fixed["card12"] = {3: 3, 4: 10, 5: 100}
    show("with card 12 un-reversed (3/10/100)", build(fixed), PAYLINES)

    show("un-reversed, duplicate payline 8 removed",
         build(fixed), [l for i, l in enumerate(PAYLINES) if i != 7])
