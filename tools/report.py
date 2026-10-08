#!/usr/bin/env python3
"""Measure how well Jot meets its requirements and write docs/REPORT.md.

usage: tools/report.py [--quick]      (--quick skips the bootstrap and the browser checks)

Sections: self-hosting, tests, compile speed (vs tcc / gcc -O0), script latency, runtime
performance (vs C), parallel speedup, static binaries, web builds (single HTML file loaded
from file:// in headless Chrome), game frame times.
"""
import os, re, shutil, subprocess, sys, time, glob, struct, zlib, platform
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pngutil import png_rows, png_colors, png_diff

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
JOT = os.path.join(ROOT, "bin", "jot")
ENV = dict(os.environ, JOT_LIB=os.path.join(ROOT, "lib"), JOT_NO_AUDIO="1")
QUICK = "--quick" in sys.argv
BUILD = os.path.join(ROOT, "build", "report")
os.makedirs(BUILD, exist_ok=True)
out = []


def say(s=""):
    print(s)
    out.append(s)


def run(cmd, timeout=600, env=ENV):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)


def cpu_time(cmd, n=5, env=ENV):
    """best user+sys CPU time of n runs (robust against a busy machine)"""
    best = None
    for _ in range(n):
        r = subprocess.run(["/usr/bin/time", "-f", "%U %S"] + cmd, capture_output=True, text=True, env=env)
        if r.returncode != 0:
            raise RuntimeError(f"{' '.join(cmd)} failed:\n{r.stderr[-2000:]}")
        u, s = r.stderr.strip().splitlines()[-1].split()
        t = float(u) + float(s)
        best = t if best is None else min(best, t)
    return best


def wall_time(cmd, n=5, env=ENV):
    best = None
    for _ in range(n):
        t0 = time.perf_counter()
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        t = time.perf_counter() - t0
        if r.returncode != 0:
            raise RuntimeError(f"{' '.join(cmd)} failed:\n{r.stderr[-2000:]}")
        best = t if best is None else min(best, t)
    return best


def instructions(cmd):
    icount = os.path.join(ROOT, "tools", "icount")
    if not os.path.exists(icount):
        subprocess.run(["gcc", "-O2", "-o", icount, icount + ".c"], check=True)
    r = run([icount] + cmd)
    m = re.search(r"([\d.]+) G instructions", r.stderr)
    return float(m.group(1)) if m else None


def fmt_ratio(x):
    return f"{x:.2f}x"


# ---------------------------------------------------------------------------
say("# Jot requirements report")
say()
say(f"Generated {time.strftime('%Y-%m-%d %H:%M')} on {platform.machine()} Linux "
    f"({os.cpu_count()} hardware threads). Load average at start: {os.getloadavg()[0]:.1f}. "
    "Times are best-of-N CPU times (user + sys) unless noted; instruction counts are exact.")
say()

# ---------------- self-hosting ----------------
say("## 1. Self-hosting")
say()
if not QUICK:
    r = run(["sh", "tools/bootstrap.sh"])
    ok = r.returncode == 0 and "fixed point" in r.stdout
    say(f"- C bootstrap -> jot1 -> jot2 -> jot3, jot2 == jot3 byte for byte: **{'yes' if ok else 'NO'}**")
else:
    say("- (bootstrap skipped with --quick)")
src_lines = sum(len(open(f).read().splitlines()) for f in glob.glob("compiler/*.jot"))
lib_lines = sum(len(open(f).read().splitlines()) for f in glob.glob("lib/*/*.jot"))
say(f"- compiler: {src_lines} lines of Jot; standard library: {lib_lines} lines of Jot")
say(f"- `bin/jot` size: {os.path.getsize(JOT) // 1024} KB, built by itself in release mode")
say()

# ---------------- tests ----------------
say("## 2. Tests")
say()
say("| mode | result |")
say("|---|---|")
for label, args in [("native, debug", []), ("native, release", ["--release"]),
                    ("web (wasm under node), debug", ["--target", "wasm"]),
                    ("web (wasm under node), release", ["--target", "wasm", "--release"]),
                    ("C bootstrap compiler", None)]:
    cmd = ["python3", "tools/runtests.py"] + (["--compiler", "jot0"] if args is None else ["--compiler", "jot"] + args)
    r = run(cmd)
    last = (r.stdout.strip().splitlines() or ["?"])[-1]
    say(f"| {label} | {last} |")
