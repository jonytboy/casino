"""Tests for the slot math model.

The important ones cross-check the fast closed form against two slower but
independent routes: full enumeration of every reel window, and actually
spinning the reels. If the closed form drifts, these catch it.
"""
import sys, pathlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from slotmath.exact import evaluate, exact_spin_stats, line_win_multiplier
from slotmath.model import GameConfig
from slotmath.paylines import PAYLINES, REELS, ROWS
from slotmath.simulate import simulate
from slotmath.strips import build_strip, max_run

_ROOT = Path(__file__).resolve().parents[1]
CONFIGS = sorted(list((_ROOT / "pirates" / "config").glob("*.json"))
                 + list((_ROOT / "santa" / "config").glob("*.json")))


def test_paylines_wellformed():
    assert len(PAYLINES) == 30
    assert len(set(PAYLINES)) == 30, "paylines must be distinct"
    for line in PAYLINES:
        assert len(line) == REELS
        assert all(0 <= r < ROWS for r in line)


def test_strip_builder_preserves_counts():
    counts = {"J": 8, "K": 7, "Q": 6, "A": 6, "Lemon": 4,
              "Seven": 3, "Star": 2, "Diamond": 2, "Wild": 1, "Bonus": 1}
    strip = build_strip(counts)
    assert len(strip) == sum(counts.values())
    for sym, n in counts.items():
        assert strip.count(sym) == n
    assert max_run(strip, "Bonus") == 1, "scatters must not stack"


def test_stacking_preserves_counts_and_blocks():
    """Stacked symbols must form contiguous blocks without changing frequency."""
    counts = {"top": 3, "mid": 5, "low": 14, "other": 18}
    strip = build_strip(counts, stacks={"top": 3})
    assert len(strip) == sum(counts.values())
    for sym, n in counts.items():
        assert strip.count(sym) == n, sym
    assert max_run(strip, "top") == 3, "stacked symbol must form a block of 3"
    assert max_run(strip, "mid") == 1, "unstacked symbols must stay spaced"


def test_stacking_does_not_change_rtp():
    """Arrangement must not move RTP: line wins depend only on marginals."""
    from slotmath.model import GameConfig
    counts = {"A": 3, "B": 6, "C": 10, "D": 21}
    paytable = {"A": {3: 100, 4: 400, 5: 2000}, "B": {3: 10, 4: 40, 5: 200},
                "C": {3: 5, 4: 20, 5: 100}}
    def cfg_for(stacks):
        return GameConfig(
            name="t", symbols=["A", "B", "C", "D", "NoWild"], wild="NoWild",
            scatter="D", paytable=paytable, scatter_pays={}, scatter_spins={},
            reels=[build_strip(counts, stacks) for _ in range(5)])
    flat = evaluate(cfg_for(None))["rtp_total"]
    stacked = evaluate(cfg_for({"A": 3}))["rtp_total"]
    assert abs(flat - stacked) < 1e-12, (flat, stacked)


def test_wild_substitution():
    cfg = GameConfig.load(CONFIGS[0])
    # Five wilds should pay the best available five-of-a-kind.
    best5 = max(cfg.paytable[s].get(5, 0) for s in cfg.paying_symbols)
    assert line_win_multiplier(cfg, ("Wild",) * 5) == best5
    # A wild must not complete the scatter.
    assert line_win_multiplier(cfg, ("Bonus", "Wild", "Wild", "Wild", "Wild")) == 0


def test_configs_valid():
    assert CONFIGS, "no configs found"
    for path in CONFIGS:
        GameConfig.load(path).validate()


def test_config_roundtrip(tmp_path=None):
    import tempfile
    cfg = GameConfig.load(CONFIGS[0])
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as fh:
        cfg.dump(fh.name)
        again = GameConfig.load(fh.name)
    assert again.reels == cfg.reels
    assert again.paytable == cfg.paytable


def test_tensor_matches_enumeration():
    """The cached win-tensor contraction must agree with brute-force enumeration.

    Enumeration is (strip length)^5, so this covers the configs small enough to
    run quickly; simulation covers the rest via test_simulation_matches_exact.
    """
    checked = 0
    for path in CONFIGS:
        cfg = GameConfig.load(path)
        try:
            res = evaluate(cfg, hit_rate=True, max_windows=4_000_000)
        except ValueError:
            continue  # strips too long to enumerate in test time
        assert abs(res["rtp_total"] - res["rtp_enumerated"]) < 1e-9, path.name
        checked += 1
    assert checked, "no config was small enough to enumerate"


def test_simulation_matches_exact():
    """Monte Carlo must land near the exact figure (loose bound: high variance)."""
    for path in CONFIGS:
        cfg = GameConfig.load(path)
        try:
            ex = evaluate(cfg, hit_rate=True, max_windows=4_000_000)
        except ValueError:
            ex = evaluate(cfg)
            ex["any_win_rate"] = None
        sim = simulate(cfg, spins=60_000, seed=7)
        assert abs(sim["rtp_total"] - ex["rtp_total"]) < 0.05, (
            f"{path.name}: exact {ex['rtp_total']:.4f} vs sim {sim['rtp_total']:.4f}")
        if ex["any_win_rate"] is not None:
            assert abs(sim["any_win_rate"] - ex["any_win_rate"]) < 0.01, path.name


def test_rtp_in_publishable_band():
    """Tuned configs should sit in the range operators and stores expect."""
    for path in CONFIGS:
        cfg = GameConfig.load(path)
        rtp = evaluate(cfg)["rtp_total"]
        assert 0.80 <= rtp <= 0.99, f"{path.name} RTP {rtp:.4f} outside sane band"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
