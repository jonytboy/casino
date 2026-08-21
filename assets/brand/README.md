# Casino Carib brand assets

Drop the wordmark in here as `logo.svg`, `logo.png` or `logo.gif` (checked in
that order) and rebuild. `build_web.py` inlines it as a data URI into the top
bar of every page; with nothing here it falls back to setting the name in type,
which is what ships today.

The originals live in Dropbox under
`/Old Files/Websites & Apps/Carib Stuff/Carib Artwork` — `logo.png`,
`logo_wht.gif`, `logo_blk.gif`, `logo_small.gif` and the master sheet
`casino-carib-logo-graphics.png`. They could not be pulled in automatically:
this environment's network policy reaches Dropbox's metadata API but not the
hosts that serve file content, so the bytes have to be copied in by hand.

Prefer `logo.svg` if a vector exists anywhere. The 2016 rasters are sized for a
2016 screen and will look soft on a phone.

## Provenance

The Casino Carib marks are the owner's own brand, reused here with permission.
The game thumbnails that sit beside them in that Dropbox folder — frankenslots,
sherlock, labyrinth, jungleslots, magictheatre, whaleworld, ra and the rest —
are the old white-label platform vendor's catalogue art for third-party titles.
They are not covered by that ownership and must not be used here.
