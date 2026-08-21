/**
 * Storage. SQLite via node:sqlite, so the server has no dependencies at all.
 *
 * The balance lives here and nowhere else. Every coin movement is also written
 * to the ledger, so a balance can always be explained: a disputed purchase or a
 * suspicious win is a query, not a guess.
 */
import { DatabaseSync } from "node:sqlite";
import { randomUUID } from "node:crypto";

const SCHEMA = `
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS players (
  id           TEXT PRIMARY KEY,
  token_hash   TEXT NOT NULL UNIQUE,
  email        TEXT UNIQUE,
  coins        INTEGER NOT NULL DEFAULT 0,
  last_free_at INTEGER NOT NULL DEFAULT 0,
  created_at   INTEGER NOT NULL,
  seen_at      INTEGER NOT NULL
);

-- Every movement, so a balance can be reconstructed and explained.
CREATE TABLE IF NOT EXISTS ledger (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  player_id  TEXT NOT NULL REFERENCES players(id),
  kind       TEXT NOT NULL,          -- spin | win | free | purchase | adjust
  amount     INTEGER NOT NULL,       -- signed
  balance    INTEGER NOT NULL,       -- after the movement
  detail     TEXT,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ledger_player ON ledger(player_id, id DESC);

-- Spins are recorded so the published RTP can be audited against reality.
CREATE TABLE IF NOT EXISTS spins (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  player_id  TEXT NOT NULL REFERENCES players(id),
  game       TEXT NOT NULL,
  stake      INTEGER NOT NULL,
  win        INTEGER NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS spins_game ON spins(game, id DESC);

-- Payment events, keyed by the provider's id so a replayed webhook cannot
-- credit the same purchase twice.
CREATE TABLE IF NOT EXISTS purchases (
  event_id   TEXT PRIMARY KEY,
  player_id  TEXT REFERENCES players(id),
  pack_id    TEXT NOT NULL,
  coins      INTEGER NOT NULL,
  status     TEXT NOT NULL,
  raw        TEXT,
  created_at INTEGER NOT NULL
);
`;

export function open(path) {
  const db = new DatabaseSync(path);
  db.exec(SCHEMA);
  return db;
}

const now = () => Date.now();

export function createPlayer(db, tokenHash, startingCoins) {
  const id = randomUUID();
  const t = now();
  db.prepare(
    `INSERT INTO players (id, token_hash, coins, created_at, seen_at)
     VALUES (?, ?, ?, ?, ?)`
  ).run(id, tokenHash, startingCoins, t, t);
  if (startingCoins > 0) {
    recordLedger(db, id, "adjust", startingCoins, startingCoins, "welcome balance");
  }
  return getPlayerById(db, id);
}

export const getPlayerByToken = (db, tokenHash) =>
  db.prepare(`SELECT * FROM players WHERE token_hash = ?`).get(tokenHash);

export const getPlayerById = (db, id) =>
  db.prepare(`SELECT * FROM players WHERE id = ?`).get(id);

export function touch(db, id) {
  db.prepare(`UPDATE players SET seen_at = ? WHERE id = ?`).run(now(), id);
}

export function recordLedger(db, playerId, kind, amount, balance, detail) {
  db.prepare(
    `INSERT INTO ledger (player_id, kind, amount, balance, detail, created_at)
     VALUES (?, ?, ?, ?, ?, ?)`
  ).run(playerId, kind, amount, balance, detail ?? null, now());
}

/**
 * Apply a spin atomically.
 *
 * The stake check and the debit happen inside one transaction, so two spins
 * racing on the same account cannot both pass a balance check and overdraw it.
 * Returns null when the player cannot cover the stake.
 */
export function applySpin(db, playerId, game, stake, win) {
  const tx = db.prepare("BEGIN IMMEDIATE");
  tx.run();
  try {
    const p = getPlayerById(db, playerId);
    if (!p || p.coins < stake) { db.prepare("ROLLBACK").run(); return null; }
    let balance = p.coins - stake;
    db.prepare(`UPDATE players SET coins = ?, seen_at = ? WHERE id = ?`).run(balance, now(), playerId);
    recordLedger(db, playerId, "spin", -stake, balance, game);
    if (win > 0) {
      balance += win;
      db.prepare(`UPDATE players SET coins = ? WHERE id = ?`).run(balance, playerId);
      recordLedger(db, playerId, "win", win, balance, game);
    }
    db.prepare(
      `INSERT INTO spins (player_id, game, stake, win, created_at) VALUES (?, ?, ?, ?, ?)`
    ).run(playerId, game, stake, win, now());
    db.prepare("COMMIT").run();
    return balance;
  } catch (e) {
    try { db.prepare("ROLLBACK").run(); } catch {}
    throw e;
  }
}

/** Grant the free top-up, but only if the cooldown has actually elapsed. */
export function claimFree(db, playerId, coins, cooldownMs) {
  db.prepare("BEGIN IMMEDIATE").run();
  try {
    const p = getPlayerById(db, playerId);
    const t = now();
    if (!p || p.last_free_at + cooldownMs > t) {
      db.prepare("ROLLBACK").run();
      return { ok: false, waitMs: Math.max(0, (p?.last_free_at ?? 0) + cooldownMs - t) };
    }
    const balance = p.coins + coins;
    db.prepare(`UPDATE players SET coins = ?, last_free_at = ?, seen_at = ? WHERE id = ?`)
      .run(balance, t, t, playerId);
    recordLedger(db, playerId, "free", coins, balance, "free top-up");
    db.prepare("COMMIT").run();
    return { ok: true, balance };
  } catch (e) {
    try { db.prepare("ROLLBACK").run(); } catch {}
    throw e;
  }
}

/**
 * Credit a completed purchase, once.
 *
 * Providers retry webhooks, so the provider's event id is the primary key: a
 * replay hits the conflict and credits nothing.
 */
export function creditPurchase(db, eventId, playerId, packId, coins, raw) {
  db.prepare("BEGIN IMMEDIATE").run();
  try {
    const seen = db.prepare(`SELECT event_id FROM purchases WHERE event_id = ?`).get(eventId);
    if (seen) { db.prepare("ROLLBACK").run(); return { ok: true, duplicate: true }; }
    const p = getPlayerById(db, playerId);
    if (!p) {
      db.prepare(
        `INSERT INTO purchases (event_id, player_id, pack_id, coins, status, raw, created_at)
         VALUES (?, NULL, ?, ?, 'orphaned', ?, ?)`
      ).run(eventId, packId, coins, raw ?? null, now());
      db.prepare("COMMIT").run();
      return { ok: false, reason: "unknown_player" };
    }
    const balance = p.coins + coins;
    db.prepare(`UPDATE players SET coins = ? WHERE id = ?`).run(balance, playerId);
    recordLedger(db, playerId, "purchase", coins, balance, packId);
    db.prepare(
      `INSERT INTO purchases (event_id, player_id, pack_id, coins, status, raw, created_at)
       VALUES (?, ?, ?, ?, 'credited', ?, ?)`
    ).run(eventId, playerId, packId, coins, raw ?? null, now());
    db.prepare("COMMIT").run();
    return { ok: true, balance };
  } catch (e) {
    try { db.prepare("ROLLBACK").run(); } catch {}
    throw e;
  }
}

/** Realised return per game, for auditing the published figure against play. */
export function gameStats(db) {
  return db.prepare(
    `SELECT game, COUNT(*) AS spins, SUM(stake) AS staked, SUM(win) AS returned
     FROM spins GROUP BY game`
  ).all();
}
