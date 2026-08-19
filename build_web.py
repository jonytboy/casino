"""Build a playable HTML slot from the solved config and the original artwork.

The page is self-contained: symbols are inlined as data URIs and the reel
strips, paytable and paylines are injected from the same JSON the Python model
verifies, so what you spin is what was measured.
"""
import base64
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "math"))
from slotmath.paylines import PAYLINES

# Art and audio are committed under assets/ so the page can be rebuilt from a
# clean checkout, without the APK.
ART = ROOT / "assets" / "pirates"
CFG = json.loads((ROOT / "math/pirates/config/pirates-v3.json").read_text())

# The APK named the seven symbol by its glyph, not its word.
FILENAME = {"Seven": "7"}

assets = {}
for sym in CFG["symbols"]:
    p = ART / "symbols" / f"{FILENAME.get(sym, sym)}.png"
    assets[sym] = "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()

# Sounds and the mute icons, straight from the APK. SoundManager preloaded all
# six; GameLayer loops finsihedspin while the reels turn, fires won on a win and
# coindrop while coins are awarded.
SOUNDS = {"spin": "finsihedspin", "won": "won", "coin": "coindrop",
          "chest": "chestopen", "nudge": "nudge", "warning": "warning"}
sfx = {}
for key, stem in SOUNDS.items():
    raw = (ART / "sounds" / f"{stem}.mp3").read_bytes()
    sfx[key] = "data:audio/mpeg;base64," + base64.b64encode(raw).decode()

icons = {}
for key in ("on", "off"):
    raw = (ART / "ui" / f"sound_{key}.png").read_bytes()
    icons[key] = "data:image/png;base64," + base64.b64encode(raw).decode()

tpl = (ROOT / "web" / "_template.html").read_text()
out = (tpl.replace("__ASSETS__", json.dumps(assets))
          .replace("__CONFIG__", json.dumps({k: CFG[k] for k in
                   ("symbols", "wild", "scatter", "rows", "paytable",
                    "scatter_pays", "scatter_spins", "reels")}))
          .replace("__PAYLINES__", json.dumps([list(l) for l in PAYLINES]))
          .replace("__SOUNDS__", json.dumps(sfx))
          .replace("__ICONS__", json.dumps(icons)))
dest = ROOT / "web" / "pirates-slot.html"
dest.write_text(out)
# docs/ is what GitHub Pages serves; keep it byte-identical to the built page.
pages = ROOT / "docs" / "index.html"
pages.parent.mkdir(exist_ok=True)
pages.write_text(out)
kb = dest.stat().st_size / 1024
print(f"wrote {dest} and {pages} ({kb:.0f} KB)")
if kb > 15000:
    raise SystemExit("page exceeds the 16MB artifact limit")
