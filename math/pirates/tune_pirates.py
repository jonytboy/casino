"""Tune reel strips for both paytable variants and compare them."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from build_config import make, COUNTS, PAYTABLE
from slotmath.exact import evaluate
from slotmath.tune import tune

MINS = {"J": 2, "K": 2, "Q": 2, "A": 1, "Lemon": 1, "Seven": 1,
        "Star": 1, "Diamond": 1, "Bonus": 1, "Wild": 0}
MAXS = {"J": 6, "K": 6, "Q": 6, "A": 5, "Lemon": 4, "Seven": 3,
        "Star": 3, "Diamond": 2, "Bonus": 1, "Wild": 4}

# Variant B: drop 2-of-a-kind pays (they create sub-stake "wins") and lift the
# top award so the game has a headline max win worth advertising.
PAY_V2 = {s: {k: v for k, v in t.items() if k >= 3} for s, t in PAYTABLE.items()}
PAY_V2["Diamond"] = {3: 100, 4: 400, 5: 2000}
PAY_V2["Star"] = {3: 30, 4: 80, 5: 200}

variants = [
    ("faithful", "config/pirates-faithful.json", PAYTABLE,
     "original APK paytable, reels solved for 94%"),
    ("v2", "config/pirates-v2.json", PAY_V2,
     "2-of-a-kind pays removed, top award raised"),
]

results = {}
for key, path, paytable, desc in variants:
    base = make()
    base = type(base)(**{**base.__dict__, "paytable": {k: dict(v) for k, v in paytable.items()}})
    print(f"\n=== tuning {key}: {desc} ===")
    counts, cfg, _ = tune(base, COUNTS, target_rtp=0.94, target_trigger=(0.004, 0.010),
                          mins=MINS, maxs=MAXS, iterations=1500, verbose=False)
    res = evaluate(cfg, hit_rate=True)
    cfg.dump(path)
    results[key] = (res, counts)
    print(f"  RTP {res['rtp_total']*100:.2f}%  -> wrote {path}")

print("\n" + "=" * 66)
print(f"{'metric':26} {'faithful':>16} {'v2':>16}")
print("=" * 66)
rows = [("RTP (total)", "rtp_total", "%"), ("  from lines", "rtp_lines", "%"),
        ("  from scatter", "rtp_scatter", "%"), ("any-win rate", "any_win_rate", "%"),
        ("net-win rate (>= stake)", "net_win_rate", "%"),
        ("LDW rate (< stake)", "ldw_rate", "%"),
        ("bonus trigger", "scatter_trigger_rate", "%"),
        ("max win (x total bet)", "max_win_x_bet", "x")]
for label, key, unit in rows:
    a, b = results["faithful"][0][key], results["v2"][0][key]
    if unit == "%":
        print(f"{label:26} {a*100:15.2f}% {b*100:15.2f}%")
    else:
        print(f"{label:26} {a:15.0f}x {b:15.0f}x")
print("=" * 66)
for k in ("faithful", "v2"):
    t = results[k][0]["scatter_trigger_rate"]
    print(f"{k:10} bonus 1 in {1/t:.0f} spins")
