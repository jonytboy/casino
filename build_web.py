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
