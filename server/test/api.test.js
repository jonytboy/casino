import test from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import * as store from "../src/db.js";
import { loadGame, exactLineRtp, exactScatterRtp } from "../src/slots.js";
import { createApp, CONFIG } from "../src/server.js";

const GAMES_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "games");
function harness() {
  const db = store.open(":memory:");
  const games = {};
  for (const k of ["santa", "pirates"]) {
    const raw = JSON.parse(readFileSync(join(GAMES_DIR, `${k}.json`), "utf8"));
    const g = loadGame(raw.cfg, raw.lines);
    g.key = k; g.title = raw.title;
    g.rtp = exactLineRtp(g) + exactScatterRtp(g);
    games[k] = g;
  }
  const server = createServer(createApp(db, games));
  return { db, server };
}

async function listen(server) {
  await new Promise((r) => server.listen(0, r));
  return `http://127.0.0.1:${server.address().port}`;
}
const call = (base, path, opts = {}) =>
  fetch(base + path, opts).then(async (r) => ({ status: r.status, body: await r.json() }));

test("a new client gets a session, a token and a starting balance", async (t) => {
  const { server } = harness();
  const base = await listen(server);
  t.after(() => server.close());
  const { status, body } = await call(base, "/api/session", { method: "POST" });
  assert.equal(status, 200);
  assert.ok(body.token, "a token is issued");
  assert.equal(body.coins, CONFIG.startingCoins);
  assert.ok(body.games.length >= 1);
});

test("spinning moves the balance, and the server decides the outcome", async (t) => {
  const { server } = harness();
  const base = await listen(server);
  t.after(() => server.close());
  const { body: s } = await call(base, "/api/session", { method: "POST" });
  const auth = { authorization: `Bearer ${s.token}`, "content-type": "application/json" };

  const { status, body } = await call(base, "/api/spin", {
    method: "POST", headers: auth,
    body: JSON.stringify({ game: "santa", betPerLine: 2 }),
  });
  assert.equal(status, 200);
  assert.ok(Array.isArray(body.window), "the server returns the window it rolled");
  assert.equal(body.coins, s.coins - body.stake + body.win);
});

test("a client cannot invent its own stake", async (t) => {
  const { server } = harness();
  const base = await listen(server);
  t.after(() => server.close());
  const { body: s } = await call(base, "/api/session", { method: "POST" });
  const auth = { authorization: `Bearer ${s.token}`, "content-type": "application/json" };
  for (const bet of [0, -5, 1e9, 2.5, "2"]) {
    const { status } = await call(base, "/api/spin", {
      method: "POST", headers: auth, body: JSON.stringify({ game: "santa", betPerLine: bet }),
    });
    assert.equal(status, 400, `bet ${bet} must be refused`);
  }
});

test("spinning without a session is refused", async (t) => {
  const { server } = harness();
  const base = await listen(server);
  t.after(() => server.close());
  const { status } = await call(base, "/api/spin", {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ game: "santa", betPerLine: 2 }),
  });
  assert.equal(status, 401);
});

test("a player cannot overdraw", async (t) => {
  const { db, server } = harness();
  const base = await listen(server);
  t.after(() => server.close());
  const { body: s } = await call(base, "/api/session", { method: "POST" });
  const auth = { authorization: `Bearer ${s.token}`, "content-type": "application/json" };
  const me = db.prepare("SELECT id FROM players LIMIT 1").get();
  db.prepare("UPDATE players SET coins = 10 WHERE id = ?").run(me.id);
  const { status, body } = await call(base, "/api/spin", {
    method: "POST", headers: auth, body: JSON.stringify({ game: "santa", betPerLine: 50 }),
  });
  assert.equal(status, 402);
  assert.equal(body.error, "insufficient_coins");
});

test("the free top-up honours its cooldown", async (t) => {
  const { server } = harness();
  const base = await listen(server);
  t.after(() => server.close());
  const { body: s } = await call(base, "/api/session", { method: "POST" });
  const auth = { authorization: `Bearer ${s.token}` };
  const first = await call(base, "/api/free", { method: "POST", headers: auth });
  assert.equal(first.status, 200);
  assert.equal(first.body.coins, s.coins + CONFIG.freeCoins);
  const second = await call(base, "/api/free", { method: "POST", headers: auth });
  assert.equal(second.status, 429, "a second claim inside the window is refused");
});

test("a webhook without a valid signature credits nothing", async (t) => {
  const { server } = harness();
  const base = await listen(server);
  t.after(() => server.close());
  CONFIG.whopSecret = "test-secret";
  t.after(() => { CONFIG.whopSecret = ""; });
  const { status } = await call(base, "/api/webhook/whop", {
    method: "POST",
    headers: { "content-type": "application/json", "x-whop-signature": "deadbeef" },
    body: JSON.stringify({ id: "evt_1", data: {} }),
  });
  assert.equal(status, 401);
});

test("a replayed webhook credits the purchase only once", async (t) => {
  const { db, server } = harness();
  const base = await listen(server);
  t.after(() => server.close());
  CONFIG.whopSecret = "test-secret";
  t.after(() => { CONFIG.whopSecret = ""; });

  const { body: s } = await call(base, "/api/session", { method: "POST" });
  const player = db.prepare("SELECT id, coins FROM players LIMIT 1").get();
  const payload = JSON.stringify({
    id: "evt_repeat",
    data: { metadata: { pack_id: "coins-10k", player_id: player.id } },
  });
  const sig = createHmac("sha256", "test-secret").update(payload).digest("hex");
  const send = () => call(base, "/api/webhook/whop", {
    method: "POST",
    headers: { "content-type": "application/json", "x-whop-signature": sig },
    body: payload,
  });

  const first = await send();
  assert.equal(first.status, 200);
  assert.equal(first.body.credited, true);

  const again = await send();
  assert.equal(again.body.duplicate, true, "the replay is recognised");
  assert.equal(again.body.credited, false);

  const after = db.prepare("SELECT coins FROM players WHERE id = ?").get(player.id);
  assert.equal(after.coins, player.coins + CONFIG.packs["coins-10k"].coins,
    "credited exactly once");
});
