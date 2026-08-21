/**
 * Reel engine — the authoritative one.
 *
 * The client renders spins; it never decides them. Everything that determines
 * money lives here: the strips, the randomness, and the win evaluation. A client
 * that could report its own outcome could report any outcome.
 *
 * This is a port of the Python model in math/slotmath, which is verified against
 * the shipped games' own logic. test/slots.test.js pins the two together.
 */
import { randomInt } from "node:crypto";

/** Best win for one payline, as a multiple of bet-per-line. */
export function lineWin(cfg, combo, paying) {
  if (cfg.rule === "leftmost_nonwild") {
    // Santa Slots pays the first non-wild symbol on the line, whatever it is
    // worth — not the best symbol the wilds could complete.
    let value = cfg.wild;
    for (const c of combo) if (c !== cfg.wild) { value = c; break; }
    let run = 0;
    for (const c of combo) { if (c === value || c === cfg.wild) run++; else break; }
    return run >= 2 ? (cfg.paytable[value]?.[run] ?? 0) : 0;
  }
  let best = 0;
  for (const sym of paying) {
    let run = 0;
    for (const c of combo) { if (c === sym || c === cfg.wild) run++; else break; }
    if (run >= 2) best = Math.max(best, cfg.paytable[sym]?.[run] ?? 0);
  }
  return best;
}

/** Length of the run that paid, so the client can light the right cells. */
export function winRun(cfg, combo, paying) {
  if (cfg.rule === "leftmost_nonwild") {
    let value = cfg.wild;
    for (const c of combo) if (c !== cfg.wild) { value = c; break; }
    let run = 0;
    for (const c of combo) { if (c === value || c === cfg.wild) run++; else break; }
    return run;
  }
  const pay = lineWin(cfg, combo, paying);
  for (const sym of paying) {
    let run = 0;
    for (const c of combo) { if (c === sym || c === cfg.wild) run++; else break; }
    if (run >= 2 && (cfg.paytable[sym]?.[run] ?? 0) === pay) return run;
  }
  return 0;
}

export function payingSymbols(cfg) {
  return cfg.symbols.filter((s) => s !== cfg.wild && s !== cfg.scatter);
}

/**
 * Spin the reels.
 *
 * `rng` defaults to crypto.randomInt — a CSPRNG, not Math.random. The odds are
 * published, so the randomness has to be worth publishing too.
 */
export function spinWindow(cfg, rng = (n) => randomInt(n)) {
  return cfg.reels.map((strip) => {
    const stop = rng(strip.length);
    return Array.from({ length: cfg.rows }, (_, r) => strip[(stop + r) % strip.length]);
  });
}

/** Evaluate a visible window. Returns the win in coins, plus display detail. */
export function evaluate(game, window, betPerLine) {
  const { cfg, lines, paying } = game;
  let lineTotal = 0;
  const lit = [];
  for (const line of lines) {
    const combo = line.map((row, reel) => window[reel][row]);
    const pay = lineWin(cfg, combo, paying);
    if (pay > 0) {
      lineTotal += pay;
      const run = winRun(cfg, combo, paying);
      for (let reel = 0; reel < run; reel++) lit.push([reel, line[reel]]);
    }
  }
  const scatters = window.reduce((n, col) => n + col.filter((s) => s === cfg.scatter).length, 0);
  const scatterMult = cfg.scatter_pays?.[scatters] ?? 0;
  return {
    win: lineTotal * betPerLine + scatterMult * betPerLine * lines.length,
    lit,
    scatters,
    freeSpins: cfg.scatter_spins?.[scatters] ?? 0,
  };
}

/**
 * Exact line RTP, by enumerating every symbol combination weighted by each
 * reel's marginals. Not a simulation — the tests compare this to the figure the
 * Python model publishes, so a strip edited by hand cannot quietly change the
 * odds the lobby advertises.
 */
export function exactLineRtp(game) {
  const { cfg } = game;
  const probs = cfg.reels.map((strip) => {
    const m = new Map();
    for (const s of strip) m.set(s, (m.get(s) ?? 0) + 1 / strip.length);
    return [...m.entries()];
  });
  let ev = 0;
  const combo = new Array(cfg.reels.length);
  const rec = (reel, p) => {
    if (p === 0) return;
    if (reel === cfg.reels.length) { ev += p * lineWin(cfg, combo, game.paying); return; }
    for (const [sym, q] of probs[reel]) { combo[reel] = sym; rec(reel + 1, p * q); }
  };
  rec(0, 1);
  return ev;
}

/** Exact scatter RTP, as a fraction of total bet. */
export function exactScatterRtp(game) {
  const { cfg } = game;
  if (!cfg.scatter_pays || !Object.keys(cfg.scatter_pays).length) return 0;
  let dist = new Map([[0, 1]]);
  for (const strip of cfg.reels) {
    const per = new Map();
    for (let stop = 0; stop < strip.length; stop++) {
      let k = 0;
      for (let r = 0; r < cfg.rows; r++) if (strip[(stop + r) % strip.length] === cfg.scatter) k++;
      per.set(k, (per.get(k) ?? 0) + 1 / strip.length);
    }
    const merged = new Map();
    for (const [a, pa] of dist) for (const [b, pb] of per) merged.set(a + b, (merged.get(a + b) ?? 0) + pa * pb);
    dist = merged;
  }
  let rtp = 0;
  for (const [k, p] of dist) rtp += p * (cfg.scatter_pays[k] ?? 0);
  return rtp;
}

export function loadGame(cfg, lines) {
  return { cfg, lines, paying: payingSymbols(cfg) };
}
