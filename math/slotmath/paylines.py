"""30-payline definitions for a 5-reel x 3-row cabinet.

Each payline is a tuple of five row indices (0 = top, 1 = middle, 2 = bottom),
one per reel, matching the line art recovered from the original APK
(assets/line1@2x.png ... line30@2x.png).
"""

ROWS = 3
REELS = 5

PAYLINES = [
    (1, 1, 1, 1, 1),  # 1  middle
    (0, 0, 0, 0, 0),  # 2  top
    (2, 2, 2, 2, 2),  # 3  bottom
    (0, 1, 2, 1, 0),  # 4  V
    (2, 1, 0, 1, 2),  # 5  inverted V
    (0, 0, 1, 2, 2),  # 6
    (2, 2, 1, 0, 0),  # 7
    (1, 0, 0, 0, 1),  # 8
    (1, 2, 2, 2, 1),  # 9
    (0, 1, 1, 1, 0),  # 10
    (2, 1, 1, 1, 2),  # 11
    (1, 0, 1, 2, 1),  # 12
    (1, 2, 1, 0, 1),  # 13
    (0, 0, 1, 0, 0),  # 14
    (2, 2, 1, 2, 2),  # 15
    (1, 1, 0, 1, 1),  # 16
    (1, 1, 2, 1, 1),  # 17
    (0, 1, 0, 1, 0),  # 18
    (2, 1, 2, 1, 2),  # 19
    (1, 0, 2, 0, 1),  # 20
    (1, 2, 0, 2, 1),  # 21
    (0, 2, 0, 2, 0),  # 22
    (2, 0, 2, 0, 2),  # 23
    (0, 1, 2, 2, 2),  # 24
    (2, 1, 0, 0, 0),  # 25
    (0, 0, 2, 0, 0),  # 26
    (2, 2, 0, 2, 2),  # 27
    (1, 0, 0, 1, 2),  # 28
    (1, 2, 2, 1, 0),  # 29
    (0, 2, 1, 0, 2),  # 30
]

assert len(PAYLINES) == 30
assert all(len(l) == REELS and all(0 <= r < ROWS for r in l) for l in PAYLINES)
