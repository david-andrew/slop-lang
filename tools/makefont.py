#!/usr/bin/env python3
"""Bake the default SDF font atlas (ASCII 32..126) used by Jot's text rendering.
Output: lib/game/assets/font.png (grayscale SDF atlas) + font.txt (metrics)."""
import sys, math
from PIL import Image, ImageDraw, ImageFont

FONT = sys.argv[1] if len(sys.argv) > 1 else "/usr/share/fonts/google-noto-vf/NotoSans[wght].ttf"
OUT = sys.argv[2] if len(sys.argv) > 2 else "lib/game/assets/font"
CELL = 48          # output cell size
SCALE = 4          # supersampling factor for the distance computation
SPREAD = 6.0       # distance (output pixels) mapped to the full 0..255 range
PX = 34            # font size in output pixels

font = ImageFont.truetype(FONT, PX * SCALE)
try: font.set_variation_by_name("Medium")
except Exception: pass
ascent, descent = font.getmetrics()
H = CELL * SCALE
INF = 1e9

def edt(inside, w, h):
    """distance (in hi-res px) from each pixel to the nearest pixel whose state differs"""
    # 8SSEDT: grid of offset vectors
    g = [[(0, 0) if not inside[y][x] else (INF, INF) for x in range(w)] for y in range(h)]
    def d2(p): return p[0] * p[0] + p[1] * p[1]
    def cmp(grid, x, y, ox, oy):
        nx, ny = x + ox, y + oy
        if 0 <= nx < w and 0 <= ny < h:
            o = grid[ny][nx]
            c = (o[0] + ox, o[1] + oy)
            if d2(c) < d2(grid[y][x]): grid[y][x] = c
    for y in range(h):
        for x in range(w):
            cmp(g, x, y, -1, 0); cmp(g, x, y, 0, -1); cmp(g, x, y, -1, -1); cmp(g, x, y, 1, -1)
        for x in range(w - 1, -1, -1): cmp(g, x, y, 1, 0)
    for y in range(h - 1, -1, -1):
        for x in range(w - 1, -1, -1):
            cmp(g, x, y, 1, 0); cmp(g, x, y, 0, 1); cmp(g, x, y, -1, 1); cmp(g, x, y, 1, 1)
        for x in range(w): cmp(g, x, y, -1, 0)
    return [[math.sqrt(d2(g[y][x])) for x in range(w)] for y in range(h)]

cols, rows = 16, 6
atlas = Image.new("L", (cols * CELL, rows * CELL), 0)
metrics = []
baseline = int(CELL * 0.76)
for i, code in enumerate(range(32, 127)):
    ch = chr(code)
    img = Image.new("L", (H, H), 0)
    d = ImageDraw.Draw(img)
    adv = font.getlength(ch) / SCALE
    # draw so that the baseline is at `baseline` and the glyph starts at x = SPREAD
    x0 = SPREAD * SCALE
    d.text((x0, baseline * SCALE), ch, font=font, fill=255, anchor="ls")
    px = img.load()
    inside = [[px[x, y] > 127 for x in range(H)] for y in range(H)]
    outside = [[not v for v in row] for row in inside]
    dout = edt(inside, H, H)     # distance to ink for outside pixels
    din = edt(outside, H, H)     # distance to background for inside pixels
    cell = Image.new("L", (CELL, CELL))
    cp = cell.load()
    for y in range(CELL):
        for x in range(CELL):
            sx, sy = x * SCALE + SCALE // 2, y * SCALE + SCALE // 2
            dist = (dout[sy][sx] - din[sy][sx]) / SCALE   # positive inside the glyph
            v = 128 + dist / SPREAD * 127
            cp[x, y] = max(0, min(255, int(round(v))))
    atlas.paste(cell, ((i % cols) * CELL, (i // cols) * CELL))
    metrics.append(adv)
    print(f"\rglyph {i + 1}/95", end="", file=sys.stderr)
atlas.save(OUT + ".png", optimize=True)
with open(OUT + ".txt", "w") as f:
    f.write(f"{CELL} {cols} {rows} {baseline} {SPREAD} {PX} {ascent / SCALE:.2f} {descent / SCALE:.2f}\n")
    f.write(" ".join(f"{a:.3f}" for a in metrics) + "\n")
print("\ndone", file=sys.stderr)
