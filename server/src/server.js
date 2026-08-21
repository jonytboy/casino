/**
 * Exuma Casino API. No dependencies: node:http, node:sqlite, node:crypto only.
 *
 * The one rule that shapes everything: the client renders spins, the server
 * decides them. Nothing a browser sends is trusted beyond "which game, what
 * stake" — and even the stake is checked against a fixed list.
 */
import { createServer } from "node:http";
import { createHash, randomBytes, timingSafeEqual, createHmac } from "node:crypto";
import { readFileSync, existsSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import * as store from "./db.js";
import { loadGame, spinWindow, evaluate, exactLineRtp, exactScatterRtp } from "./slots.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..");

export const CONFIG = {
  port: Number(process.env.PORT ?? 8080),
  dbPath: process.env.DB_PATH ?? join(ROOT, "data", "casino.db"),
  startingCoins: Number(process.env.STARTING_COINS ?? 10000),
  freeCoins: Number(process.env.FREE_COINS ?? 2000),
  freeCooldownMs: Number(process.env.FREE_COOLDOWN_MS ?? 15 * 60 * 1000),
  whopSecret: process.env.WHOP_WEBHOOK_SECRET ?? "",
  allowOrigin: process.env.ALLOW_ORIGIN ?? "*",
  // Stakes a client may ask for. Anything else is rejected, so a crafted
  // request cannot bet 0 to farm wins or bet negative to mint coins.
  bets: [1, 2, 5, 10, 25, 50],
  packs: {
    "coins-10k": { coins: 10000, price: "£0.99" },
    "coins-60k": { coins: 60000, price: "£4.99" },
    "coins-200k": { coins: 200000, price: "£9.99" },
  },
};

/* ---------------------------------------------------------------- games ---- */

function loadGames() {
  const games = {};
  const dir = join(ROOT, "games");
  for (const key of ["santa", "pirates"]) {
    const path = join(dir, `${key}.json`);
    if (!existsSync(path)) continue;
    const raw = JSON.parse(readFileSync(path, "utf8"));
    const game = loadGame(raw.cfg, raw.lines);
    game.key = key;
    game.title = raw.title;
    game.rtp = exactLineRtp(game) + exactScatterRtp(game);
    games[key] = game;
  }
  if (!Object.keys(games).length) throw new Error("no game configs found in games/");
  return games;
}

/* ---------------------------------------------------------------- tokens --- */

// The player's token is a bearer credential, so only its hash is stored: a
// leaked database does not hand out accounts.
const hashToken = (t) => createHash("sha256").update(t).digest("hex");
const newToken = () => randomBytes(32).toString("base64url");

function authenticate(db, req) {
  const header = req.headers.authorization ?? "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : null;
  if (!token) return null;
  const player = store.getPlayerByToken(db, hashToken(token));
  if (player) store.touch(db, player.id);
  return player;
}

/* ------------------------------------------------------------------ http --- */

const json = (res, code, body) => {
  const payload = JSON.stringify(body);
  res.writeHead(code, {
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(payload),
    "cache-control": "no-store",
  });
  res.end(payload);
};

async function readBody(req, limit = 64 * 1024) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > limit) throw new Error("body too large");
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

// A small fixed-window limiter. Enough to stop a script hammering spins;
// a real deployment behind a proxy should also rate limit at the edge.
const hits = new Map();
function rateLimit(key, max, windowMs) {
  const t = Date.now();
  const e = hits.get(key);
  if (!e || t > e.reset) { hits.set(key, { n: 1, reset: t + windowMs }); return true; }
  if (e.n >= max) return false;
  e.n++;
  return true;
}
setInterval(() => {
  const t = Date.now();
  for (const [k, e] of hits) if (t > e.reset) hits.delete(k);
}, 60_000).unref?.();

/* ---------------------------------------------------------------- routes --- */

