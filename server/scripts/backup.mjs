#!/usr/bin/env node
/**
 * Snapshot the balances.
 *
 * `VACUUM INTO` is SQLite's own online-backup path: it produces a consistent,
 * fully-formed database file from a live one without stopping writes, and
 * without needing the sqlite3 CLI in the image. Copying the .db file with `cp`
 * while the server is running does not do this — you can get a torn file that
 * looks fine until you need it.
 *
 *   node scripts/backup.mjs [dest-dir] [keep]
 *
 * On Fly:
 *   fly ssh console -C "node /app/scripts/backup.mjs /data/backups 14"
 *   fly ssh sftp get /data/backups/<name>.db     # pull one down
 */
import { DatabaseSync } from "node:sqlite";
import { mkdirSync, readdirSync, statSync, unlinkSync } from "node:fs";
import { join } from "node:path";

const src = process.env.DB_PATH ?? "/data/casino.db";
const dir = process.argv[2] ?? join(process.env.HOME ?? ".", "casino-backups");
const keep = Number(process.argv[3] ?? 14);

// Colons are legal in filenames and a nuisance in every tool that reads them.
// Milliseconds stay in the name because VACUUM INTO refuses to overwrite, so
// two snapshots in the same second would be an error rather than a second file.
const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 23);
const dest = join(dir, `casino-${stamp}.db`);

mkdirSync(dir, { recursive: true });
const db = new DatabaseSync(src, { readOnly: true });
db.exec(`VACUUM INTO '${dest.replace(/'/g, "''")}'`);

// Read the snapshot back before trusting it. A backup nobody has opened is a
// guess, and this is the one file in the system that cannot be regenerated.
const check = new DatabaseSync(dest, { readOnly: true });
const { n, coins } = check.prepare("SELECT count(*) n, coalesce(sum(coins),0) coins FROM players").get();
const { ledger } = check.prepare("SELECT count(*) ledger FROM ledger").get();
check.close();
db.close();

console.log(`${dest}  ${(statSync(dest).size / 1024).toFixed(0)}KB  ${n} players, ${coins} coins, ${ledger} ledger rows`);

const old = readdirSync(dir)
  .filter((f) => /^casino-.*\.db$/.test(f))
  .sort()
  .slice(0, -keep);
for (const f of old) {
  unlinkSync(join(dir, f));
  console.log(`pruned ${f}`);
}
