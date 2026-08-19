# casino

Recovery and modernisation of a portfolio of 2015-era mobile slot games.

## Portfolio

Source lives in Dropbox under `/Old Files/Websites & Apps/AR Android/`:

| game | engine | platforms | status |
|---|---|---|---|
| Pirate Slots | cocos2d-android (Java) | Android | APK decompiled, maths modelled |
| Santa Slots | **Construct 2 (HTML5)** | iOS + Android | event sheets read, maths estimated |
| 777 Mega Slot | unknown | iOS | not yet examined |
| Android Roulette | unknown | Android | not yet examined |
| XO Roulette | unknown | — | not yet examined |
| Vegas Casino Roulette | unknown | iOS | not yet examined |
| Unity Slots | Unity (SlotCreatorPro) | — | not yet examined |

Santa Slots reportedly performed best commercially, and it shipped as a **paid**
app (`santaslotpaid.capx`). It is also the only one already on an HTML5 engine,
which makes it the cheapest to revive and the only one with a real migration
path (Construct 3 imports Construct 2 projects).

## The problem both games share

Neither game has a defined RTP. Both pick symbols with a uniform random call and
no reel strips, so the payout percentage is an emergent side effect of the spin
code rather than a designed number:

- **Pirate Slots** — `Math.random()` at ~20 sites across a 4,364-line
  `GameLayer.java`; the paytable existed only as UI label text.
- **Santa Slots** — `floor(random(0,14))` per cell, uniform over 15 symbols;
  the paytable is a separate `prizes.xml`.

Measured against their own paytables, both pay far under the 92-96% band players
and stores expect:

| game | measured RTP | notes |
|---|---|---|
| Pirate Slots | **68.40%** | exact |
| Santa Slots | **47.47%** | exact, from the shipped `prizes.xml` |

Santa Slots — the game that sold best — returns **47.47%**. A player staking
£100 gets back about £47. Both games were built to pay roughly half to two
thirds of what the market expects.

An undefined RTP blocks every commercial route: you cannot state your odds to a
store, tune monetisation against it, or license the content to an operator.

## What is here

`math/` — an engine-independent model of the slot maths. The maths lives as
**data** (`config/*.json`) plus a verifier, so any client (Unity, Godot, HTML5)
consumes the same reel strips and paytable and provably pays the same.

Everything is computed exactly, three ways, cross-checked so an error in one is
caught by the others:

1. **Win-tensor contraction** — the full `|S|^5` win tensor is built once, so
   each evaluation is a contraction against per-reel probabilities. ~3ms.
2. **Full enumeration** — every reel-stop combination. Needed because hit rate,
   unlike RTP, cannot be derived from per-line probabilities: paylines overlap
   on the same 15 visible symbols. Assuming independence overstated the hit rate
   by 34 points. Cost is `(strip length)^5`, so it is guarded by `max_windows`.
3. **Monte Carlo** — actually spins the reels.

Routes 1 and 2 agree to 1e-9; route 3 lands within sampling error.

```bash
pip install numpy
python3 math/tests/test_math.py                          # 8 tests
python3 math/pirates/report.py math/pirates/config/pirates-v3.json
python3 math/santa/santa_exact.py
```

See `math/pirates/README.md` for the recovered Pirate Slots paytable and the
three tuned configs (all solved to 94.00% RTP, differing in feel not in cost).

## Santa Slots findings

Read directly from the Construct 2 project via the Dropbox connector.

- **5x3 grid, 20 paylines, 14 symbols** (ids 0-13; only 0-12 pay), uniform
  RNG per cell — `floor(random(0,14))`.
- **Line 8 is an exact duplicate of line 3** (both `(0,0,0,0,0)`, the top row).
  This is RTP-neutral, since the player stakes for that line too — but it means
  lines 3 and 8 always win and lose together, which raises variance and wastes a
  payline slot that could have been a distinct pattern.
- **Top award is 5000x line bet on `card0`** — 285x total bet, against Pirate
  Slots' 51x. The best headline number in the portfolio.
- **Four symbols pay from 2 of a kind** (`card0`, `card9`, `card10`, `card11`),
  but the LDW rate is only 7.4% — far healthier than Pirates' 20.7%, because
  14 uniform symbols make two-of-a-kind much rarer than Pirates' setup did.
- Bonus is a pick-a-box awarding `choose(10,15,20,25) * line_bet * lines`.
- Credits persist in `WebStorage.LocalValue("credits")` — i.e. browser local
  storage, trivially editable by the player. Fine for a paid offline game,
  unacceptable if anything of value is ever attached to the balance.

- **`card12`'s paytable is reversed.** It reads 3-of-a-kind = 100, 4 = 10,
  5 = 3, so a better outcome pays less. Almost certainly the three values were
  entered backwards. Note the direction of the error: because 3-of-a-kind is far
  commoner than 5, the bug *over*-pays. Un-reversing it to 3/10/100 drops RTP
  from 47.47% to 44.21%, so the shipped game is accidentally more generous than
  intended — correcting it in isolation makes the game worse for the player.

Nothing above is inferred. The paytable comes from `Files/prizes.xml`, the
paylines from the 20 `checkLine` calls in `Event sheets/game.xml`, and the
uniform reel model from that same file's `floor(random(0,14))`. An earlier
estimate of ~61% in this repo's history was wrong: it guessed 15 symbols and a
scatter component that does not exist.

## Known blockers

- **Binary downloads from Dropbox are blocked.** `dl.dropboxusercontent.com` is
  denied by this environment's egress policy, so APKs and the source `.zip`s
  cannot be pulled in. Text files read fine, which is how the Santa Slots event
  sheets were recovered. Fixing this needs the host allowed in the egress policy.
- Most source is inside `.zip` archives, which the text-extraction path cannot
  open. Santa Slots is the exception — its source is unzipped in Dropbox.

## Next

1. Solve Santa Slots reel strips to a target RTP, as already done for Pirates.
   This means introducing reel strips at all — there are none today.
2. Sweep the remaining five games' Dropbox folders for unzipped source.
3. Decide the shipping engine. Santa Slots being Construct 2 argues for HTML5.
