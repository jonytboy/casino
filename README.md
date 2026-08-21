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

- **Casino Carib (the lobby):** https://claude.ai/code/artifact/9ba2a514-793f-4cc4-9f83-606d979d9306
  Both machines, one shared purse. This is the demo build and labels itself as
  one; the live build is served by the API (see Hosting it).
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

### Two modes: demo and live

The lobby is built twice from the same source.

With no `CASINO_API` set, the page spins in the browser and keeps the purse in
`localStorage`. That is right for play money — private to each browser, survives
a reload, needs no accounts — and exactly wrong for anything sold, because a
player can edit it. So that build labels itself **demo · local play** in the top
bar and the coin packs stay inert.

    python3 build_web.py hub                                  # demo build

The live build never computes an outcome. It asks for every spin, the server
draws it and moves the balance, and the reels only animate a result that is
already committed. That build says **live**, and if the API is unreachable at
load it falls back to local play and relabels itself rather than showing a
balance that means nothing.

    python3 build_web.py serve                                # live build

`serve` writes `server/public/index.html`, which the server hosts itself — so
its API is its own origin and there is nothing to configure. `CASINO_API` exists
for the other case, hosting the page somewhere else:

    CASINO_API=https://api.example.com python3 build_web.py hub

An empty API means same origin and a null one means demo, which is why the page
tests it against null rather than for truthiness — `""` is an answer, not an
absence.

`server/` is the authoritative half: accounts, server-held balances, a ledger
every movement is written to, and a Whop webhook that credits coins after a
completed charge. See `server/README.md`. Until a checkout exists,
`build_web.py`'s `STORE["checkoutBase"]` is `None`, the pack buttons are inert
and say so, and the free top-up carries the game.

Worth checking before taking money: coins that never convert to money or prizes
are not gambling and are a normal product, but payment providers set their own
rules on casino-adjacent content, and that is a question for the provider rather
than an assumption.

### Hosting it

There are two ways to run this, and the cheap one is the right one until coins
cost money.

**Static, free, no server.** `python3 build_web.py static` writes
`dist/index.html`: the whole lobby as one self-contained file with no build
step, no external requests and no backend. Drop that folder on Cloudflare
Pages, Netlify, or any static host and it plays. The purse lives in the browser
and the page labels itself **demo · local play**, which is honest and costs
nothing.

This is the entire product for as long as nothing is sold. What a server buys
is a balance worth protecting — one that survives a cleared browser, follows a
player between devices, and cannot be edited. None of that matters while the
coins are free, and all of it matters the moment they are not.

**Server-hosted, when there is money to protect.** `python3 build_web.py serve`
writes `server/public/index.html` — the same lobby with its API set to its own
origin — and the server serves it at `/`. One deploy rather than two, which
removes a class of mistake: a page only ever served by the API it talks to
cannot be deployed pointing at a stale API, or somebody else's, and there is no
CORS to get wrong because there is no cross origin.

`server/deploy/` is a whole VPS deployment — the game, Caddy in front of it for
TLS, and a script that ships both. On a fresh Hetzner box with Docker:

    # once, on the server
    mkdir -p /opt/casino && cd /opt/casino
    #   copy server/deploy/.env.example here as .env and fill in DOMAIN
    #   point a DNS A record at the box first: Caddy gets the certificate on
    #   first start, and it cannot do that for a name that does not resolve

    # from your machine, every time
    server/deploy/deploy.sh root@casinocarib.com

The compose file bind-mounts `./data` rather than using a named volume, so the
balances are an ordinary directory you can see, copy and cron. `deploy.sh`
excludes `data/` from its rsync `--delete`, which is the one line standing
between a routine deploy and wiping every player's coins.

Caddy renews the certificate itself; there is no certbot step and no renewal
cron to forget. `docker compose up -d` and `restart: unless-stopped` cover
reboots.

`server/fly.toml` is committed too if you would rather not run a box. Whichever
you pick, it is one machine: the balances are a SQLite file on a disk, and two
machines cannot share one — scale by giving the machine more CPU, never by
adding machines. That disk is the part that is not free anywhere, because it is
the part that is real.

Rebuild the page whenever the maths or the artwork changes:

    python3 build_web.py static                       # static host
    server/deploy/deploy.sh root@casinocarib.com   # server host

### Backing up the balances

The volume is the only thing here that cannot be regenerated. `build_web.py`
rebuilds every page from the configs, the configs are in git, the artwork is in
`assets/` — but the balances exist in exactly one place.

    # on the VPS — server/deploy/backup.cron installs this nightly
    cd /opt/casino && docker compose exec -T api node scripts/backup.mjs /data/backups 14
    scp root@casinocarib.com:/opt/casino/data/backups/casino-....db .

    # or on Fly
    fly ssh console -C "node /app/scripts/backup.mjs /data/backups 14"

