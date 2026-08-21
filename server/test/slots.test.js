import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { loadGame, exactLineRtp, exactScatterRtp, spinWindow, evaluate, lineWin } from "../src/slots.js";

const GAMES_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "games");
const load = (k) => {
  const raw = JSON.parse(readFileSync(join(GAMES_DIR, `${k}.json`), "utf8"));
  const g = loadGame(raw.cfg, raw.lines);
  g.key = k;
  return g;
};

// The figures the Python model publishes and the lobby advertises. If the server
// drifts from these, the advertised odds are a lie — so the build fails first.
const PUBLISHED = { santa: 0.94, pirates: 0.94 };

for (const key of Object.keys(PUBLISHED)) {
  test(`${key}: server RTP matches the published figure`, () => {
    const g = load(key);
    const rtp = exactLineRtp(g) + exactScatterRtp(g);
    assert.ok(Math.abs(rtp - PUBLISHED[key]) < 0.0005,
      `${key} reads ${(rtp * 100).toFixed(4)}%, published ${(PUBLISHED[key] * 100).toFixed(2)}%`);
  });

  test(`${key}: simulated play converges on the exact figure`, () => {
    const g = load(key);
    const exact = exactLineRtp(g) + exactScatterRtp(g);
    let staked = 0, returned = 0;
    for (let i = 0; i < 200_000; i++) {
      const w = spinWindow(g.cfg);
      returned += evaluate(g, w, 1).win;
      staked += g.lines.length;
    }
    const sim = returned / staked;
    assert.ok(Math.abs(sim - exact) < 0.06,
      `${key}: simulated ${(sim * 100).toFixed(2)}% vs exact ${(exact * 100).toFixed(2)}%`);
  });

  test(`${key}: a spin never returns a symbol the reels cannot show`, () => {
    const g = load(key);
    const allowed = new Set(g.cfg.reels.flat());
    for (let i = 0; i < 500; i++) {
      for (const col of spinWindow(g.cfg)) {
        assert.equal(col.length, g.cfg.rows);
        for (const s of col) assert.ok(allowed.has(s), `unexpected symbol ${s}`);
      }
    }
  });
}

test("the two win rules genuinely differ", () => {
  const pt = { low: { 3: 7, 4: 25, 5: 150 }, high: { 2: 10, 3: 150, 4: 500, 5: 5000 } };
  const base = { symbols: ["wild", "low", "high", "other"], wild: "wild", scatter: "none", paytable: pt };
  const combo = ["wild", "wild", "wild", "low", "other"];
  const paying = ["low", "high"];
  assert.equal(lineWin({ ...base, rule: "best" }, combo, paying), 150);
  assert.equal(lineWin({ ...base, rule: "leftmost_nonwild" }, combo, paying), 25);
});

test("a losing line pays nothing", () => {
  const g = load("pirates");
  const combo = g.cfg.reels.map((_, i) => g.cfg.reels[i][0]);
  const pay = lineWin(g.cfg, ["Diamond", "J", "Q", "K", "A"], g.paying);
  assert.equal(pay, 0, "five different symbols must not pay");
  assert.ok(combo.length === 5);
});
