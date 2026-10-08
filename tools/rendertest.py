#!/usr/bin/env python3
"""Render regression test: draw frame 60 of the example games with the software renderer (no
GPU, no display) and compare with the reference frames in tests/render. The small scenes in
tests/render/*.jot check shader semantics: their references were rendered by a GPU.
usage: rendertest.py [--update]   (--update rewrites the references; scenes need a display)"""
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pngutil import downsample, png_rows, write_png

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
jot = os.path.join(root, "bin", "jot")
refdir = os.path.join(root, "tests", "render")
update = "--update" in sys.argv
os.makedirs("/tmp/jot-render", exist_ok=True)
games = {"cube": "examples/cube.jot", "lumen": "examples/lumen/lumen.jot", "dunes": "examples/dunes/dunes.jot"}
scenes = sorted(f[:-4] for f in os.listdir(refdir) if f.endswith(".jot"))
for sc in scenes:
    games[sc] = f"tests/render/{sc}.jot"
env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
env.update(JOT_LIB=os.path.join(root, "lib"), JOT_SOFTWARE="1", JOT_FRAMES="60")
LIMIT = 1.0           # mean absolute difference allowed (0..255), for other CPUs' rounding
failed = 0
for name, src in games.items():
    exe = f"/tmp/jot-render/{name}"
    r = subprocess.run([jot, "build", "--release", os.path.join(root, src), "-o", exe], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"FAIL {name}: build failed\n{r.stderr}")
        failed += 1
        continue
    png = f"/tmp/jot-render/{name}.png"
    r = subprocess.run([exe], env=dict(env, JOT_SCREENSHOT=png), capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not os.path.exists(png):
        print(f"FAIL {name}: render failed\n{r.stderr}")
        failed += 1
        continue
    w, h, got = downsample(png, 4)
    ref = os.path.join(refdir, f"{name}.png")
    if update:
        if name in scenes:
            # the truth for these is the GPU's frame
            if not os.environ.get("DISPLAY"):
                print(f"skipped {name} (needs a display)")
                continue
            gpu = f"/tmp/jot-render/{name}_gpu.png"
            genv = dict(os.environ, JOT_LIB=os.path.join(root, "lib"), JOT_FRAMES="60", JOT_SCREENSHOT=gpu)
            subprocess.run([exe], env=genv, capture_output=True, timeout=120)
            w, h, got = downsample(gpu, 4)
        write_png(ref, w, h, got)
        print(f"updated {name}")
        continue
    rw, rh, bpp, rows = png_rows(ref)
    want = b"".join(rows)
    if (rw, rh) != (w, h):
        print(f"FAIL {name}: size {w}x{h}, reference {rw}x{rh}")
        failed += 1
        continue
    d = sum(abs(a - b) for a, b in zip(got, want)) / len(want)
    print(f"{'ok  ' if d <= LIMIT else 'FAIL'} {name}: mean abs difference {d:.3f}")
    failed += d > LIMIT
print(f"{len(games) - failed} passed, {failed} failed")
sys.exit(1 if failed else 0)
