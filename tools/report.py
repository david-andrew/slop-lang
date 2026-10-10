#!/usr/bin/env python3
"""Measure how well Sloppy meets its requirements and write docs/REPORT.md.

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
SLOPPY = os.path.join(ROOT, "bin", "sloppy")
ENV = dict(os.environ, SLOPPY_LIB=os.path.join(ROOT, "lib"), SLOPPY_NO_AUDIO="1")
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
say("# Sloppy requirements report")
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
    say(f"- C bootstrap -> sloppy1 -> sloppy2 -> sloppy3, sloppy2 == sloppy3 byte for byte: **{'yes' if ok else 'NO'}**")
else:
    say("- (bootstrap skipped with --quick)")
src_lines = sum(len(open(f).read().splitlines()) for f in glob.glob("compiler/*.jo"))
lib_lines = sum(len(open(f).read().splitlines()) for f in glob.glob("lib/*/*.jo"))
say(f"- compiler: {src_lines} lines of Sloppy; standard library: {lib_lines} lines of Sloppy")
say(f"- `bin/sloppy` size: {os.path.getsize(SLOPPY) // 1024} KB, built by itself in release mode")
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
    cmd = ["python3", "tools/runtests.py"] + (["--compiler", "sloppy0"] if args is None else ["--compiler", "sloppy"] + args)
    r = run(cmd)
    last = (r.stdout.strip().splitlines() or ["?"])[-1]
    say(f"| {label} | {last} |")
r = run(["python3", "tools/lsptest.py", SLOPPY], timeout=300)
say(f"| language server (`sloppy lsp`, driven as an editor would) | {(r.stdout.strip().splitlines() or ['?'])[-1]} |")
r = run(["python3", "tools/rendertest.py"], timeout=1200)
say(f"| rendering (software renderer vs references; also on the GPU when there is a display) | {(r.stdout.strip().splitlines() or ['?'])[-1]} |")
if not QUICK:
    r = run(["python3", "tools/fuzz.py", "60"], timeout=3000)
    say(f"| differential fuzzing: random programs (unions, closures, soa, n-D arrays...) built 4 ways (+ the C bootstrap compiler for its subset) | {(r.stdout.strip().splitlines() or ['?'])[-1]} |")
say()

# ---------------- compile speed ----------------
say("## 3. Compile speed")
say()
if not os.path.exists("bench/big.jo"):
    run(["python3", "tools/genbench.py", "2000", "bench/big"])
lines = len(open("bench/big.jo").read().splitlines())
clines = len(open("bench/big.c").read().splitlines())
dbg = cpu_time([SLOPPY, "build", "bench/big.jo", "-o", f"{BUILD}/big"])
rel = cpu_time([SLOPPY, "build", "bench/big.jo", "-o", f"{BUILD}/big_r", "--release"], n=3)
di = instructions([SLOPPY, "build", "bench/big.jo", "-o", f"{BUILD}/big"])
ri = instructions([SLOPPY, "build", "bench/big.jo", "-o", f"{BUILD}/big_r", "--release"])
say(f"Generated program `bench/big.jo`: {lines} lines (2000 functions, loops, structs, strings, floats), "
    f"and the equivalent C program `bench/big.c` ({clines} lines).")
say()
say("| compiler | CPU time | lines / second | instructions |")
say("|---|---|---|---|")
say(f"| sloppy (debug build) | {dbg:.3f} s | {lines / dbg:,.0f} | {di:.2f} G |")
say(f"| sloppy (release build) | {rel:.3f} s | {lines / rel:,.0f} | {ri:.2f} G |")
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
say("## 4. Script workflow (`sloppy file.jo`: compile + run)")
say()
say("| program | lines | compile + run (wall) |")
say("|---|---|---|")
hello = os.path.join(BUILD, "hello.jo")
open(hello, "w").write('print("hello, world")\n')
t = wall_time([SLOPPY, hello])
say(f"| hello world | 1 | {t * 1000:.0f} ms |")
for g in ["examples/rebound/rebound.jo", "examples/dunes/dunes.jo"]:
    n = len(open(g).read().splitlines())
    t = wall_time([SLOPPY, "build", g, "-o", f"{BUILD}/g"])
    say(f"| {g} (compile only) | {n} | {t * 1000:.0f} ms |")
say()

# ---------------- runtime performance ----------------
say("## 5. Runtime performance vs C")
say()
say("Each benchmark exists as Sloppy and as equivalent C (`bench/rt`). Ratios are Sloppy time / C time (lower is better).")
say()
say("| benchmark | C -O2 | C -O0 | Sloppy release | Sloppy debug | release / C -O2 |")
say("|---|---|---|---|---|---|")
ratios = []
for src in sorted(glob.glob("bench/rt/*.jo")):
    name = os.path.basename(src)[:-3]
    csrc = src[:-3] + ".c"
    if not os.path.exists(csrc):
        continue
    run(["gcc", "-O2", "-o", f"{BUILD}/{name}_c2", csrc, "-lm"])
    run(["gcc", "-O0", "-o", f"{BUILD}/{name}_c0", csrc, "-lm"])
    run([SLOPPY, "build", src, "-o", f"{BUILD}/{name}_jd"])
    run([SLOPPY, "build", src, "-o", f"{BUILD}/{name}_jr", "--release"])
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
    say(f"Geometric mean, Sloppy release / C -O2: **{fmt_ratio(geo)}**.")
say()
say("Hot loops of a game (`bench/loops`): nanoseconds per element, Sloppy release vs C -O2 (the C dotted "
    "expression also makes a new array each time):")
say()
say("| loop | C -O2 | Sloppy release | ratio |")
say("|---|---|---|---|")
run(["gcc", "-O2", "-o", f"{BUILD}/loops_c", "bench/loops/loops.c", "-lm"])
run([SLOPPY, "build", "bench/loops/loops.jo", "-o", f"{BUILD}/loops_j"])
def loop_times(exe):
    best = {}
    for _ in range(3):
        for line in run([exe]).stdout.splitlines():
            k, v = line.split()
            if k != "check": best[k] = min(best.get(k, 1e9), float(v))
    return best
lc = loop_times(f"{BUILD}/loops_c")
lj = loop_times(f"{BUILD}/loops_j")
for k in lc:
    if k in lj: say(f"| {k.replace('_', ' ')} | {lc[k]:.2f} ns | {lj[k]:.2f} ns | {fmt_ratio(lj[k] / lc[k])} |")
say()

say("Loops the compiler vectorizes (`bench/simd`, arrays that fit in the cache): nanoseconds per element. "
    "Sloppy uses AVX2 where the processor has it and SSE2 otherwise (`SLOPPY_NO_AVX=1` forces SSE2), from one "
    "executable; gcc -O2 vectorizes with SSE2, the x86-64 baseline:")
say()
run(["gcc", "-O2", "-o", f"{BUILD}/simd_c", "bench/simd/simd.c"])
run([SLOPPY, "build", "bench/simd/simd.jo", "-o", f"{BUILD}/simd_j"])
def simd_times(cmd, env=None):
    best = {}
    vals = {}
    for _ in range(3):
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        for line in r.stdout.splitlines():
            k, v, x = line.split()
            best[k] = min(best.get(k, 1e9), float(v))
            vals[k] = x
    return best, vals
sc, scv = simd_times([f"{BUILD}/simd_c"])
sa, sav = simd_times([f"{BUILD}/simd_j"])
ss, ssv = simd_times([f"{BUILD}/simd_j"], dict(os.environ, SLOPPY_NO_AVX="1"))
avx = " avx2" in open("/proc/cpuinfo").read()
say(f"| loop | C -O2 | Sloppy (AVX2{'' if avx else ': not on this machine, so SSE2'}) | Sloppy (SSE2) | same results |")
say("|---|---|---|---|---|")
for k in sc:
    if k in sa:
        same = sav[k] == ssv[k]
        say(f"| {k.replace('_', ' ')} | {sc[k]:.3f} ns | {sa[k]:.3f} ns | {ss[k]:.3f} ns | {'yes' if same else 'NO'} |")
say()

say("Game logic (`bench/game/swarm`: 3000 agents flocking, a spatial hash, shooting, events, "
    "respawning, sorting, strings; no window), milliseconds per frame. The C version (`swarm.c`) is "
    "what a C programmer would write (buffers reused, its own random numbers):")
say()
run(["gcc", "-O2", "-o", f"{BUILD}/swarm_c", "bench/game/swarm.c", "-lm"])
run([SLOPPY, "build", "bench/game/swarm.jo", "-o", f"{BUILD}/swarm_jr", "--release"])
run([SLOPPY, "build", "bench/game/swarm.jo", "-o", f"{BUILD}/swarm_jd"])
def frame_ms(exe):
    best = 1e9
    for _ in range(3):
        r = run([exe])
        best = min(best, float(r.stderr.split()[0]))
    return best
fc = frame_ms(f"{BUILD}/swarm_c")
fr = frame_ms(f"{BUILD}/swarm_jr")
fd = frame_ms(f"{BUILD}/swarm_jd")
say("| C -O2 | Sloppy release | Sloppy debug | release / C |")
say("|---|---|---|---|")
say(f"| {fc:.2f} ms | {fr:.2f} ms | {fd:.2f} ms | {fmt_ratio(fr / fc)} |")
say()

# ---------------- parallelism ----------------
say("## 6. CPU parallelism")
say()
par = os.path.join(BUILD, "par.jo")
open(par, "w").write('''build:
    opt = release
collatz = (n0: int) -> int:
    n = n0
    s = 0
    loop n != 1:
        if n % 2 == 0: n /= 2
        else: n = 3 * n + 1
        s += 1
    s
main = ():
    xs = [1..1000000]
    t0 = time()
    a = xs.map((x): collatz(x))
    t1 = time()
    b = parallel_map(xs, (x): collatz(x))
    t2 = time()
    print(a == b, cpu_count(), (t1 - t0) / (t2 - t1))
''')
r = run([SLOPPY, par])
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
run([SLOPPY, "build", hello, "-o", f"{BUILD}/hello"])
ph = run(["readelf", "-lW", f"{BUILD}/hello"]).stdout
dy = run(["readelf", "-dW", f"{BUILD}/hello"]).stdout
static = "INTERP" not in ph and "NEEDED" not in dy
say(f"- hello world: {os.path.getsize(f'{BUILD}/hello')} bytes; no program interpreter and no shared library "
    f"dependencies: **{'yes' if static else 'NO'}**")
run([SLOPPY, "build", "examples/dunes/dunes.jo", "-o", f"{BUILD}/dunes"])
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
for g in ["rebound", "dunes"]:
    html = os.path.join(webdir, f"{g}.html")
    r = run([SLOPPY, "build", f"examples/{g}/{g}.jo", "-o", html, "--target", "wasm"])
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
    say("| game | mode | frame CPU time (update + draw + submit) | pixels, how frames reach the screen | screenshot |")
    say("|---|---|---|---|---|")
    for g in ["rebound", "dunes"]:
        for mode in ["debug", "release"]:
            exe = f"{BUILD}/{g}_{mode}"
            run([SLOPPY, "build", f"examples/{g}/{g}.jo", "-o", exe] + (["--release"] if mode == "release" else []))
            png = f"{BUILD}/{g}_{mode}.png"
            env = dict(ENV, SLOPPY_FRAMES="240", SLOPPY_SCREENSHOT=png, SLOPPY_FRAME_STATS="1")
            r = run([exe], env=env, timeout=120)
            m = re.search(r"frame cpu: ([\d.]+) ms", r.stderr)
            how = re.search(r"ms; (.*)$", r.stderr.strip())
            ncol = png_colors(png) if os.path.exists(png) else 0
            say(f"| {g} | {mode} | {m.group(1) + ' ms' if m else 'n/a'} | {how.group(1) if how else 'n/a'} | {ncol} colors |")
else:
    say("(no display: skipped)")
say()

# ---------------- software rendering ----------------
say("## 10. Without a GPU driver (software renderer)")
say()
say("With no OpenGL ES driver (or `SLOPPY_SOFTWARE=1`) the same binaries draw with a multithreaded software "
    "renderer that runs the Sloppy shader functions on the CPU, at half resolution. Without libX11 it speaks "
    "the X11 protocol itself, and screenshot runs need no display at all. Below, frame 60 of each game "
    "rendered with no display and no GPU, compared with the GPU's frame:")
say()
say("| game | software frame CPU time | mean abs difference vs GPU frame (0-255) |")
say("|---|---|---|")
has_display = os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
for g in ["cube", "rebound", "dunes"]:
    src = f"examples/{g}.jo" if g == "cube" else f"examples/{g}/{g}.jo"
    exe = f"{BUILD}/{g}_sw"
    run([SLOPPY, "build", src, "-o", exe, "--release"])
    soft_png = f"{BUILD}/{g}_soft.png"
    env = {k: v for k, v in ENV.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY")}
    env.update(SLOPPY_SOFTWARE="1", SLOPPY_FRAMES="60", SLOPPY_SCREENSHOT=soft_png, SLOPPY_FRAME_STATS="1")
    r = run([exe], env=env, timeout=300)
    m = re.search(r"frame cpu: ([\d.]+) ms", r.stderr)
    diff = "n/a (no display for the GPU frame)"
    if has_display:
        gpu_png = f"{BUILD}/{g}_gpu.png"
        run([exe], env=dict(ENV, SLOPPY_FRAMES="60", SLOPPY_SCREENSHOT=gpu_png, SLOPPY_SCALE="1"), timeout=120)
        if os.path.exists(soft_png) and os.path.exists(gpu_png):
            d = png_diff(soft_png, gpu_png)
            diff = f"{d:.2f}" if d is not None else "size mismatch"
    say(f"| {g} | {m.group(1) + ' ms' if m else 'FAILED'} | {diff} |")
say()

open("docs/REPORT.md", "w").write("\n".join(out) + "\n")
print("\nwrote docs/REPORT.md")
