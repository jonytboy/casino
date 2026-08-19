"""Slot configuration model: symbols, paytable, reel strips.

All payline values are expressed as multiples of BET PER LINE.
Scatter (Bonus) values are multiples of TOTAL BET, per standard slot convention.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class GameConfig:
    name: str
    symbols: list[str]
    wild: str
    scatter: str
    # symbol -> {count_in_a_row: multiplier of bet-per-line}
    paytable: dict[str, dict[int, float]]
    # scatter count -> multiplier of total bet
    scatter_pays: dict[int, float]
    # scatter count -> free spins awarded
    scatter_spins: dict[int, int]
    # five reel strips, each a list of symbol names
    reels: list[list[str]]
    rows: int = 3

    @property
    def paying_symbols(self) -> list[str]:
        """Symbols that form left-to-right line wins (excludes wild and scatter)."""
        return [s for s in self.symbols if s not in (self.wild, self.scatter)]

    def strip_counts(self, reel_index: int) -> dict[str, int]:
        strip = self.reels[reel_index]
        return {s: strip.count(s) for s in self.symbols}

    def symbol_probs(self, reel_index: int) -> dict[str, float]:
        """Marginal probability of each symbol landing on a given row of a reel.

        Independent of which row: for a uniformly random stop p, the symbol at
        row r is strip[(p + r) mod L], which is uniform over the strip.
        """
        strip = self.reels[reel_index]
        n = len(strip)
        return {s: strip.count(s) / n for s in self.symbols}

    def validate(self) -> None:
        assert len(self.reels) == 5, "expected 5 reels"
        for i, strip in enumerate(self.reels):
            assert len(strip) > 0, f"reel {i} is empty"
            unknown = set(strip) - set(self.symbols)
            assert not unknown, f"reel {i} has unknown symbols: {unknown}"
        assert self.wild in self.symbols
        assert self.scatter in self.symbols
        for sym, pays in self.paytable.items():
            assert sym in self.symbols, f"paytable references unknown symbol {sym}"

    @staticmethod
    def load(path: str | Path) -> "GameConfig":
        data = json.loads(Path(path).read_text())
        cfg = GameConfig(
            name=data["name"],
            symbols=data["symbols"],
            wild=data["wild"],
            scatter=data["scatter"],
            paytable={s: {int(k): float(v) for k, v in t.items()}
                      for s, t in data["paytable"].items()},
            scatter_pays={int(k): float(v) for k, v in data.get("scatter_pays", {}).items()},
            scatter_spins={int(k): int(v) for k, v in data.get("scatter_spins", {}).items()},
            reels=data["reels"],
            rows=data.get("rows", 3),
        )
        cfg.validate()
        return cfg

    def dump(self, path: str | Path) -> None:
        data = {
            "name": self.name,
            "symbols": self.symbols,
            "wild": self.wild,
            "scatter": self.scatter,
            "rows": self.rows,
            "paytable": {s: {str(k): v for k, v in t.items()} for s, t in self.paytable.items()},
            "scatter_pays": {str(k): v for k, v in self.scatter_pays.items()},
            "scatter_spins": {str(k): v for k, v in self.scatter_spins.items()},
            "reels": self.reels,
        }
        Path(path).write_text(json.dumps(data, indent=2) + "\n")
