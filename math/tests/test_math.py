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
_ALL = sorted(list((_ROOT / "pirates" / "config").glob("*.json"))
              + list((_ROOT / "santa" / "config").glob("*.json")))

# Configs recovered from the shipped games are historical records, not designs:
# they are allowed to be broken, and two of them pay over 100%. Only the solved
# configs are held to a publishable standard.
AS_SHIPPED = [p for p in _ALL if "as-shipped" in p.name]
SOLVED = [p for p in _ALL if p not in AS_SHIPPED]
CONFIGS = _ALL


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


def test_hit_rate_depends_on_the_paylines_given():
    """Passing different paylines must change the enumerated statistics.

    Regression test. evaluate() used to take a line *count* and silently
    enumerate against the default 30-line set, so a 20-line game was measured
    over the wrong paylines. RTP is invariant to the line count, so it kept
    agreeing and hid the fault; only the hit rate exposes it.
    """
    cfg = GameConfig.load(CONFIGS[0])
    few = PAYLINES[:5]
    a = evaluate(cfg, lines=PAYLINES, hit_rate=True, max_windows=4_000_000)
    b = evaluate(cfg, lines=few, hit_rate=True, max_windows=4_000_000)
    assert a["lines"] == 30 and b["lines"] == 5
    assert b["any_win_rate"] < a["any_win_rate"], "fewer paylines must win less often"
    # RTP is line-count invariant, which is exactly why it could not catch this.
    assert abs(a["rtp_total"] - b["rtp_total"]) < 1e-9


def test_evaluate_rejects_a_line_count():
    """A bare integer is the mistake this API used to invite."""
    cfg = GameConfig.load(CONFIGS[0])
    try:
        evaluate(cfg, lines=30)
    except TypeError:
        return
    raise AssertionError("evaluate() should reject an int for lines")


def test_leftmost_nonwild_rule():
    """The two win rules must actually differ, and in the documented direction.

    Santa Slots pays the first non-wild symbol on a line; Pirate Slots pays the
    best symbol the wilds could complete. Three wilds followed by a low symbol
    is where they part company.
    """
    from slotmath.model import GameConfig
    pt = {"low": {3: 7, 4: 25, 5: 150}, "high": {2: 10, 3: 150, 4: 500, 5: 5000}}
    syms = ["wild", "low", "high", "other", "none"]
    def cfg_for(rule):
        return GameConfig(name="t", symbols=syms, wild="wild", scatter="none",
                          paytable=pt, scatter_pays={}, scatter_spins={},
                          reels=[syms[:4]] * 5, rule=rule)
    combo = ("wild", "wild", "wild", "low", "other")
    assert line_win_multiplier(cfg_for("best"), combo) == 150
    assert line_win_multiplier(cfg_for("leftmost_nonwild"), combo) == 25
    # An all-wild line pays the wild's own row under the leftmost rule.
    assert line_win_multiplier(cfg_for("leftmost_nonwild"), ("wild",) * 5) == 0


def test_wild_substitution():
    """Wild behaviour under the 'best' rule, on a config built for the purpose.

    This used to load CONFIGS[0] and assume it used the "best" rule. Adding a
    config whose name sorted earlier silently changed what the test measured —
    so it now builds its own fixture rather than depending on glob order.
    """
    from slotmath.model import GameConfig
    pt = {"low": {3: 5, 4: 20, 5: 100}, "high": {3: 100, 4: 200, 5: 400}}
    syms = ["low", "high", "Wild", "Bonus"]
    cfg = GameConfig(name="t", symbols=syms, wild="Wild", scatter="Bonus",
                     paytable=pt, scatter_pays={}, scatter_spins={},
                     reels=[syms] * 5, rule="best")
    # Five wilds pay the best available five-of-a-kind.
    assert line_win_multiplier(cfg, ("Wild",) * 5) == 400
    # A wild must not complete the scatter.
    assert line_win_multiplier(cfg, ("Bonus", "Wild", "Wild", "Wild", "Wild")) == 0
    # And it does substitute for an ordinary symbol.
    assert line_win_multiplier(cfg, ("low", "Wild", "low", "Wild", "low")) == 100


def test_as_shipped_configs_pay_over_100_percent():
    """Both shipped games over-paid; that is the project's central finding.

    Pinned so the recovered strips and paytables cannot drift unnoticed.
    """
    assert AS_SHIPPED, "no as-shipped configs found"
    for path in AS_SHIPPED:
        rtp = evaluate(GameConfig.load(path))["rtp_total"]
        assert rtp > 1.0, f"{path.name} reads {rtp:.4f}, expected over 100%"


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
    """Solved configs should sit in the range operators and stores expect."""
    assert SOLVED, "no solved configs found"
    for path in SOLVED:
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
