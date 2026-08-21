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
import os
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

def santa_art(cfg):
    art_dir = ROOT / "assets" / "santa"
    art = {s: data_uri(art_dir / "symbols" / f"{s}.png", "image/png")
           for s in cfg.symbols if (art_dir / "symbols" / f"{s}.png").exists()}
    # Symbols the config declares but the game never draws (the inert scatter
    # placeholder) still need something to render.
    blank = ("data:image/svg+xml;base64," + base64.b64encode(
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 155 192"/>').decode())
    for s in cfg.symbols:
        art.setdefault(s, blank)

    # Mapped from the project's own sound set: ROLL is the reel loop, GET the
    # win, BONE the bonus box, HoHoHo the celebration.
    stems = {"spin": "ROLL", "won": "GET", "coin": "SPIN",
             "chest": "HoHoHo", "nudge": "stopROLL", "warning": "BONE"}
    sfx = {k: data_uri(art_dir / "sounds" / f"{v}.ogg", "audio/ogg") for k, v in stems.items()}

    # Santa has no recovered mute graphic, so draw one rather than borrow
    # Pirate Slots' button plate.
    def speaker(on):
        waves = ('<path d="M30 16a12 12 0 0 1 0 18" stroke="#E3D5BC" stroke-width="3.5" fill="none" stroke-linecap="round"/>'
                 if on else
                 '<path d="M30 17l14 16M44 17L30 33" stroke="#C8595C" stroke-width="3.5" stroke-linecap="round"/>')
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 50 50">'
               f'<rect width="50" height="50" rx="9" fill="#16414C"/>'
               f'<path d="M12 20h6l8-7v24l-8-7h-6z" fill="#E3D5BC"/>{waves}</svg>')
        return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()

    return art, sfx, {"on": speaker(True), "off": speaker(False)}


# ----------------------------------------------------------------------- build

GAMES = {
    "pirates": dict(
        config="math/pirates/config/pirates-v3.json", lines=PIRATE_LINES, art=pirate_art,
        title="Pirate Slots", out="pirates-slot.html",
        subtitle="The original artwork, running on reel strips solved to a verified "
                 "94.00% return. The machine below reports its own odds and converges "
                 "to them as you play.",
        rules="Wild substitutes for every symbol except Bonus. Three or more Bonus "
              "anywhere pays a multiple of the total stake.",
    ),
    "santa": dict(
        config="math/santa/config/santa-94.json", lines=SANTA_LINES, art=santa_art,
        title="Santa Slots", out="santa-slot.html",
        subtitle="The original artwork and sound, on reel strips solved to a verified "
                 "94.00% return. The game shipped paying 229.60% \u2014 more than twice "
                 "what it took \u2014 because its wild landed one spin in fourteen.",
        rules="The wild substitutes for any symbol, and a line pays the first non-wild "
              "symbol on it. Two of a kind pays only on the wild, the reindeer, the "
              "sleigh and the present.",
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
                "scatter_spins", "reels", "rule")}
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
    kb = dest.stat().st_size / 1024
    print(f"  {spec['title']:14} {rtp * 100:.2f}% RTP  {len(lines):>2} lines  "
          f"{windows:>12,} windows  ->  web/{spec['out']} ({kb:.0f} KB)")
    if kb > 15000:
        raise SystemExit(f"{dest} exceeds the 16MB artifact limit")
    return dest


# Friendly names for the paytable, since the Construct project only ever knew
# its symbols by index.
SANTA_NAMES = {
    "card0": "Wild", "card1": "Stocking", "card2": "Stocking (red)",
    "card3": "Snow globe", "card4": "Snow globe (gold)", "card5": "Snowman",
    "card6": "Snowman (green)", "card7": "Bauble", "card8": "Candy cane",
    "card9": "Present", "card10": "Reindeer", "card11": "Sleigh",
    "card12": "Tree", "card13": "Bonus",
}

# Coin packs. No checkout is wired: selling coins needs a server that owns the
# balance, and a page whose wallet lives in localStorage cannot sell anything a
# player could not simply mint. Set checkoutBase once a real store exists.
STORE = {
    "checkoutBase": None,
    "packs": [
        {"id": "coins-10k", "coins": 10_000, "price": "\u00a30.99"},
        {"id": "coins-60k", "coins": 60_000, "price": "\u00a34.99"},
        {"id": "coins-200k", "coins": 200_000, "price": "\u00a39.99"},
    ],
}


def hub_page() -> tuple:
    """Assemble both machines into one lobby with a shared purse."""
    games = {}
    for key in ("santa", "pirates"):
        spec = GAMES[key]
        cfg = GameConfig.load(ROOT / spec["config"])
        lines = spec["lines"]
        art, sfx, icons = spec["art"](cfg)
        res = evaluate(cfg, lines=lines)
        windows = 1
        for strip in cfg.reels:
            windows *= len(strip)
        top = max((max(t.values()) for t in cfg.paytable.values() if t), default=0)
        preview = sorted(cfg.paytable, key=lambda s: -max(cfg.paytable[s].values()))[:4]
        games[key] = {
            # The engine names games by key when it asks the server for a spin.
            "key": key,
            "title": spec["title"],
            "cfg": {k: getattr(cfg, k) for k in
                    ("symbols", "wild", "scatter", "rows", "paytable",
                     "scatter_pays", "scatter_spins", "reels", "rule")},
            "lines": [list(l) for l in lines],
            "art": art, "sfx": sfx, "icons": icons,
            "rtp": f"{res['rtp_total'] * 100:.2f}%",
            "windows": f"{windows:,}",
            "topAward": f"{top:,.0f}x line bet",
            "rules": spec["rules"],
            "names": SANTA_NAMES if key == "santa" else {},
            "preview": preview,
        }

    parts = [(ROOT / "web" / f"_hub_{n}.html").read_text() for n in ("head", "body", "script")]
    return parts, games


def fill(page: str, games: dict, api) -> str:
    """Substitute the build-time constants.

    `api` is null for a demo build, "" when the page is served from the API's
    own origin, or an absolute origin when it is hosted elsewhere. Note that ""
    is a real answer and not an absent one, so the page tests it against null.
    """
    return (page.replace("__GAMES__", json.dumps(games))
                .replace("__STORE__", json.dumps(STORE))
                .replace("__API__", json.dumps(api)))


def build_hub() -> pathlib.Path:
    """The artifact build. Demo unless CASINO_API names a server to talk to."""
    parts, games = hub_page()
    api = os.environ.get("CASINO_API")
    api = api.rstrip("/") if api else None
    dest = ROOT / "web" / "casino.html"
    dest.write_text(fill("\n".join(parts), games, api))
    kb = dest.stat().st_size / 1024
    mode = "demo" if api is None else f"live -> {api or 'same origin'}"
    print(f"  {'Exuma Casino':14} {len(games)} machines, shared purse, {mode}"
          f"  ->  web/casino.html ({kb:.0f} KB)")
    if kb > 15000:
        raise SystemExit("hub exceeds the 16MB artifact limit")
    return dest


def build_public() -> pathlib.Path:
    """The hosted build, served by the API itself.

    Always live and always same-origin: the server that hosts this page is the
    server that decides its spins, so there is no origin to configure and no
    way to deploy a page pointed at the wrong one. The artifact build is a
    fragment because the artifact host supplies the document around it; this
    one has to bring its own.
    """
    parts, games = hub_page()
    head, body, script = (fill(part, games, "") for part in parts)
    doc = ('<!doctype html>\n<html lang="en">\n<head>\n'
           f'{head}'
           '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
           f'</head>\n<body>\n{body}\n{script}\n</body>\n</html>\n')
    dest = ROOT / "server" / "public" / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(doc)
    kb = dest.stat().st_size / 1024
    print(f"  {'(hosted build)':14} standalone document, same-origin API"
          f"  ->  server/public/index.html ({kb:.0f} KB)")
    return dest


if __name__ == "__main__":
    wanted = sys.argv[1:] or list(GAMES) + ["hub", "serve"]
    for key in wanted:
        if key == "hub":
            build_hub()
        elif key == "serve":
            build_public()
        else:
            build(key)
