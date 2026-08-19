"""Build playable HTML slots from the solved configs.

One template, one game per config. The reels, paytable and paylines are injected
from the same JSON the Python model verifies, so a published page cannot drift
from the measured figures without the build changing.

Art and audio are committed under assets/ where they have been recovered. Where
they have not, the build generates obvious placeholder symbols rather than
borrowing another game's artwork — a placeholder should look like one.
"""
import base64
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "math"))
sys.path.insert(0, str(ROOT / "math" / "santa"))

from slotmath.exact import evaluate
from slotmath.model import GameConfig
from slotmath.paylines import PAYLINES as PIRATE_LINES
from santa_exact import PAYLINES as SANTA_LINES


def data_uri(path: pathlib.Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


# ---------------------------------------------------------------- Pirate Slots

def pirate_art(cfg):
    art_dir = ROOT / "assets" / "pirates"
    names = {"Seven": "7"}  # the APK named the seven by its glyph
    art = {s: data_uri(art_dir / "symbols" / f"{names.get(s, s)}.png", "image/png")
           for s in cfg.symbols}
    stems = {"spin": "finsihedspin", "won": "won", "coin": "coindrop",
             "chest": "chestopen", "nudge": "nudge", "warning": "warning"}
    sfx = {k: data_uri(art_dir / "sounds" / f"{v}.mp3", "audio/mpeg") for k, v in stems.items()}
    icons = {k: data_uri(art_dir / "ui" / f"sound_{k}.png", "image/png") for k in ("on", "off")}
    return art, sfx, icons


# ----------------------------------------------------------------- Santa Slots

# Santa's artwork is still in Dropbox. Its symbols are known only by pay rank, so
# the placeholders say exactly that instead of inventing imagery.
SANTA_TIERS = {
    "card0":  ("#F4C860", "#4A3512", "TOP"),
    "card11": ("#E0784B", "#3A1B0E", "PREM"),
    "card10": ("#D9694E", "#3A1710", "PREM"),
    "card9":  ("#C8595C", "#331216", "PREM"),
    "card8":  ("#5FA9A2", "#12332F", "MID"),
    "card7":  ("#57A0AC", "#122E33", "MID"),
    "card6":  ("#5090B8", "#122736", "MID"),
    "card5":  ("#5A86BE", "#131F33", "MID"),
    "card4":  ("#6E8FA8", "#16242E", "LOW"),
    "card3":  ("#6D95A0", "#16262A", "LOW"),
    "card2":  ("#74998F", "#182722", "LOW"),
    "card1":  ("#7C9C86", "#1A2720", "LOW"),
    "card12": ("#9B7BB5", "#241A2E", "ODD"),
    "card13": ("#37525C", "#16262C", ""),
}


def santa_art(cfg):
    art = {}
    for sym in cfg.symbols:
        fill, ink, tier = SANTA_TIERS.get(sym, ("#37525C", "#16262C", ""))
        top = max(cfg.paytable.get(sym, {}).values(), default=0)
        label = sym.replace("card", "")
        value = f"{top:g}" if top else "—"
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 140 140">'
            f'<circle cx="70" cy="70" r="62" fill="{fill}" stroke="{ink}" stroke-width="5"/>'
            f'<text x="70" y="66" font-family="Georgia,serif" font-size="46" font-weight="bold"'
            f' fill="{ink}" text-anchor="middle">{label}</text>'
            f'<text x="70" y="96" font-family="monospace" font-size="20"'
            f' fill="{ink}" text-anchor="middle" opacity=".8">{value}</text>'
            f'<text x="70" y="120" font-family="monospace" font-size="13"'
            f' fill="{ink}" text-anchor="middle" opacity=".6">{tier}</text></svg>'
        )
        art[sym] = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    return art, {}, {}


# ----------------------------------------------------------------------- build

GAMES = {
    "pirates": dict(
        config="math/pirates/config/pirates-v3.json", lines=PIRATE_LINES, art=pirate_art,
        title="Pirate Slots", out="pirates-slot.html", pages=True,
        subtitle="The original artwork, running on reel strips solved to a verified "
                 "94.00% return. The machine below reports its own odds and converges "
                 "to them as you play.",
        rules="Wild substitutes for every symbol except Bonus. Three or more Bonus "
              "anywhere pays a multiple of the total stake.",
    ),
    "santa": dict(
        config="math/santa/config/santa-94.json", lines=SANTA_LINES, art=santa_art,
        title="Santa Slots", out="santa-slot.html", pages=False,
        subtitle="Reel strips solved to a verified 94.00% return, up from the 47.47% "
                 "the original shipped with. Symbols are placeholders showing each "
                 "one's rank and top award until the artwork is recovered.",
        rules="Symbols are placeholders: the number is the symbol's id and beneath it "
              "is its five-of-a-kind award. This game has no wild and no scatter.",
    ),
}


def build(key: str) -> pathlib.Path:
    spec = GAMES[key]
    cfg = GameConfig.load(ROOT / spec["config"])
    lines = spec["lines"]
    art, sfx, icons = spec["art"](cfg)

    rtp = evaluate(cfg, lines=lines)["rtp_total"]
    windows = 1
    for strip in cfg.reels:
        windows *= len(strip)

    payload = {k: getattr(cfg, k) for k in
               ("symbols", "wild", "scatter", "rows", "paytable", "scatter_pays",
                "scatter_spins", "reels")}
    out = (ROOT / "web" / "_template.html").read_text()
    for token, value in (
        ("__ASSETS__", json.dumps(art)), ("__CONFIG__", json.dumps(payload)),
        ("__PAYLINES__", json.dumps([list(l) for l in lines])),
        ("__SOUNDS__", json.dumps(sfx)), ("__ICONS__", json.dumps(icons)),
        ("__TITLE__", spec["title"]), ("__SUBTITLE__", spec["subtitle"]),
        ("__RULES__", spec["rules"]), ("__LINES__", str(len(lines))),
        ("__RTP__", f"{rtp * 100:.2f}%"), ("__WINDOWS__", f"{windows:,}"),
    ):
        out = out.replace(token, value)

    dest = ROOT / "web" / spec["out"]
    dest.write_text(out)
    if spec["pages"]:
        pages = ROOT / "docs" / "index.html"
        pages.parent.mkdir(exist_ok=True)
        pages.write_text(out)
    kb = dest.stat().st_size / 1024
    print(f"  {spec['title']:14} {rtp * 100:.2f}% RTP  {len(lines):>2} lines  "
          f"{windows:>12,} windows  ->  web/{spec['out']} ({kb:.0f} KB)")
    if kb > 15000:
        raise SystemExit(f"{dest} exceeds the 16MB artifact limit")
    return dest


if __name__ == "__main__":
    wanted = sys.argv[1:] or list(GAMES)
    for key in wanted:
        build(key)