`scripts/backup.mjs` uses SQLite's `VACUUM INTO`, which snapshots a live
database consistently without stopping writes — `cp` on a running database can
hand you a torn file that looks fine until the day you need it. It then reopens
the snapshot and reports the player count and coin total, because a backup
nobody has opened is a guess. Run it on a schedule you can live with losing.

## The problem both games share

**Both games shipped paying out more than they took.** That is the finding that
matters, and it is portfolio-wide.

- **Santa Slots** has no reel strips at all: `floor(random(0,14))` fills each
  cell uniformly from 14 symbols, and card0 — the wild — lands one spin in
  fourteen on every reel. **229.60%**.
- **Pirate Slots** *does* have reel strips, hardcoded as five 20-symbol arrays
  in `checkIfWon()`. Its paytable and win rule are in the same method. **103.66%**.

An earlier version of this file claimed Pirate Slots had no strips and returned
68.40%. Both were wrong. The `Math.random()` calls drive the spin animation, not
the symbol layout, and the 68.40% was this project's own invented strips measured
against the real paytable — a statement about a reconstruction, not about the
shipped game. The real strips are now committed at
`math/pirates/config/pirates-as-shipped.json`.

Pirate Slots' rule pays **reel 1's symbol**, with wilds substituting on reels
2-5 (`r13.indexOf(r22)` where r22 is the first reel). Reel 1 carries no Wild, so
that is identical to Santa's leftmost-non-wild rule, and identical to the "best
symbol" rule this project had assumed — the assumption was harmless here, but
only by luck of the strip design.

The code also confirms the paytable recovered from the in-game paytable screen,
value for value.

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

80 sessions per game, capped at 25,000 spins:

| game | median spins to broke | never went broke |
|---|---|---|
| Pirates — as shipped (103.66%) | 5,158 | **79 / 80** |
| Santa — as shipped (229.60%) | never | **80 / 80** |
| Santa — solved (94.00%) | 1,689 | 3 / 80 |
| Pirates — solved (94.00%) | 1,574 | 0 / 80 |

As shipped, almost no simulated player ever ran out of credits — none at all in
Santa Slots. The prompt that drives rewarded video could not fire, which is a
plausible large part of why a portfolio with the ad SDKs already wired in never
earned. Solved to 94%, the same bank lasts a median 1,574-1,689 spins: long
enough to enjoy, finite enough to monetise.

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

## Account status (Play Console, checked 19 Aug 2026)

Developer account **Exuma Trading LTD** (personal account, 8 apps). Every one of
the eight reads **Removed by Google**, and the installed audience is 0 on all of
them bar one.

| app | package | status | last updated |
|---|---|---|---|
| Casino Pirates Vegas Slots | `com.jonty.caribbeanslots` | Removed by Google | 9 Nov 2021 |
| Santa Slots Christmas Casino | `com.tigamedev.santaslots` | Removed by Google | 9 Nov 2021 |
| Santa Slot Xmas Slot Machine | `com.tigamedev.santaslotspaid` | Removed by Google | 9 Nov 2021 |
| Casino Vegas Roulette | `com.xo.roulette` | Removed, **app rejected** | 4 Jan 2021 |
| Casino Vegas Roulette Free | `com.xo.roulettefree` | Removed, **app rejected** | 4 Jan 2021 |
| Beach Hut iManager | `com.app.app44429d9df7dc` | Removed by Google | 30 Sep 2015 |
| Stock Ordering Form JT Leisure | `com.app.appede3cc882c5d` | Removed by Google | 6 Jan 2016 |
| Zoom Sunset Shopping | `com.wZoom_8619566` | Removed by Google | 20 Feb 2019 |

What this settles:

- **There is no install base to preserve.** The earlier concern about the
  third-party signing key blocking an in-place update is moot: with zero
  installs and every listing removed, nothing is lost by publishing fresh. That
  removes the keystore hunt from the critical path entirely.
- **Those package names are burned.** A published package name can never be
  reused, so any relaunch needs new ones.
- **Santa shipped under `com.tigamedev`**, not the account holder's own
  namespace — matching the Pirate Slots APK being signed by a Kolkata agency.
  Both games were built and published by third parties.
- **Two roulette apps were rejected outright** in Jan 2021, which is a caution
  about how the gambling category is reviewed.
- **Removed by Google is not the same as unpublished by the developer.** The
  reason matters: it bears on whether the account is in good standing before
  anything new is submitted. Play Console → Policy status has the detail, and it
  is the first thing to read.

A second deadline also surfaced, separate from the target API one: **Android
developer verification**. Unregistered apps stop being installable on certified
devices in select countries from **September 2026**.

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
