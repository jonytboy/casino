"""Final figures for every solved config, plus both games as originally shipped."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "santa"))

from santa_exact import PAYLINES as SANTA_LINES, build as santa_build, load_paytable
from slotmath.exact import evaluate
from slotmath.model import GameConfig

HERE = pathlib.Path(__file__).resolve().parent

rows = []


def add(label, cfg, lines):
    r = evaluate(cfg, lines=lines, hit_rate=True, max_windows=None)
    rows.append((label, len(cfg.reels[0]), lines, r))
    print(f"  done: {label}", flush=True)


print("computing (exact enumeration, slow for 40-position strips)...", flush=True)
add("Pirate Slots — as shipped", GameConfig.load(HERE / "pirates/config/pirates-faithful.json"), 30)
add("Santa Slots — as shipped", santa_build(load_paytable()), len(SANTA_LINES))
add("Pirate Slots — solved v3", GameConfig.load(HERE / "pirates/config/pirates-v3.json"), 30)
add("Santa Slots — solved", GameConfig.load(HERE / "santa/config/santa-94.json"), len(SANTA_LINES))

print("\n" + "=" * 92)
print(f"{'game':30}{'strip':>7}{'lines':>7}{'RTP':>9}{'any-win':>10}{'net-win':>9}{'LDW':>8}{'max win':>10}")
print("=" * 92)
for label, strip, lines, r in rows:
    print(f"{label:30}{strip:>7}{lines:>7}{r['rtp_total']*100:>8.2f}%"
          f"{r['any_win_rate']*100:>9.2f}%{r['net_win_rate']*100:>8.2f}%"
          f"{r['ldw_rate']*100:>7.2f}%{r['max_win_x_bet']:>9.0f}x")
print("=" * 92)
