# Pirates Slot — math model

An engine-independent model of the slot maths recovered from `PiratesSlot.apk`
(built 13 Nov 2015, `com.jonty.caribbeanslots`).

The original game had **no defined RTP**. `GameLayer.java` called `Math.random()`
at roughly twenty separate sites across 4,364 lines, with no reel strips and no
paytable in code — the paytable existed only as UI label text, and the odds were
an emergent side effect of the reel-fill logic. Nobody could state what the game
paid out.

This package fixes that. The maths lives as **data** (`config/*.json`) plus a
verifier, so any client — Unity, Godot, HTML5 — consumes the same reel strips and
paytable and is guaranteed to pay the same.

## What was recovered

Extracted verbatim from `GameLayer.creatPayTableView()`. Values are per payline,
as multiples of bet-per-line:

| symbol  | 2  | 3   | 4   | 5   |
|---------|----|-----|-----|-----|
| J       | 2  | 4   | 8   | 16  |
| K       | –  | 5   | 10  | 20  |
| Q       | 4  | 8   | 16  | 32  |
| A       | –  | 10  | 20  | 40  |
| Lemon   | –  | 20  | 40  | 80  |
| Seven   | –  | 25  | 50  | 100 |
| Star    | 10 | 30  | 60  | 120 |
| Diamond | –  | 100 | 200 | 400 |

Wild substitutes for everything except Bonus. Bonus is a scatter: 3 or more
triggers free spins (the original awarded 5/10/20/40).

Cabinet: 5 reels x 3 rows, 20-position strips, 30 paylines.

## Findings

**The original paytable pays 68.40%.** Against a naive uniform-ish reel design,
the recovered paytable returns 68.40% — far below the 92–96% players and
operators expect. As shipped it would have felt punishing.

**Two symbols pay from 2 of a kind, and it distorts everything.** J, Q and Star
pay on two symbols. Across 30 paylines that makes a win land on most spins, but
a 2-symbol J pays 2x bet-per-line against a 30x total stake. The player is shown
a win and a win sound while being down on the spin. At 94% RTP those
"losses disguised as wins" run at **20.7% of all spins** — more than a third of
every win the machine celebrates. Variant `v2` removes 2-of-a-kind pays.

**The strips are too short to control the bonus.** With 20 positions and one
Bonus per reel, the scatter is visible 3/20 of the time, which pins the bonus at
1 in 38 spins no matter what else is tuned. Real slot strips run 30–100
positions. Variant `v3` uses 40 and reaches 1 in 110.

**Max win is low.** The recovered paytable tops out around 51x total bet.
Modern slots advertise 1,000x+, and max win is a headline marketing number.
`v3` reaches 287x; going higher means raising the top award and re-solving.

## Configs

All three are solved to 94.00% RTP, so they differ in feel, not in cost.

| config | strips | any-win | net-win | LDW | bonus | max win |
|---|---|---|---|---|---|---|
| `pirates-faithful.json` | 20 | 55.5% | 34.9% | 20.7% | 1 in 38 | 51x |
| `pirates-v2.json` | 20 | 45.7% | 26.7% | 19.1% | 1 in 38 | 82x |
| `pirates-v3.json` | 40 | 49.0% | 21.1% | 27.9% | 1 in 110 | 287x |

*net-win = returns at least the stake. LDW = pays out, but less than staked.*

`pirates.json` is the working file written by `build_config.py` / `tune_pirates.py`.

## How the maths is computed

Everything is **exact**, not sampled. Three routes, cross-checked against each
other so an error in one is caught by the others:

1. **Win-tensor contraction** (`exact.py`) — the win for any 5-symbol
   combination is fixed by the paytable, so the full `|S|^5` tensor is built once
   and each evaluation is a contraction against per-reel probabilities. ~3ms.
2. **Full enumeration** (`exact_spin_stats`) — every reel-stop combination.
   Needed because hit rate, unlike RTP, cannot be derived from per-line
   probabilities: the 30 paylines overlap on the same 15 visible symbols.
   Assuming independence overstated the hit rate by 34 points.
   Cost is `(strip length)^5`, so it is guarded by `max_windows`.
3. **Monte Carlo** (`simulate.py`) — actually spins the reels.

Routes 1 and 2 agree to 1e-9; route 3 lands within sampling error.

## Usage

```bash
pip install numpy

python3 build_config.py                    # regenerate from the recovered paytable
python3 tune_pirates.py                    # solve reels for faithful + v2
python3 tune_v3.py                         # solve 40-position variant
python3 report.py config/pirates-v3.json   # full report for one config
python3 tests/test_math.py                 # 8 tests
```

Tuning is a deterministic hill-climb over per-reel symbol counts (fixed seed),
minimising distance to a target RTP with the bonus trigger as a soft band.

## Porting to a client

The client needs only `config/*.json` and two rules:

- **Line win** — for each payline, take one row per reel; count the run from
  reel 1 where each symbol is the paying symbol or a wild; pay the highest-value
  symbol that qualifies.
- **Scatter** — count Bonus anywhere in the 3x5 window; pay as a multiple of
  total bet.

`simulate.evaluate_window` is the reference implementation, in 30 lines.

Do not re-derive odds in the client. If the client rolls its own randomness the
RTP figures here stop being true of the shipped game — which is exactly how the
2015 build ended up with unknown odds.