export function createApp(db, games) {
  const publicGame = (g) => ({
    key: g.key, title: g.title, rtp: g.rtp,
    lines: g.lines, cfg: g.cfg,
  });

  return async function handle(req, res) {
    const url = new URL(req.url, `http://${req.headers.host ?? "localhost"}`);
    const path = url.pathname;
    const ip = req.headers["x-forwarded-for"]?.split(",")[0].trim() ?? req.socket.remoteAddress ?? "?";

    res.setHeader("access-control-allow-origin", CONFIG.allowOrigin);
    res.setHeader("access-control-allow-headers", "authorization, content-type");
    res.setHeader("access-control-allow-methods", "GET, POST, OPTIONS");
    if (req.method === "OPTIONS") return res.writeHead(204).end();

    try {
      if (path === "/api/health") return json(res, 200, { ok: true });

      /* Issue or restore a player. A client with no token gets a new account
         and a welcome balance; a client with one gets its balance back. */
      if (path === "/api/session" && req.method === "POST") {
        if (!rateLimit(`sess:${ip}`, 30, 60_000)) return json(res, 429, { error: "slow_down" });
        let player = authenticate(db, req);
        let token = null;
        if (!player) {
          token = newToken();
          player = store.createPlayer(db, hashToken(token), CONFIG.startingCoins);
        }
        return json(res, 200, {
          token,
          coins: player.coins,
          freeReadyAt: player.last_free_at + CONFIG.freeCooldownMs,
          bets: CONFIG.bets,
          games: Object.values(games).map(publicGame),
          packs: CONFIG.packs,
        });
      }

      if (path === "/api/me" && req.method === "GET") {
        const player = authenticate(db, req);
        if (!player) return json(res, 401, { error: "no_session" });
        return json(res, 200, {
          coins: player.coins,
          freeReadyAt: player.last_free_at + CONFIG.freeCooldownMs,
        });
      }

      /* The spin. The client says which game and how much; the server does
         everything else and reports the result. */
      if (path === "/api/spin" && req.method === "POST") {
        const player = authenticate(db, req);
        if (!player) return json(res, 401, { error: "no_session" });
        if (!rateLimit(`spin:${player.id}`, 240, 60_000)) return json(res, 429, { error: "slow_down" });

        let body;
        try { body = JSON.parse((await readBody(req)).toString() || "{}"); }
        catch { return json(res, 400, { error: "bad_json" }); }

        const game = games[body.game];
        if (!game) return json(res, 400, { error: "unknown_game" });
        // Strict: the bet must arrive as a JSON number and be one this server
        // offers. Coercing "2" would work, but at a boundary that moves money
        // it is better to refuse anything that is not exactly what was meant.
        const betPerLine = body.betPerLine;
        if (typeof betPerLine !== "number" || !Number.isFinite(betPerLine) ||
            !CONFIG.bets.includes(betPerLine)) {
          return json(res, 400, { error: "bad_bet", allowed: CONFIG.bets });
        }

        const stake = betPerLine * game.lines.length;
        const window = spinWindow(game.cfg);
        const result = evaluate(game, window, betPerLine);
        const balance = store.applySpin(db, player.id, game.key, stake, result.win);
        if (balance === null) return json(res, 402, { error: "insufficient_coins", coins: player.coins });

        return json(res, 200, {
          window, stake, coins: balance,
          win: result.win, lit: result.lit,
          scatters: result.scatters, freeSpins: result.freeSpins,
        });
      }

      if (path === "/api/free" && req.method === "POST") {
        const player = authenticate(db, req);
        if (!player) return json(res, 401, { error: "no_session" });
        const r = store.claimFree(db, player.id, CONFIG.freeCoins, CONFIG.freeCooldownMs);
        if (!r.ok) return json(res, 429, { error: "too_soon", waitMs: r.waitMs });
        return json(res, 200, { coins: r.balance, freeReadyAt: Date.now() + CONFIG.freeCooldownMs });
      }

      /* Payment webhook. Signature first, then idempotency, then credit. */
      if (path === "/api/webhook/whop" && req.method === "POST") {
        const raw = await readBody(req);
        if (!CONFIG.whopSecret) return json(res, 503, { error: "webhook_not_configured" });

        const sent = req.headers["x-whop-signature"] ?? "";
        const expected = createHmac("sha256", CONFIG.whopSecret).update(raw).digest("hex");
        const a = Buffer.from(String(sent));
        const b = Buffer.from(expected);
        if (a.length !== b.length || !timingSafeEqual(a, b)) {
          return json(res, 401, { error: "bad_signature" });
        }

        let event;
        try { event = JSON.parse(raw.toString()); } catch { return json(res, 400, { error: "bad_json" }); }

        // Field names differ between providers and plan types; map them here
        // rather than scattering the provider's shape through the codebase.
        const eventId = event.id ?? event.event_id;
        const data = event.data ?? event;
        const packId = data.metadata?.pack_id ?? data.plan_id;
        const playerId = data.metadata?.player_id;
        const pack = CONFIG.packs[packId];

        if (!eventId) return json(res, 400, { error: "missing_event_id" });
        if (!pack) return json(res, 400, { error: "unknown_pack", packId });
        if (!playerId) return json(res, 400, { error: "missing_player_id" });

        const r = store.creditPurchase(db, eventId, playerId, packId, pack.coins, raw.toString());
        if (!r.ok) return json(res, 202, { accepted: true, credited: false, reason: r.reason });
        return json(res, 200, { credited: !r.duplicate, duplicate: !!r.duplicate });
      }

      /* Realised return per game, so the advertised figure can be checked
         against what players actually got. */
      if (path === "/api/stats" && req.method === "GET") {
        const rows = store.gameStats(db).map((r) => ({
          game: r.game, spins: r.spins,
          staked: r.staked, returned: r.returned,
          realisedRtp: r.staked ? r.returned / r.staked : null,
          publishedRtp: games[r.game]?.rtp ?? null,
        }));
        return json(res, 200, { games: rows });
      }

      return json(res, 404, { error: "not_found" });
    } catch (err) {
      console.error("[error]", path, err?.message);
      return json(res, 500, { error: "server_error" });
    }
  };
}

export function start() {
  mkdirSync(dirname(CONFIG.dbPath), { recursive: true });
  const db = store.open(CONFIG.dbPath);
  const games = loadGames();
  const server = createServer(createApp(db, games));
  server.listen(CONFIG.port, () => {
    const list = Object.values(games).map((g) => `${g.key} ${(g.rtp * 100).toFixed(2)}%`).join(", ");
    console.log(`exuma-casino api on :${CONFIG.port}  [${list}]`);
    if (!CONFIG.whopSecret) console.warn("WHOP_WEBHOOK_SECRET unset — purchases will be refused");
  });
  return server;
}
