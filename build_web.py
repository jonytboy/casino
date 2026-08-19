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

ART = pathlib.Path("/tmp/claude-0/-home-user-Snagging/f12b2003-ed21-56e3-9573-420cb273b7a6/scratchpad/apk/assets")
CFG = json.loads((ROOT / "math/pirates/config/pirates-v3.json").read_text())

# The APK names the seven symbol by its glyph, not its word.
FILENAME = {"Seven": "7"}

assets = {}
for sym in CFG["symbols"]:
    p = ART / f"slotitem_{FILENAME.get(sym, sym)}@2x.png"
    assets[sym] = "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()

# Sounds and the mute icons, straight from the APK. SoundManager preloaded all
# six; GameLayer loops finsihedspin while the reels turn, fires won on a win and
# coindrop while coins are awarded.
SOUNDS = {
    "spin": ("res/raw/finsihedspin.mp3", "audio/mpeg"),
    "won": ("res/raw/won.mp3", "audio/mpeg"),
    "coin": ("res/raw/coindrop.mp3", "audio/mpeg"),
    "chest": ("res/raw/chestopen.mp3", "audio/mpeg"),
    "nudge": ("res/raw/nudge.mp3", "audio/mpeg"),
    "warning": ("res/raw/warning.mp3", "audio/mpeg"),
}
APK = ART.parent
sfx = {}
for key, (rel, mime) in SOUNDS.items():
    sfx[key] = f"data:{mime};base64," + base64.b64encode((APK / rel).read_bytes()).decode()

icons = {}
for key, name in (("on", "sound_on@2x.png"), ("off", "sound_off@2x.png")):
    icons[key] = "data:image/png;base64," + base64.b64encode((ART / name).read_bytes()).decode()

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
kb = dest.stat().st_size / 1024
print(f"wrote {dest} ({kb:.0f} KB)")
if kb > 15000:
    raise SystemExit("page exceeds the 16MB artifact limit")
