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

## Play it

- **Pirate Slots:** https://claude.ai/code/artifact/24c0fb37-7050-48bd-81e6-26e9f1e64519
- **Santa Slots:** https://claude.ai/code/artifact/aa8db3cb-2e88-4491-8d7b-e9b5e95348f2
  (original artwork and sound)

Both are built by `build_web.py` from the solved configs, so the reels, paytable
and paylines are the same data the Python model verifies and a page cannot drift
from the measured figures without the build changing. Both carry their original artwork and sound — Pirate Slots' from the APK's
`res/raw`, Santa Slots' from the Construct project.

Each build is checked by replaying its own JavaScript over millions of spins and
comparing against the model. That check is not ceremony: it is what caught the
payline bug described under Santa Slots below.

    python3 build_web.py            # both games
    python3 build_web.py santa      # one game

### Hosting it

`docs/index.html` is the built page, kept byte-identical to
`web/pirates-slot.html` by `build_web.py`. To serve it from this repo:
**Settings → Pages → Source: Deploy from a branch → `main` / `/docs`**. The URL
is then `https://jonytboy.github.io/casino/`.

Two things to know before flipping that switch. GitHub Pages on a *private*
repo needs a paid plan; on a free plan the repo has to be public, which would
publish the analysis and commit history alongside the game. And the page embeds
the artwork as data URIs, so anyone with the URL can extract the symbol PNGs and
the audio — worth weighing, since the art is the asset actually worth something
here.

The page is a single self-contained file with no build step or external
requests, so any static host works equally well: drag `docs/index.html` onto
Netlify Drop, a Cloudflare Pages project, or any web server.

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
| Santa Slots | **229.60%** | exact, verified against the game's own JavaScript |

They fail in opposite directions. Pirate Slots pays **68.40%**, well under the
92-96% band. Santa Slots pays **229.60%** — it returns more than twice what it
takes, because its wild lands one spin in fourteen on every reel.

That was not harmless. These shipped **free, funded by ads** — the paid build
was the same game with the ads removed. In a coin-based slot the highest-value
ad unit is rewarded video, and it is triggered by scarcity: the player runs dry
and is offered coins for an ad view. At 229.60% the balance only ever climbs, so
that prompt never fires.

`math/bankroll.py` measures it. Starting with 10,000 credits at 2 per line:

| game | median spins to broke | runs that never went broke |
|---|---|---|
| Santa — as shipped (229.60%) | never | **120 / 120** |
| Santa — solved (94.00%) | 1,747 | 0 / 120 |
| Pirates — solved (94.00%) | 1,470 | 0 / 120 |

Not one simulated player ran out of credits in the shipped game. The reward-video
loop could not fire, which is a plausible large part of why the portfolio never
earned. Solving to 94% gives roughly 1,500-1,750 spins of runway before the
first ask — long enough to be enjoyed, finite enough to monetise.

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
- **card0 is the wild** and also carries the top award. At 1-in-14 on every
  reel it is the single biggest driver of the shipped game's RTP.
- **Line 8 is an exact duplicate of line 3** (both `(0,0,0,0,0)`, the top row).
  This is RTP-neutral, since the player stakes for that line too — but it means
  lines 3 and 8 always win and lose together, which raises variance and wastes a
  payline slot that could have been a distinct pattern.
- **Four symbols pay from 2 of a kind** — the wild, the reindeer, the sleigh
  and the present (`card0`, `card9`, `card10`, `card11`). `checkLine` hard-codes
  exactly that set, and it matches the `lv="2"` rows in `prizes.xml`.
- Bonus is a pick-a-box awarding `choose(10,15,20,25) * line_bet * lines`.
- Credits persist in `WebStorage.LocalValue("credits")` — i.e. browser local
  storage, trivially editable by the player. Fine for a paid offline game,
  unacceptable if anything of value is ever attached to the balance.

- **A line pays the first non-wild symbol on it, not the best one.** Three
  wilds followed by a low symbol pays that low symbol, not the premium the wilds
  could have completed. This is unusual and costs about a point of RTP against
  the conventional rule, so the engine carries both as an explicit `rule` field.
