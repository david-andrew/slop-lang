"""Small PNG helpers for the test tools (standard library only)."""
import struct, zlib


def png_rows(path, every=1):
    """decode an 8-bit RGB/RGBA PNG: (width, height, bytes per pixel, [rows]) keeping every n-th row"""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return 0, 0, 0, []
    pos, idat, w, h, ct = 8, b"", 0, 0, 0
    while pos < len(data):
        ln, typ = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, _, ct = struct.unpack(">IIBB", body[:10])
        elif typ == b"IDAT":
            idat += body
        pos += 12 + ln
    raw = zlib.decompress(idat)
    bpp = {2: 3, 6: 4}.get(ct, 4)
    stride = w * bpp + 1
    rows = []
    prev = bytearray(w * bpp)
    for y in range(h):
        f = raw[y * stride]
        row = bytearray(raw[y * stride + 1:(y + 1) * stride])
        if f != 0:
            for i in range(len(row)):
                a = row[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                if f == 1: row[i] = (row[i] + a) & 255
                elif f == 2: row[i] = (row[i] + b) & 255
                elif f == 3: row[i] = (row[i] + (a + b) // 2) & 255
                elif f == 4:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        if y % every == 0:
            rows.append(bytes(row))
        prev = row
    return w, h, bpp, rows


def png_colors(path):
    """number of distinct colors in a PNG (a rendered frame has many; a blank one has 1)"""
    w, h, bpp, rows = png_rows(path, 16)
    colors = set()
    for row in rows:
        for x in range(0, w, 8):
            colors.add(bytes(row[x * bpp:x * bpp + 3]))
    return len(colors)


def png_diff(a, b):
    """mean absolute difference of the RGB channels of two same-sized PNGs (0..255), sampled"""
    wa, ha, pa, ra = png_rows(a, 4)
    wb, hb, pb, rb = png_rows(b, 4)
    if (wa, ha) != (wb, hb) or not ra:
        return None
    total = n = 0
    for x_row, y_row in zip(ra, rb):
        for x in range(0, wa, 2):
            for ch in range(3):
                total += abs(x_row[x * pa + ch] - y_row[x * pb + ch])
                n += 1
    return total / n


def downsample(path, k):
    """(w, h, RGB bytes) of a PNG, keeping every k-th pixel of every k-th row"""
    w, h, bpp, rows = png_rows(path, k)
    out = bytearray()
    for row in rows:
        for x in range(0, w, k):
            out += row[x * bpp:x * bpp + 3]
    return (w + k - 1) // k, len(rows), bytes(out)


def write_png(path, w, h, rgb):
    raw = b"".join(b"\0" + rgb[y * w * 3:(y + 1) * w * 3] for y in range(h))
    def chunk(t, body):
        return struct.pack(">I", len(body)) + t + body + struct.pack(">I", zlib.crc32(t + body) & 0xFFFFFFFF)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    open(path, "wb").write(data)