say()

# ---------------- compile speed ----------------
say("## 3. Compile speed")
say()
if not os.path.exists("bench/big.jot"):
    run(["python3", "tools/genbench.py"])
lines = len(open("bench/big.jot").read().splitlines())
clines = len(open("bench/big.c").read().splitlines())
dbg = cpu_time([JOT, "build", "bench/big.jot", "-o", f"{BUILD}/big"])
rel = cpu_time([JOT, "build", "bench/big.jot", "-o", f"{BUILD}/big_r", "--release"], n=3)
di = instructions([JOT, "build", "bench/big.jot", "-o", f"{BUILD}/big"])
ri = instructions([JOT, "build", "bench/big.jot", "-o", f"{BUILD}/big_r", "--release"])
say(f"Generated program `bench/big.jot`: {lines} lines (2000 functions, loops, structs, strings, floats), "
    f"and the equivalent C program `bench/big.c` ({clines} lines).")
say()
say("| compiler | CPU time | lines / second | instructions |")
say("|---|---|---|---|")
say(f"| jot (debug build) | {dbg:.3f} s | {lines / dbg:,.0f} | {di:.2f} G |")
say(f"| jot (release build) | {rel:.3f} s | {lines / rel:,.0f} | {ri:.2f} G |")
tcc = shutil.which("tcc") or ("/tmp/tcc-install/bin/tcc" if os.path.exists("/tmp/tcc-install/bin/tcc") else None)
if tcc:
    t = cpu_time([tcc, "bench/big.c", "-o", f"{BUILD}/bigc_tcc", "-lm"])
    ti = instructions([tcc, "bench/big.c", "-o", f"{BUILD}/bigc_tcc", "-lm"])
    say(f"| tcc | {t:.3f} s | {clines / t:,.0f} | {ti:.2f} G |")
if shutil.which("gcc"):
    t = cpu_time(["gcc", "-O0", "bench/big.c", "-o", f"{BUILD}/bigc_gcc", "-lm"], n=1)
    say(f"| gcc -O0 | {t:.3f} s | {clines / t:,.0f} | |")
say()
say(f"Release builds take {rel / dbg:.1f}x the time of debug builds (requirement: at most 10x).")
say()

# ---------------- script latency ----------------
say("## 4. Script workflow (`jot file.jot`: compile + run)")
say()
say("| program | lines | compile + run (wall) |")
say("|---|---|---|")
hello = os.path.join(BUILD, "hello.jot")
open(hello, "w").write('print("hello, world")\n')
t = wall_time([JOT, hello])
say(f"| hello world | 1 | {t * 1000:.0f} ms |")
for g in ["examples/lumen/lumen.jot", "examples/dunes/dunes.jot"]:
    n = len(open(g).read().splitlines())
    t = wall_time([JOT, "build", g, "-o", f"{BUILD}/g"])
    say(f"| {g} (compile only) | {n} | {t * 1000:.0f} ms |")
say()

# ---------------- runtime performance ----------------
say("## 5. Runtime performance vs C")
say()
say("Each benchmark exists as Jot and as equivalent C (`bench/rt`). Ratios are Jot time / C time (lower is better).")
say()
say("| benchmark | C -O2 | C -O0 | Jot release | Jot debug | release / C -O2 |")
say("|---|---|---|---|---|---|")
ratios = []
for src in sorted(glob.glob("bench/rt/*.jot")):
    name = os.path.basename(src)[:-4]
    csrc = src[:-4] + ".c"
    if not os.path.exists(csrc):
        continue
    run(["gcc", "-O2", "-o", f"{BUILD}/{name}_c2", csrc, "-lm"])
    run(["gcc", "-O0", "-o", f"{BUILD}/{name}_c0", csrc, "-lm"])
    run([JOT, "build", src, "-o", f"{BUILD}/{name}_jd"])
    run([JOT, "build", src, "-o", f"{BUILD}/{name}_jr", "--release"])
    outs = {v: run([f"{BUILD}/{name}_{v}"]).stdout for v in ["c2", "jr", "jd"]}
    same = outs["c2"] == outs["jr"] == outs["jd"]
    c2 = cpu_time([f"{BUILD}/{name}_c2"], n=3)
    c0 = cpu_time([f"{BUILD}/{name}_c0"], n=3)
    jr = cpu_time([f"{BUILD}/{name}_jr"], n=3)
    jd = cpu_time([f"{BUILD}/{name}_jd"], n=3)
    ratios.append(jr / c2)
    say(f"| {name}{'' if same else ' (OUTPUT DIFFERS)'} | {c2:.2f} s | {c0:.2f} s | {jr:.2f} s | {jd:.2f} s | {fmt_ratio(jr / c2)} |")
