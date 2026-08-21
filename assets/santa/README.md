# Santa Slots artwork and sound

Recovered from the original Construct project: fourteen symbols (`card0`–`card13`)
and the sound set.

## The symbols have been rotated

They were stored a quarter turn counter-clockwise — every one displayed on its
side, wreaths sideways and the word WILD reading bottom to top. The committed
files have had `tools/rotate_png.py --cw` applied once and are now 192×155,
which is landscape, which is right: this was a landscape phone game with five
reels across the screen.

If you ever re-extract these from the Construct project, they will come out
sideways again and need the same turn. Do not run the script over the files
already in this directory — it is not idempotent and would put them back on
their side.

`card0` is the wild and `card13` the bonus; `card12` is declared by the config
but never drawn, so the build substitutes a blank of the same shape.