- **`card11` is drawn as a SCATTER and `card13` as a BONUS**, but `checkLine`
  treats card11 as an ordinary left-to-right symbol — the scatter label is
  decorative. card13 has no entry in `prizes.xml`, so it pays nothing on a line
  and exists to drive the separate pick-a-box round, which is not yet modelled.
- **`card12`'s paytable is reversed.** It reads 3-of-a-kind = 100, 4 = 10,
  5 = 3, so a better outcome pays less. Almost certainly the three values were
  entered backwards. Because 3-of-a-kind is far commoner than 5, the bug
  *over*-pays: un-reversing it to 3/10/100 drops the shipped RTP from 229.60% to
  208.95%.

Nothing above is inferred. The paytable comes from `Files/prizes.xml`, the
paylines from the 20 `checkLine` calls in `Event sheets/game.xml`, and the
uniform reel model from that same file's `floor(random(0,14))`. An earlier
estimate of ~61% in this repo's history was wrong: it guessed 15 symbols and a
scatter component that does not exist.

## Play Store position (checked 19 Aug 2026)

Social casino apps are permitted on Google Play. This was verified against live
listings rather than policy text: Slotomania (`air.com.playtika.slotomania`)
has current Play listings including en_GB, and Jackpot Party is the top-grossing
casino app on Android. Aggregator sites quote a line reading "apps must not
provide simulated gambling content" as though it were a blanket ban; it cannot
be, given the above, and appears to be lifted out of the real-money gambling
policy or a country-scoped restriction.

The certification whose standards change on **26 August 2026** is a **Google Ads**
certification — it governs whether a social casino game can be *advertised*
through Google Ads, not whether it can be *listed* on Play. It only matters if
paid user acquisition is on the table, which the economics above argue against
anyway.

What does apply to publishing:

- an 18+ content rating for simulated gambling, and no targeting of minors
- disclosure of odds for any randomised virtual item sold for money (this game
  sells coins outright, so it is likely not triggered)
- country restrictions on where the app may be distributed
- **target API 36 from 31 August 2026** for new apps and updates — the real
  hard deadline, and the reason the cocos2d build cannot simply be re-uploaded
- a 12-tester, 14-day closed test before production access on new personal
  developer accounts

Worth noting alongside this: the sector is under active press and regulatory
scrutiny in 2026, including a Bloomberg investigation into social casino
monetisation. Relevant when deciding how hard to lean on the LDW-heavy
configurations recorded above.

### The signing key is a third party's

`META-INF/CERT.RSA` in the shipped APK is signed by:

    CN=mrinmoy, OU=amj, O=amj, L=kol, ST=wb, C=in   (Kolkata, India)
    SHA1 C2:55:7C:B9:45:91:7D:9E:08:DA:8D:0D:FC:BB:68:17:7C:62:99:98
    valid 2014-11-04 to 2042-03-22, 2048-bit RSA, SHA1withRSA

That is the original development agency, not the account holder. It matters
because an update to an existing Play listing must be signed with the same key.
Without that keystore, `com.jonty.caribbeanslots` cannot be updated in place.

The escape hatch is Play App Signing: if the app was enrolled, Google holds the
app signing key and only the upload key is needed, which support can reset.
Play App Signing became the default for new apps in 2021, so a 2015 title is
unlikely to be enrolled unless it was opted in later. Worth checking under
**Play Console -> the app -> Test and release -> App integrity**.

If neither the keystore nor Play App Signing is available, the game has to ship
under a new package name. Published package names can never be reused, so the
old listing, its reviews and its install base are lost. Not fatal — the client
is a rewrite regardless — but it is the difference between updating a listing
and starting one from zero, and it matters most for whichever title actually
had an audience.

## Known blockers

- **Binary downloads from Dropbox are blocked.** `dl.dropboxusercontent.com` is
  denied by this environment's egress policy, so APKs and the source `.zip`s
  cannot be pulled in. Text files read fine, which is how the Santa Slots event
  sheets were recovered. Fixing this needs the host allowed in the egress policy.
