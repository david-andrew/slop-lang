#!/usr/bin/env python3
"""Write tiny.ttf: a minimal TrueType font for tests/t/font.jo. Glyphs: 0 .notdef, 1 'I' (a
rectangle), 2 'O' (a quadratic ring: off-curve points, two in a row), 3 'L' (a composite: two
copies of 'I', one moved and scaled), 4 space; 1000 units per em."""
import struct, os

def simple(contours):
    # contours: lists of (x, y, on_curve)
    xs = [p[0] for c in contours for p in c]; ys = [p[1] for c in contours for p in c]
    out = struct.pack(">hhhhh", len(contours), min(xs), min(ys), max(xs), max(ys))
    n = 0
    for c in contours:
        n += len(c); out += struct.pack(">H", n - 1)
    out += struct.pack(">H", 0)                     # no instructions
    flags = b""; xd = b""; yd = b""
    px = py = 0
    for c in contours:
        for (x, y, on) in c:
            flags += bytes([1 if on else 0])        # (long coordinates: plain 16-bit deltas)
            xd += struct.pack(">h", x - px); yd += struct.pack(">h", y - py)
            px, py = x, y
    out += flags + xd + yd
    return out + b"\0" * (len(out) % 2)

def composite(parts):
    # parts: (glyph, dx, dy, scale or None)
    out = struct.pack(">hhhhh", -1, 0, 0, 0, 0)
    for i, (g, dx, dy, sc) in enumerate(parts):
        flags = 1 | 2                               # word offsets, xy values
        if sc is not None: flags |= 8
        if i < len(parts) - 1: flags |= 0x20
        out += struct.pack(">HHhh", flags, g, dx, dy)
        if sc is not None: out += struct.pack(">h", int(sc * 16384))
    return out

glyphs = [b"",
          simple([[(100, 0, 1), (100, 700, 1), (300, 700, 1), (300, 0, 1)]]),
          simple([[(500, 0, 1), (100, 0, 0), (100, 700, 0), (500, 700, 1), (900, 700, 0), (900, 0, 0)]]),
          composite([(1, 0, 0, None), (1, 200, 0, 0.5)]),
          b""]
advances = [500, 400, 1000, 700, 300]
glyf = b"".join(glyphs)
loca = b""; o = 0
for g in glyphs:
    loca += struct.pack(">I", o); o += len(g)
loca += struct.pack(">I", o)
head = struct.pack(">IIIIHHqqhhhhHHhhh", 0x10000, 0x10000, 0, 0x5F0F3CF5, 0, 1000, 0, 0, 0, 0, 1000, 1000, 0, 8, 2, 1, 0)
hhea = struct.pack(">Ihhh" + "H" + "hhh" + "hhh" + "hhhhh" + "H", 0x10000, 800, -200, 0, 1000, 0, 0, 1000, 1, 0, 0, 0, 0, 0, 0, 0, len(glyphs))
maxp = struct.pack(">IH", 0x5000, len(glyphs))
hmtx = b"".join(struct.pack(">Hh", a, 0) for a in advances)
# cmap format 4: ' ' -> 4, 'I' -> 1, 'L' -> 3, 'O' -> 2
segs = [(32, 32, 4 - 32), (73, 73, 1 - 73), (76, 76, 3 - 76), (79, 79, 2 - 79), (0xFFFF, 0xFFFF, 1)]
n = len(segs)
f4 = struct.pack(">HHHHHHH", 4, 16 + 8 * n, 0, 2 * n, 2, 1, 0)
f4 += b"".join(struct.pack(">H", s[1]) for s in segs) + b"\0\0"
f4 += b"".join(struct.pack(">H", s[0]) for s in segs)
f4 += b"".join(struct.pack(">h", ((s[2] + 32768) % 65536) - 32768) for s in segs)
f4 += b"\0\0" * n
cmap = struct.pack(">HHHHI", 0, 1, 3, 1, 12) + f4
tables = {b"cmap": cmap, b"glyf": glyf, b"head": head, b"hhea": hhea, b"hmtx": hmtx, b"loca": loca, b"maxp": maxp}
out = struct.pack(">IHHHH", 0x10000, len(tables), 0, 0, 0)
offset = 12 + 16 * len(tables)
body = b""
for tag in sorted(tables):
    data = tables[tag]
    out += tag + struct.pack(">III", 0, offset + len(body), len(data))
    body += data + b"\0" * ((4 - len(data) % 4) % 4)
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "tiny.ttf"), "wb").write(out + body)