if ratios:
    geo = 1.0
    for r_ in ratios:
        geo *= r_
    geo **= 1.0 / len(ratios)
    say()
    say(f"Geometric mean, Jot release / C -O2: **{fmt_ratio(geo)}**.")
say()

# ---------------- parallelism ----------------
say("## 6. CPU parallelism")
say()
par = os.path.join(BUILD, "par.jot")
open(par, "w").write('''build:
    opt = release
fn collatz(n0: int) -> int:
    n := n0
    s := 0
    while n != 1:
        if n % 2 == 0: n /= 2
        else: n = 3 * n + 1
        s += 1
    s
fn main():
    xs: [int]
    for i in 1..1000001: xs.push(i)
    t0 := time()
    a := xs.map(fn(x): collatz(x))
    t1 := time()
    b := parallel_map(xs, fn(x): collatz(x))
    t2 := time()
    print(a == b, cpu_count(), (t1 - t0) / (t2 - t1))
''')
r = run([JOT, par])
try:
    same, cpus, speed = r.stdout.split()
    say(f"`parallel_map` over 1M Collatz lengths on {cpus} hardware threads: **{float(speed):.1f}x** faster than "
        f"`map` (results identical: {same}).")
except ValueError:
    say(f"parallel benchmark failed: {r.stdout} {r.stderr}")
say()

# ---------------- static binaries ----------------
say("## 7. Native executables are static")
say()
run([JOT, "build", hello, "-o", f"{BUILD}/hello"])
ph = run(["readelf", "-lW", f"{BUILD}/hello"]).stdout
dy = run(["readelf", "-dW", f"{BUILD}/hello"]).stdout
static = "INTERP" not in ph and "NEEDED" not in dy
say(f"- hello world: {os.path.getsize(f'{BUILD}/hello')} bytes; no program interpreter and no shared library "
    f"dependencies: **{'yes' if static else 'NO'}**")
run([JOT, "build", "examples/dunes/dunes.jot", "-o", f"{BUILD}/dunes"])
ph = run(["readelf", "-lW", f"{BUILD}/dunes"]).stdout
dy = run(["readelf", "-dW", f"{BUILD}/dunes"]).stdout
say(f"- 3D game (dunes): {os.path.getsize(f'{BUILD}/dunes') // 1024} KB; static: "
    f"**{'yes' if 'INTERP' not in ph and 'NEEDED' not in dy else 'NO'}** (the GPU driver is loaded at run time "
    "if present; without one it renders in software, see section 10)")
say("- the compiler writes machine code and ELF files itself: no assembler, linker or C toolchain is used")
say()

