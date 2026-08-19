"""Full exact report for one slot config."""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from slotmath.exact import evaluate
from slotmath.model import GameConfig

default = pathlib.Path(__file__).resolve().parent / "config" / "pirates.json"
cfg = GameConfig.load(sys.argv[1] if len(sys.argv) > 1 else default)

t = time.time()
try:
    r = evaluate(cfg, hit_rate=True)
except ValueError as e:
    print(f"note: {e}\nfalling back to RTP only.\n")
    r = evaluate(cfg)
elapsed = time.time() - t

print(f"=== {cfg.name} ===")
print(f"strips {len(cfg.reels[0])} positions x 5 reels | {r['lines']} paylines | {elapsed:.2f}s\n")
print(f"  TOTAL RTP           {r['rtp_total']*100:8.2f}%")
print(f"    from paylines     {r['rtp_lines']*100:8.2f}%")
print(f"    from scatter      {r['rtp_scatter']*100:8.2f}%")
if "rtp_enumerated" in r:
    print(f"    (enumerated check {r['rtp_enumerated']*100:8.2f}%)")
print()
if "any_win_rate" in r:
    print(f"  any-win rate        {r['any_win_rate']*100:8.2f}%")
    print(f"  net-win rate        {r['net_win_rate']*100:8.2f}%   (returns at least the stake)")
    print(f"  LDW rate            {r['ldw_rate']*100:8.2f}%   (pays out, but less than staked)")
    print(f"  max win             {r['max_win_x_bet']:8.0f}x total bet")
print(f"  volatility index    {r['volatility_index']:8.2f}")
t = r["scatter_trigger_rate"]
print(f"  bonus trigger       {t*100:8.3f}%   (1 in {1/max(t,1e-12):.0f} spins)")
print("\n  scatter count distribution:")
for k in sorted(r["scatter_dist"]):
    p = r["scatter_dist"][k]
    if p > 1e-9:
        print(f"    {k} bonus: {p*100:7.4f}%")
