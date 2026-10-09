#!/usr/bin/env python3
"""Run Sloppy test programs and compare output with .out files.
usage: runtests.py [--compiler sloppy0|sloppy|path] [--release] [--target native|wasm|windows] [pattern]
(on Windows itself: the compiler is bin/sloppy.exe, and programs are native Windows ones)"""
import os, re, subprocess, sys, glob, tempfile, time

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[1:]
compiler = "sloppy0"
release = False
target = "native"
pattern = ""
i = 0
while i < len(args):
    if args[i] == "--compiler": compiler = args[i + 1]; i += 2
    elif args[i] == "--release": release = True; i += 1
    elif args[i] == "--target": target = args[i + 1]; i += 2
    else: pattern = args[i]; i += 1

on_windows = os.name == "nt"
tmp = os.path.join(tempfile.gettempdir(), "sloppy-tests")
sloppy_bin = os.path.join(root, "bin", "sloppy.exe" if on_windows else "sloppy")
tests = sorted(glob.glob(os.path.join(root, "tests", "t", "*.jo")))
tests = [t for t in tests if pattern in os.path.basename(t)]
passed = failed = 0
os.makedirs(tmp, exist_ok=True)
for t in tests:
    name = os.path.basename(t)[:-3]
    exp_path = t[:-3] + ".out"
    expected = open(exp_path, encoding="utf-8").read() if os.path.exists(exp_path) else None
    exe = os.path.join(tmp, name)
    if target == "windows":
        # (run under Wine: SLOPPY_WINE_DIR is shared with the container SLOPPY_WINE runs in)
        exe = os.path.join(os.environ.get("SLOPPY_WINE_DIR", "/tmp/winshare"), "tests", name)
        os.makedirs(os.path.dirname(exe), exist_ok=True)
    if compiler == "sloppy0" and "# requires: sloppy" in open(t, encoding="utf-8").read(2000):
        continue
    if compiler == "sloppy0":
        cmd = [os.path.join(root, "stage0", "sloppy0"), t, "-o", exe]
    else:
        sloppy = sloppy_bin if compiler == "sloppy" else os.path.abspath(compiler)
        cmd = [sloppy, "build", t, "-o", exe] + (["--target", target] if target != "native" else []) + (["--release"] if release else [])
        env = dict(os.environ, SLOPPY_LIB=os.path.join(root, "lib"))
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=dict(os.environ, SLOPPY_LIB=os.path.join(root, "lib")), timeout=60)
    except subprocess.TimeoutExpired:
        print(f"FAIL {name}: the compiler took over 60 s")
        failed += 1
        continue
    if r.returncode != 0:
        print(f"FAIL {name}: compile error\n{r.stderr}")
        failed += 1
        continue
    if target == "wasm":
        run = ["node", os.path.join(root, "tools", "runwasm.js"), exe + ".html"]
    elif target == "windows":
        run = os.environ.get("SLOPPY_WINE", "podman exec sloppy-win /w/run.sh").split() + ["tests/" + name + ".exe"]
    elif on_windows:
        run = [exe + ".exe"]
    else:
        run = [exe]
    try:
        r = subprocess.run(run, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
    except subprocess.TimeoutExpired:
        print(f"FAIL {name}: timed out")
        failed += 1
        continue
    out = r.stdout
    if r.returncode != 0 and not name.startswith("panic"):
        # (the backtrace after a panic differs with --release and is not there on the web;
        # tests/backtrace checks it)
        err = "".join(l for l in r.stderr.splitlines(True) if not l.startswith(("    in ", "    called from ", "    ... and ")))
        out += f"[exit {r.returncode}] {err}"
    if expected is None:
        print(f"NEW  {name}:\n{out}")
        failed += 1
    elif out != expected:
        print(f"FAIL {name}")
        el, ol = expected.splitlines(), out.splitlines()
        for k in range(max(len(el), len(ol))):
            e = el[k] if k < len(el) else "<missing>"
            o = ol[k] if k < len(ol) else "<missing>"
            if e != o:
                print(f"   line {k+1}: expected {e!r}\n   line {k+1}:      got {o!r}")
                break
        failed += 1
    else:
        passed += 1
# backtraces after a panic: tests/backtrace/*.jo, all of stderr against .out (native debug builds)
if compiler != "sloppy0" and target in ("native", "windows") and not release:
    sloppy = sloppy_bin if compiler == "sloppy" else os.path.abspath(compiler)
    for t in sorted(glob.glob(os.path.join(root, "tests", "backtrace", "*.jo"))):
        name = "backtrace/" + os.path.basename(t)[:-3]
        if pattern not in name: continue
        exe = os.path.join(tmp, "bt_" + os.path.basename(t)[:-3])
        run = [exe + ".exe"] if on_windows else [exe]
        if target == "windows":
            exe = os.path.join(os.environ.get("SLOPPY_WINE_DIR", "/tmp/winshare"), "tests", "bt_" + os.path.basename(t)[:-3])
            run = os.environ.get("SLOPPY_WINE", "podman exec sloppy-win /w/run.sh").split() + ["tests/" + os.path.basename(exe) + ".exe"]
        subprocess.run([sloppy, "build", t, "-o", exe] + (["--target", target] if target != "native" else []), capture_output=True, env=dict(os.environ, SLOPPY_LIB=os.path.join(root, "lib")))
        r = subprocess.run(run, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
        # (how deep a recursion gets before the stack runs out depends on the machine)
        out = re.sub(r"\(\d+ times\)", "(N times)", r.stdout + r.stderr)
        exp_path = t[:-3] + ".out"
        if not os.path.exists(exp_path):
            print(f"NEW  {name}:\n{out}")
            failed += 1
        elif out != open(exp_path, encoding="utf-8").read():
            print(f"FAIL {name}:\n{out}")
            failed += 1
        else: passed += 1
# `test` blocks in tests/unit, run with `sloppy test` (native, self-hosted compiler only)
if compiler != "sloppy0" and target == "native":
    sloppy = sloppy_bin if compiler == "sloppy" else os.path.abspath(compiler)
    for t in sorted(glob.glob(os.path.join(root, "tests", "unit", "*.jo"))):
        name = "unit/" + os.path.basename(t)[:-3]
        if pattern not in name: continue
        r = subprocess.run([sloppy, "test", t], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=dict(os.environ, SLOPPY_LIB=os.path.join(root, "lib")), timeout=60)
        if r.returncode == 0 and "tests passed" in r.stdout: passed += 1
        else:
            print(f"FAIL {name}\n{r.stdout}{r.stderr}")
            failed += 1
    # programs the compiler must reject: tests/errors/*.jo start with `# error: <part of the message>`
    for t in sorted(glob.glob(os.path.join(root, "tests", "errors", "*.jo"))):
        name = "errors/" + os.path.basename(t)[:-3]
        if pattern not in name: continue
        want = open(t, encoding="utf-8").readline().split("# error:", 1)[-1].strip()
        r = subprocess.run([sloppy, "build", t, "-o", os.path.join(tmp, "error_case")], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=dict(os.environ, SLOPPY_LIB=os.path.join(root, "lib")), timeout=60)
        # (a diagnostic: exit status 1 with an error at a place, never the compiler crashing)
        crashed = r.returncode != 1 or "panic:" in r.stderr or "internal compiler error" in r.stderr
        if not crashed and want in r.stderr: passed += 1
        else:
            print(f"FAIL {name}: expected an error containing {want!r}\n{r.stderr}")
            failed += 1
    # the interactive prompt: tests/repl/*.in typed at `sloppy` (stdout and stderr) against .out
    # (not on Windows yet)
    for t in [] if on_windows else sorted(glob.glob(os.path.join(root, "tests", "repl", "*.in"))):
        name = "repl/" + os.path.basename(t)[:-3]
        if pattern not in name: continue
        exp_path = t[:-3] + ".out"
        r = subprocess.run([sloppy], stdin=open(t), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                           env=dict(os.environ, SLOPPY_LIB=os.path.join(root, "lib")), timeout=60, cwd=os.path.dirname(t))
        out = r.stdout + (f"[exit {r.returncode}]\n" if r.returncode != 0 else "")
        if not os.path.exists(exp_path):
            print(f"NEW  {name}:\n{out}")
            failed += 1
        elif out != open(exp_path, encoding="utf-8").read():
            print(f"FAIL {name}:\n{out}")
            failed += 1
        else: passed += 1
print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
