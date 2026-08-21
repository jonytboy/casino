# Casino Carib — API

The authoritative half of the casino. **The client renders spins; this server
decides them.** Nothing a browser sends is trusted beyond which game and which
stake, and even the stake is checked against a fixed list.

That is the whole reason this exists. The lobby's original wallet lived in
`localStorage`, which a player can edit — fine for play money, useless the
moment coins are sold, because anything on sale could equally be minted for
free. Balances live here now.

## No dependencies

`node:http`, `node:sqlite` and `node:crypto` only. There is no `npm install`,
no lockfile and no native build — which also means nothing to audit and nothing
to keep patched. Requires **Node 22.5+** for `node:sqlite`.

    cp .env.example .env      # then fill it in
    npm start                 # or: node index.js
    npm test                  # 16 tests

The server also hosts the game. Build the page first or `/` answers 503:

    python3 ../build_web.py serve     # writes public/index.html

Docker:

    docker build -t exuma-casino .
    docker run -p 8080:8080 -v exuma-data:/data --env-file .env exuma-casino

`/data` must be a volume. It holds the balances.

Fly.io, which `fly.toml` is written for:

    fly launch --no-deploy
    fly volumes create casino_data --size 1 --region lhr
    fly deploy

One machine, on purpose — the balances are a SQLite file on that volume, and two
machines cannot share one. Scale by giving the machine more CPU.

Take backups with `scripts/backup.mjs`; see the root README.

## Endpoints

| method | path | purpose |
|---|---|---|
| `POST` | `/api/session` | Issue or restore a player. Returns a bearer token on first call — the client stores it and sends it thereafter. |
| `GET` | `/api/me` | Balance and free-top-up readiness. |
| `POST` | `/api/spin` | `{game, betPerLine}`. The server rolls, evaluates, debits, credits, and returns the window it rolled. |
| `POST` | `/api/free` | Claim the free top-up, cooldown enforced server-side. |
| `POST` | `/api/webhook/whop` | Credit a completed purchase. Signature-checked and idempotent. |
| `GET` | `/api/stats` | Realised return per game against the published figure. |
| `GET` | `/api/health` | Liveness. |
| `GET` | `/` | The game itself, from `public/index.html`. ETagged, gzipped, `no-cache` so a deploy is picked up but a repeat visit costs a 304 rather than a megabyte. |

## What stops the obvious attacks

- **Reporting your own win.** Impossible: the client never sends an outcome. It
  asks for a spin and is told what happened.
- **Betting a negative or absurd stake.** The bet must arrive as a JSON number
  and be one of `[1, 2, 5, 10, 25, 50]`. Anything else is refused, including a
  string `"2"` that would otherwise coerce.
- **Overdrawing by racing two spins.** The balance check and the debit are one
  `BEGIN IMMEDIATE` transaction, so two concurrent spins cannot both pass.
- **Re-claiming the free coins.** The cooldown is stored on the player row and
  checked inside the same transaction that grants it.
- **Replaying a purchase webhook.** The provider's event id is the primary key
  of the `purchases` table, so a replay credits nothing. Providers retry by
  design, so this is a normal event rather than an attack.
- **Forging a purchase.** The webhook body is HMAC-verified against
  `WHOP_WEBHOOK_SECRET` with a constant-time compare. With no secret set the
  endpoint refuses everything with 503 rather than failing open.
- **Stealing tokens from a database dump.** Only the SHA-256 of a token is
  stored.

Not covered, and worth knowing: there is no email recovery, so a player who
loses their browser storage loses the account and anything bought with it. Add
an account-claim flow before charging real money.

## Auditing the odds

The published RTP is not a claim in a README, it is a test. `test/slots.test.js`
computes each game's return exactly — enumerating every symbol combination
weighted by the reel marginals — and fails the build if it drifts from the
figure the lobby advertises. `/api/stats` then shows what players actually got,
so the advertised number can be checked against reality rather than trusted.

## Wiring up Whop

1. Create the coin packs. Their ids must match the keys in `CONFIG.packs`
   (`coins-10k`, `coins-60k`, `coins-200k`) or the webhook rejects them.
2. Point the webhook at `POST /api/webhook/whop` and set the signing secret as
   `WHOP_WEBHOOK_SECRET`.
3. Pass the player's id through checkout as metadata `player_id`, and the pack
   as `pack_id`. Without `player_id` the server records the purchase as
   `orphaned` and credits nobody — deliberately, since guessing which player
   paid is worse than failing loudly.
4. Confirm the header name and payload shape against a real Whop delivery. The
   handler reads `x-whop-signature` and `event.id` / `event.data.metadata`,
   which is the common shape, but it has not been tested against live Whop
   traffic — check one real event before taking money.

One non-technical check first: coins that never convert to money or prizes are
an ordinary product rather than gambling, but payment providers set their own
rules on casino-adjacent content. That is a question for Whop, not an assumption
to build on.