- Most source is inside `.zip` archives, which the text-extraction path cannot
  open. Santa Slots is the exception — its source is unzipped in Dropbox.

## Santa Slots solved to 94%

`math/santa/santa_tune.py` introduces reel strips — the shipped game has none —
and solves their composition. The paytable is left exactly as shipped, including
`card12`'s reversed values, so the game keeps its identity; only symbol
frequency changes.

| metric | as shipped | solved |
|---|---|---|
| RTP | 229.60% | **94.00%** |
| any-win rate | 40.09% | 30.28% |
| net-win rate | 28.36% | 16.95% |
| LDW rate | 11.72% | 13.33% |
| max win | 546x | **900x** |

Two earlier revisions of this table were wrong, both caught the same way — by
building the playable page and finding its JavaScript disagreed with the model:

1. `evaluate()` took a line *count* and enumerated against the default 30-line
   set, so Santa's 20-line game was measured over Pirate Slots' paylines. RTP is
   invariant to the line count, so the figure being used as the cross-check was
   the one metric incapable of catching it.
2. Worse: **card0 is the wild**, and it was modelled as an ordinary symbol. The
   artwork says WILD on it, and the event sheet's JavaScript confirms the
   mechanic. That alone moved the shipped game's RTP from a reported 47.47% to
   an actual 229.60%.

`math/santa/verify_against_game.py` now transcribes the shipped `checkLine`
function and compares it against the model across all 537,824 possible lines.
It reports zero mismatches, so the model is the game rather than an
approximation of it.

Both figures are exact — the solved config is enumerated over all 40^5 =
102,400,000 windows, not sampled.

Two things are worth understanding about that table.

**RTP alone is not a design target.** The first solve hit 94.00% with a reel
that paid on one spin in five: it had loaded two mid-value symbols to the cap
and minimised the cheap ones. Correct arithmetic, unplayable game. The tuner now
takes a per-line hit-rate band alongside the RTP target, which is what moves
any-win from 18.6% to 30.3%. LDW rises with it — more frequent small wins means
more wins below stake — but at 13.1% it stays well under Pirate Slots' 20.7%.

**The top award comes from stacking, not from tuning.** An earlier solve
reached 94% with a max win of only 175x, because `build_strip` spaced repeats
evenly and no premium ever stacked — and a large top win needs one symbol
filling all three visible rows of a reel at once. `card0` is now fixed at 3 per
reel and laid down as a contiguous block, so exactly one stop in 40 fills a reel
with it. Five such stops together pay the 5000x top award, at odds of about
**1 in 102,400,000 spins** — normal rarity for an advertised maximum.

Stacking is free in RTP terms, which is worth knowing: line wins depend only on
each reel's marginal symbol frequency, and that is count/length however the
symbols are arranged. Stacking changes the joint distribution across rows, not
the mean. `test_stacking_does_not_change_rtp` pins this.

**The remaining weakness is the LDW rate**, which rose from 13.1% to 20.9% —
now level with Pirate Slots. The cause is `card1` sitting at 12-14 positions per
reel: it is what lifts the any-win rate to 40%, but its 3-of-a-kind pays 5
against a 20-line stake, so those frequent wins return less than they cost. This
is not fixable by moving symbols around. The clean fix is a paytable change —
raise the cheap symbols' 3-of-a-kind above the stake — which would be the first
deliberate departure from the game as shipped.

## Next

1. Model Santa's pick-a-box bonus round. `BONUS.xml` awards
   `choose(10,15,20,25) * line_bet * lines` per opened box, which is large
   enough to matter, and it is currently outside the RTP figure entirely.
2. Confirm Pirate Slots' win rule from the decompiled cocos2d source. It is
   assumed to be `best`; Santa's turned out not to be, so the assumption is
   worth checking rather than trusting.
3. Recover the remaining four games' source.
4. Decide the shipping engine. Santa Slots being Construct 2 argues for HTML5.
