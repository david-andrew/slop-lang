#!/usr/bin/env python3
"""Mutation fuzzing of the compiler: take real programs (tests, examples), break them in small
random ways (delete, repeat, swap or replace tokens and lines, cut them off), and build each
one. Whatever the input, the compiler must answer with a program (exit 0) or an error at a
place (exit 1): a panic, an internal compiler error, another exit status or a hang is a bug.
Each one found is shrunk to a small program and saved to build/fuzz/crash_<seed>.jo.

usage: tools/fuzz_errors.py [count] [--seed N] [--jobs N] [--target linux|wasm|windows]
"""
import glob, os, random, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLOPPY = os.environ.get("SLOPPY_FUZZ_COMPILER") or os.path.join(ROOT, "bin", "sloppy")
ENV = dict(os.environ, SLOPPY_LIB=os.path.join(ROOT, "lib"))
OUT = os.path.join(ROOT, "build", "fuzz")
TOKEN = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|\w+|[^\w\s]')

corpus = []
for pat in ["tests/t/*.jo", "tests/errors/*.jo", "tests/unit/*.jo", "examples/*.jo", "examples/*/*.jo"]:
    for p in sorted(glob.glob(os.path.join(ROOT, pat))):
        corpus.append(open(p, encoding="utf-8").read())
vocab = sorted({t for src in corpus for t in TOKEN.findall(src) if len(t) < 20})


def mutate(src, r):
    """a few random breakages of src"""
    for _ in range(r.randint(1, 3)):
        lines = src.split("\n")
        how = r.randrange(8)
        if how == 0 and len(lines) > 1:                     # delete a line
            del lines[r.randrange(len(lines))]
        elif how == 1:                                      # repeat a line
            i = r.randrange(len(lines))
            lines.insert(i, lines[i])
        elif how == 2:                                      # change a line's indentation
            i = r.randrange(len(lines))
            lines[i] = " " * r.choice([0, 2, 4, 8, 12]) + lines[i].lstrip()
        elif how == 3:                                      # cut the program off
            src = src[:r.randrange(len(src) + 1)]
            continue
        else:                                               # a token: delete, repeat, replace, swap
            spans = [m.span() for m in TOKEN.finditer(src)]
            if not spans: continue
            k = r.randrange(len(spans))
            a, b = spans[k]
            if how == 4: src = src[:a] + src[b:]
            elif how == 5: src = src[:a] + src[a:b] + " " + src[a:]
            elif how == 6: src = src[:a] + r.choice(vocab) + src[b:]
            elif k + 1 < len(spans):
                c, d = spans[k + 1]
                src = src[:a] + src[c:d] + src[b:c] + src[a:b] + src[d:]
            continue
        src = "\n".join(lines)
    return src


def verdict(src, target, timeout=20):
    """None if the compiler behaved (a program or an error), else what went wrong"""
    with tempfile.TemporaryDirectory(prefix="sloppy-fuzz-") as d:
        path = os.path.join(d, "m.jo")
        open(path, "w", encoding="utf-8").write(src)
        cmd = [SLOPPY, "build", path, "-o", os.path.join(d, "m")] + (["--target", target] if target != "linux" else [])
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, timeout=timeout, cwd=d)
        except subprocess.TimeoutExpired:
            return "hang"
    err = r.stderr
    if "internal compiler error" in err: return "internal compiler error: " + err.split("internal compiler error:", 1)[1].split("\n")[0].strip()
    if "panic:" in err:
        m = re.search(r"panic: (.*)\n(?:\s+in (\S+))?", err)
        return f"panic: {m.group(1)[:80]} in {m.group(2)}" if m else "panic"
    if r.returncode not in (0, 1): return f"exit {r.returncode}"
    if r.returncode == 1 and ": error:" not in err and "error" not in err: return "exit 1 without an error message"
    return None


def kind(v):
    """what identifies a bug (messages vary with the program; where it crashed does not)"""
    return re.sub(r"\d+", "N", v.split(":")[0] if not v.startswith("panic") else v.split(" in ")[-1] + v[:20])


def shrink(src, want, target):
    """delete lines, then tokens, while the compiler still fails the same way"""
    def same(s): v = verdict(s, target); return v is not None and kind(v) == want
    lines = src.split("\n")
    chunk = max(1, len(lines) // 2)
    while chunk >= 1:
        i = 0
        while i < len(lines):
            t = lines[:i] + lines[i + chunk:]
            if t and same("\n".join(t)): lines = t
            else: i += chunk
        chunk //= 2
    src = "\n".join(lines)
    i = 0
    while True:
        spans = [m.span() for m in TOKEN.finditer(src)]
        if i >= len(spans): break
        a, b = spans[i]
        t = src[:a] + src[b:]
        if same(t): src = t
        else: i += 1
    return src


def main():
    args = sys.argv[1:]
    count, seed, jobs, target = 500, random.randrange(1 << 30), os.cpu_count() or 4, "linux"
    i = 0
    while i < len(args):
        if args[i] == "--seed": seed = int(args[i + 1]); i += 2
        elif args[i] == "--jobs": jobs = int(args[i + 1]); i += 2
        elif args[i] == "--target": target = args[i + 1]; i += 2
        else: count = int(args[i]); i += 1
    os.makedirs(OUT, exist_ok=True)

    def one(s):
        r = random.Random(s)
        src = mutate(r.choice(corpus), r)
        return s, src, verdict(src, target)

    found = {}
    with ThreadPoolExecutor(jobs) as ex:
        for s, src, v in ex.map(one, range(seed, seed + count)):
            if v is None: continue
            k = kind(v)
            if k in found: continue
            found[k] = (s, src, v)
            print(f"seed {s}: {v}", flush=True)
    for k, (s, src, v) in found.items():
        small = shrink(src, k, target)
        path = os.path.join(OUT, f"crash_{s}.jo")
        open(path, "w", encoding="utf-8").write(small)
        print(f"  {path} ({len(small.splitlines())} lines): {v}")
    print(f"{count} programs (seeds {seed}..{seed + count - 1}), {len(found)} kinds of compiler failure")
    sys.exit(1 if found else 0)


main()
