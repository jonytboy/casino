"""Rotate 8-bit RGBA PNGs by a quarter turn, with no image library.

Written because this box has no Pillow, no ImageMagick and no ffmpeg, and the
Santa symbols were recovered from the Construct project stored a quarter turn
counter-clockwise — every one of them displayed on its side.

Only the case actually needed is handled: bit depth 8, colour type 6 (RGBA),
no interlacing. Anything else raises rather than guessing, because a silent
wrong answer here corrupts artwork that cannot be regenerated.

NOT idempotent — running it twice rotates twice. The committed assets have
already had `--cw` applied once; see assets/santa/README.md.

    python3 tools/rotate_png.py --cw path/to/*.png
"""
import argparse
import pathlib
import struct
import sys
import zlib

SIG = b"\x89PNG\r\n\x1a\n"
BPP = 4  # RGBA


def chunks(blob):
    i = 8
    while i < len(blob):
        (length,) = struct.unpack(">I", blob[i:i + 4])
        yield blob[i + 4:i + 8], blob[i + 8:i + 8 + length]
        i += 12 + length


def paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else (b if pb <= pc else c)


def unfilter(raw, width, height):
    """Undo the per-scanline filters, returning one bytearray of pixels."""
    stride = width * BPP
    out = bytearray(stride * height)
    pos = 0
    for y in range(height):
        ft = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        up_off = (y - 1) * stride
        for x in range(stride):
            a = line[x - BPP] if x >= BPP else 0
            b = out[up_off + x] if y else 0
            c = out[up_off + x - BPP] if y and x >= BPP else 0
            if ft == 0:
                pass
            elif ft == 1:
                line[x] = (line[x] + a) & 0xFF
            elif ft == 2:
                line[x] = (line[x] + b) & 0xFF
            elif ft == 3:
                line[x] = (line[x] + (a + b) // 2) & 0xFF
            elif ft == 4:
                line[x] = (line[x] + paeth(a, b, c)) & 0xFF
            else:
                raise ValueError(f"unknown filter type {ft} on row {y}")
        out[y * stride:(y + 1) * stride] = line
    return out


def turn(pixels, width, height, clockwise):
    """A quarter turn. Returns (pixels, new_width, new_height)."""
    new_w, new_h = height, width
    out = bytearray(len(pixels))
    src_stride, dst_stride = width * BPP, new_w * BPP
    for y in range(height):
        row = y * src_stride
        for x in range(width):
            if clockwise:
                nx, ny = height - 1 - y, x
            else:
                nx, ny = y, width - 1 - x
            s = row + x * BPP
            d = ny * dst_stride + nx * BPP
            out[d:d + BPP] = pixels[s:s + BPP]
    return out, new_w, new_h


def encode(pixels, width, height):
    stride = width * BPP
    # Filter type 0 throughout: these are small, and zlib does the work.
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += pixels[y * stride:(y + 1) * stride]

    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (SIG + chunk(b"IHDR", ihdr) + chunk(b"sRGB", b"\x00")
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def load(path):
    blob = path.read_bytes()
    if blob[:8] != SIG:
        raise ValueError(f"{path}: not a PNG")
    idat = b""
    size = None
    for tag, body in chunks(blob):
        if tag == b"IHDR":
            w, h, depth, colour, comp, filt, interlace = struct.unpack(">IIBBBBB", body)
            if (depth, colour, interlace) != (8, 6, 0):
                raise ValueError(f"{path}: need 8-bit RGBA non-interlaced, "
                                 f"got depth {depth} colour {colour} interlace {interlace}")
            size = (w, h)
        elif tag == b"IDAT":
            idat += body
    if size is None:
        raise ValueError(f"{path}: no IHDR")
    w, h = size
    return unfilter(zlib.decompress(idat), w, h), w, h


def selftest(pixels, w, h, clockwise):
    """Four quarter turns must return the original pixels exactly."""
    p, cw, ch = pixels, w, h
    for _ in range(4):
        p, cw, ch = turn(p, cw, ch, clockwise)
    if (cw, ch) != (w, h) or bytes(p) != bytes(pixels):
        raise SystemExit("rotation self-test failed — refusing to write")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    d = ap.add_mutually_exclusive_group(required=True)
    d.add_argument("--cw", action="store_true", help="quarter turn clockwise")
    d.add_argument("--ccw", action="store_true", help="quarter turn counter-clockwise")
    ap.add_argument("paths", nargs="+", type=pathlib.Path)
    args = ap.parse_args()

    for path in args.paths:
        pixels, w, h = load(path)
        selftest(pixels, w, h, args.cw)
        rotated, nw, nh = turn(pixels, w, h, args.cw)
        path.write_bytes(encode(rotated, nw, nh))
        print(f"  {path.name:12} {w}x{h} -> {nw}x{nh}")


if __name__ == "__main__":
    sys.exit(main())
