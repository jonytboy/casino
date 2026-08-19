# Santa Slots — recovered source material

Read out of Dropbox through the connector, which is intermittent. These are the
only copies outside Dropbox, so they are committed rather than re-fetched.

- `prizes.xml` — the paytable, verbatim from `Files/prizes.xml`. Card id plus
  level (count in a row) to payout, as a multiple of bet per line.
- `game-eventsheet.txt` — text extraction of `Event sheets/game.xml`, the
  Construct 2 event sheet. The extraction strips XML tags, so it reads as bare
  values; it is enough to recover the paylines and the reel model but is not a
  substitute for the original file.

What was recovered from these: 20 paylines over a 5x3 grid, one of which
(line 8) duplicates line 3; symbols drawn with `floor(random(0,14))`, so 14
symbols uniformly and no reel strips at all; and the paytable above.

Still in Dropbox and not yet recovered: the symbol artwork, the audio
(SPIN/ROLL/BONE/GET/HoHoHo/Jingle1-4), and the `.capx` project itself.
