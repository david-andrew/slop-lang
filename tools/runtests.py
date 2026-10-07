#!/usr/bin/env python3
"""Run Jot test programs and compare output with .out files.
usage: runtests.py [--compiler jot0|jot] [--target native|wasm] [pattern]"""
import os, subprocess, sys, glob, time

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = sys.argv[1:]
compiler = "jot0"
target = "native"
pattern = ""
i = 0
while i < len(args):
    if args[i] == "--compiler": compiler = args[i + 1]; i += 2
    elif args[i] == "--target": target = args[i + 1]; i += 2
    else: pattern = args[i]; i += 1

tests = sorted(glob.glob(os.path.join(root, "tests", "t", "*.jot")))
tests = [t for t in tests if pattern in os.path.basename(t)]
passed = failed = 0
os.makedirs("/tmp/jot-tests", exist_ok=True)
for t in tests:
    name = os.path.basename(t)[:-4]
    exp_path = t[:-4] + ".out"
    expected = open(exp_path).read() if os.path.exists(exp_path) else None
    exe = f"/tmp/jot-tests/{name}"
    if compiler == "jot0":
        cmd = [os.path.join(root, "stage0", "jot0"), t, "-o", exe]
    else:
        cmd = [os.path.join(root, "bin", "jot"), "build", t, "-o", exe] + (["--target", "wasm"] if target == "wasm" else [])
        env = dict(os.environ, JOT_LIB=os.path.join(root, "lib"))
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, env=dict(os.environ, JOT_LIB=os.path.join(root, "lib")))
    if r.returncode != 0:
        print(f"FAIL {name}: compile error\n{r.stderr}")
        failed += 1
        continue
    if target == "wasm":
        run = ["node", os.path.join(root, "tools", "runwasm.js"), exe + ".html"]
    else:
        run = [exe]
    r = subprocess.run(run, capture_output=True, text=True, timeout=60)
    out = r.stdout
    if r.returncode != 0 and not name.startswith("panic"):
        out += f"[exit {r.returncode}] {r.stderr}"
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
print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