# ---------------- web ----------------
say("## 8. Web builds")
say()
chrome = shutil.which("google-chrome") or shutil.which("chromium")
webdir = os.path.join(ROOT, "build", "report-web")
os.makedirs(webdir, exist_ok=True)
for g in ["lumen", "dunes"]:
    html = os.path.join(webdir, f"{g}.html")
    r = run([JOT, "build", f"examples/{g}/{g}.jot", "-o", html, "--target", "wasm"])
    text = open(html).read()
    external = re.findall(r'(?:src|href)\s*=\s*"(?!data:)[^"]+"', text)
    line = f"- {g}: single file `{os.path.basename(html)}`, {len(text) // 1024} KB, external references: {len(external)}"
    if chrome and not QUICK:
        png = os.path.join(webdir, f"{g}.png")
        if os.path.exists(png):
            os.remove(png)
        cmd = [chrome, "--headless=new", "--no-sandbox", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
               "--hide-scrollbars", f"--screenshot={png}", "--window-size=1280,720", "--virtual-time-budget=4000",
               "file://" + html]
        if open(chrome).read(200).find("flatpak") >= 0:
            cmd = ["flatpak", "run", f"--filesystem={webdir}", "com.google.Chrome"] + cmd[1:]
        r = run(cmd, timeout=120)
        errors = [l for l in r.stderr.splitlines() if "GL_INVALID" in l or "Uncaught" in l]
        ncol = png_colors(png) if os.path.exists(png) else 0
        line += f"; opened from file:// in headless Chrome: {ncol} distinct colors in the frame" + \
                (", **renders**" if ncol > 50 and not errors else f", **PROBLEM** ({len(errors)} errors)")
    say(line)
say()

# ---------------- games ----------------
say("## 9. Games (native, OpenGL ES 3)")
say()
if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
    say("| game | mode | frame CPU time (update + draw + submit) | screenshot |")
    say("|---|---|---|---|")
    for g in ["lumen", "dunes"]:
        for mode in ["debug", "release"]:
            exe = f"{BUILD}/{g}_{mode}"
            run([JOT, "build", f"examples/{g}/{g}.jot", "-o", exe] + (["--release"] if mode == "release" else []))
            png = f"{BUILD}/{g}_{mode}.png"
            env = dict(ENV, JOT_FRAMES="240", JOT_SCREENSHOT=png, JOT_FRAME_STATS="1")
            r = run([exe], env=env, timeout=120)
            m = re.search(r"frame cpu: ([\d.]+) ms", r.stderr)
            ncol = png_colors(png) if os.path.exists(png) else 0
            say(f"| {g} | {mode} | {m.group(1) + ' ms' if m else 'n/a'} | {ncol} colors |")
else:
    say("(no display: skipped)")
say()

# ---------------- software rendering ----------------
say("## 10. Without a GPU driver (software renderer)")
say()
say("With no OpenGL ES driver (or `JOT_SOFTWARE=1`) the same binaries draw with a multithreaded software "
    "renderer that runs the Jot shader functions on the CPU, at half resolution. Without libX11 it speaks "
    "the X11 protocol itself, and screenshot runs need no display at all. Below, frame 60 of each game "
    "rendered with no display and no GPU, compared with the GPU's frame:")
say()
say("| game | software frame CPU time | mean abs difference vs GPU frame (0-255) |")
say("|---|---|---|")
has_display = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
for g in ["cube", "lumen", "dunes"]:
    src = f"examples/{g}.jot" if g == "cube" else f"examples/{g}/{g}.jot"
    exe = f"{BUILD}/{g}_sw"
    run([JOT, "build", src, "-o", exe, "--release"])
    soft_png = f"{BUILD}/{g}_soft.png"
    env = {k: v for k, v in ENV.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
    env.update(JOT_SOFTWARE="1", JOT_FRAMES="60", JOT_SCREENSHOT=soft_png, JOT_FRAME_STATS="1")
    r = run([exe], env=env, timeout=300)
    m = re.search(r"frame cpu: ([\d.]+) ms", r.stderr)
    diff = "n/a (no display for the GPU frame)"
    if has_display:
        gpu_png = f"{BUILD}/{g}_gpu.png"
        run([exe], env=dict(ENV, JOT_FRAMES="60", JOT_SCREENSHOT=gpu_png), timeout=120)
        if os.path.exists(soft_png) and os.path.exists(gpu_png):
            d = png_diff(soft_png, gpu_png)
            diff = f"{d:.2f}" if d is not None else "size mismatch"
    say(f"| {g} | {m.group(1) + ' ms' if m else 'FAILED'} | {diff} |")
say()

open("docs/REPORT.md", "w").write("\n".join(out) + "\n")
print("\nwrote docs/REPORT.md")
