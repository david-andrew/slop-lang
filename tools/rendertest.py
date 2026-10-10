#!/usr/bin/env python3
"""Render regression test: draw frame 60 of the example games with the software renderer (no
GPU, no display) and compare with the reference frames in tests/render. The small scenes in
tests/render/*.jo check shader semantics: their references were rendered by a GPU.
With a display (or --gpu), each frame is also rendered on the GPU and compared with the same
references, which catches shader code that only the GPU driver compiles.
usage: rendertest.py [--update] [--gpu | --no-gpu]   (--update rewrites the references; scenes need a display)"""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pngutil import downsample, png_rows, write_png

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sloppy = os.path.join(root, "bin", "sloppy.exe" if os.name == "nt" else "sloppy")
out = os.path.join(tempfile.gettempdir(), "sloppy-render")
refdir = os.path.join(root, "tests", "render")
update = "--update" in sys.argv
has_display = bool(os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"))
gpu_too = ("--gpu" in sys.argv or has_display) and "--no-gpu" not in sys.argv and not update
GPU_FRAME_LIMIT = 4.0   # a whole game frame on a GPU (different rasterization and precision)
os.makedirs(out, exist_ok=True)
games = {"cube": "examples/cube.jo", "rebound": "examples/rebound/rebound.jo", "dunes": "examples/dunes/dunes.jo", "lowline": "examples/lowline/lowline.jo"}
scenes = sorted(f[:-3] for f in os.listdir(refdir) if f.endswith(".jo"))
for sc in scenes:
    games[sc] = f"tests/render/{sc}.jo"
env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
# (games that save progress start with nothing saved, so their frames do not depend on it)
import shutil
shutil.rmtree(os.path.join(out, "saved-data"), ignore_errors=True)
env.update(SLOPPY_LIB=os.path.join(root, "lib"), SLOPPY_SOFTWARE="1", SLOPPY_FRAMES="60", SLOPPY_SAVE_DIR=os.path.join(out, "saved-data"))
LIMIT = 1.0           # mean absolute difference allowed (0..255), for other CPUs' rounding
GPU_LIMIT = 2.0       # against a GPU's frame: the software renderer works at half resolution
failed = 0
for name, src in games.items():
    exe = os.path.join(out, name)
    r = subprocess.run([sloppy, "build", "--release", os.path.join(root, src), "-o", exe], capture_output=True, text=True)
    if os.name == "nt": exe += ".exe"
    if r.returncode != 0:
        print(f"FAIL {name}: build failed\n{r.stderr}")
        failed += 1
        continue
    png = os.path.join(out, f"{name}.png")
    r = subprocess.run([exe], env=dict(env, SLOPPY_SCREENSHOT=png), capture_output=True, text=True, timeout=300)
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
            gpu = os.path.join(out, f"{name}_gpu.png")
            genv = dict(os.environ, SLOPPY_LIB=os.path.join(root, "lib"), SLOPPY_FRAMES="60", SLOPPY_SCREENSHOT=gpu, SLOPPY_SCALE="1")
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
    limit = GPU_LIMIT if name in scenes else LIMIT
    print(f"{'ok  ' if d <= limit else 'FAIL'} {name}: mean abs difference {d:.3f}")
    failed += d > limit
    if gpu_too:
        gpng = os.path.join(out, f"{name}_gpu.png")
        if os.path.exists(gpng): os.remove(gpng)
        genv = dict(os.environ, SLOPPY_LIB=os.path.join(root, "lib"), SLOPPY_FRAMES="60", SLOPPY_SCREENSHOT=gpng, SLOPPY_SCALE="1")
        genv.pop("SLOPPY_SOFTWARE", None)
        r = subprocess.run([exe], env=genv, capture_output=True, text=True, timeout=300)
        if r.returncode != 0 or not os.path.exists(gpng):
            print(f"FAIL {name} (GPU): render failed\n{r.stderr[-2000:]}")
            failed += 1
            continue
        if "software renderer" in r.stderr:
            print(f"skip {name} (GPU): no GPU driver")
            continue
        w2, h2, got2 = downsample(gpng, 4)
        if (w2, h2) != (rw, rh):
            print(f"FAIL {name} (GPU): size {w2}x{h2}, reference {rw}x{rh}")
            failed += 1
            continue
        d2 = sum(abs(a - b) for a, b in zip(got2, want)) / len(want)
        print(f"{'ok  ' if d2 <= GPU_FRAME_LIMIT else 'FAIL'} {name} (GPU): mean abs difference {d2:.3f}")
        failed += d2 > GPU_FRAME_LIMIT
print(f"{len(games) * (2 if gpu_too else 1) - failed} passed, {failed} failed")
sys.exit(1 if failed else 0)
