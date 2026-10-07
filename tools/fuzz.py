#!/usr/bin/env python3
"""Differential fuzzing: generate random (well-defined) Jot programs and check that debug,
release and web builds print the same thing.

usage: tools/fuzz.py [count] [--seed N] [--no-wasm] [--keep]
Failing programs are saved to build/fuzz/fail_<seed>.jot.
"""
import os, random, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOT = os.path.join(ROOT, "bin", "jot")
ENV = dict(os.environ, JOT_LIB=os.path.join(ROOT, "lib"))
OUT = os.path.join(ROOT, "build", "fuzz")
os.makedirs(OUT, exist_ok=True)


class Gen:
    def __init__(self, rnd):
        self.r = rnd
        self.lines = []
        self.ints = []      # names of int variables in scope
        self.ro = set()     # read-only ones (parameters, loop variables)
        self.floats = []
        self.arrays = []    # [int] arrays (never empty)
        self.depth = 0
        self.fns = []       # (name, nparams) of helper functions: int -> int
        self.n = 0

    def fresh(self, p):
        self.n += 1
        return f"{p}{self.n}"

    def emit(self, s):
        self.lines.append("    " * self.depth + s)

    # ---------------- expressions ----------------
    def iexpr(self, d=0):
        r = self.r
        if d > 3 or r.random() < 0.25:
            c = r.random()
            if c < 0.5 and self.ints: return r.choice(self.ints)
            if c < 0.65 and self.arrays:
                a = r.choice(self.arrays)
                return f"{a}[abs({self.iexpr(d + 2)}) % {a}.len()]"
            if c < 0.75 and self.arrays: return f"{r.choice(self.arrays)}.len()"
            return str(r.choice([0, 1, 2, 3, 7, -1, -5, 100, 255, 1000, -32768, 65537, 2147483647, -2147483648]))
        op = r.choice(["+", "-", "*", "/", "%", "&", "|", "^", "<<", ">>", "call", "neg", "if", "min", "cmpsel", "float"])
        a = self.iexpr(d + 1)
        b = self.iexpr(d + 1)
        if op in "+-*&|^": return f"({a} {op} {b})"
        if op in ("/", "%"): return f"({a} {op} (abs({b}) % 9 + 1))"
        if op in ("<<", ">>"): return f"({a} {op} (abs({b}) % 13))"
        if op == "neg": return f"(0 - {a})"
        if op == "call" and self.fns:
            name, np_ = r.choice(self.fns)
            args = ", ".join(self.iexpr(d + 2) for _ in range(np_))
            return f"{name}({args})"
        if op == "if": return f"(if {self.cond(d + 1)}: {a} else: {b})"
        if op == "min": return f"min({a}, {b})"
        if op == "cmpsel": return f"int({a} < {b}) + int({a} == {b}) * 2"
        if op == "float" and self.floats: return f"int({r.choice(self.floats)} * 3.0) % 100000"
        return a

    def fexpr(self, d=0):
        r = self.r
        if d > 3 or r.random() < 0.3:
            if self.floats and r.random() < 0.6: return r.choice(self.floats)
            return r.choice(["0.5", "1.25", "-3.75", "100.0", "0.1", "2.0"])
        op = r.choice(["+", "-", "*", "/", "int", "sqrt", "abs", "floor"])
        a = self.fexpr(d + 1)
        b = self.fexpr(d + 1)
        if op in "+-*": return f"({a} {op} {b})"
        if op == "/": return f"({a} / (abs({b}) + 1.0))"
        if op == "int": return f"float({self.iexpr(d + 2)} % 1000)"
        if op == "sqrt": return f"sqrt(abs({a}))"
        if op == "abs": return f"abs({a})"
        return f"floor({a})"

    def cond(self, d=0):
        r = self.r
        c = r.random()
        if c < 0.6: return f"{self.iexpr(d + 1)} {r.choice(['<', '<=', '>', '>=', '==', '!='])} {self.iexpr(d + 1)}"
        if c < 0.75 and self.floats: return f"{self.fexpr(d + 1)} < {self.fexpr(d + 1)}"
        if c < 0.9: return f"({self.cond(d + 2)}) {r.choice(['and', 'or'])} ({self.cond(d + 2)})"
        return f"not ({self.cond(d + 2)})"

    # ---------------- statements ----------------
    def block(self, n):
        saved = (list(self.ints), list(self.floats), list(self.arrays))
        self.depth += 1
        for _ in range(n): self.stmt()
        if not self.lines[-1].strip() or self.lines[-1].endswith(":"): self.emit("pass")
        self.depth -= 1
        self.ints, self.floats, self.arrays = saved

    def stmt(self):
        r = self.r
        c = r.random()
        if c < 0.2 or not self.ints:
            v = self.fresh("i")
            self.emit(f"{v} := {self.iexpr()}")
            self.ints.append(v)
        elif c < 0.3:
            v = self.fresh("f")
            self.emit(f"{v} := {self.fexpr()}")
            self.floats.append(v)
        elif c < 0.38:
            v = self.fresh("a")
            n = r.randint(1, 6)
            self.emit(f"{v} := [{', '.join(self.iexpr(2) for _ in range(n))}]")
            self.arrays.append(v)
        elif c < 0.55 and [x for x in self.ints if x not in self.ro]:
            v = r.choice([x for x in self.ints if x not in self.ro])
            self.emit(f"{v} {r.choice(['=', '+=', '-=', '^='])} {self.iexpr()}")
        elif c < 0.62 and self.floats:
            v = r.choice(self.floats)
            self.emit(f"{v} = {self.fexpr()}")
        elif c < 0.7 and self.arrays:
            a = r.choice(self.arrays)
            if r.random() < 0.5: self.emit(f"{a}[abs({self.iexpr(2)}) % {a}.len()] = {self.iexpr()}")
            else: self.emit(f"if {a}.len() < 64: {a}.push({self.iexpr()})")
        elif c < 0.78 and self.depth < 4:
            self.emit(f"if {self.cond()}:")
            self.block(r.randint(1, 3))
            if r.random() < 0.5:
                self.emit("else:")
                self.block(r.randint(1, 3))
        elif c < 0.85 and self.depth < 3:
            k = self.fresh("k")
            self.emit(f"for {k} in 0..{r.randint(1, 12)}:")
            self.ints.append(k)
            self.ro.add(k)
            self.block(r.randint(1, 4))
            self.ints.remove(k)
        elif c < 0.9 and self.depth < 3 and self.arrays:
            x = self.fresh("x")
            self.emit(f"for {x} in {r.choice(self.arrays)}:")
            self.ints.append(x)
            self.ro.add(x)
            self.block(r.randint(1, 3))
            self.ints.remove(x)
        elif c < 0.94 and self.depth < 3:
            w = self.fresh("w")
            self.emit(f"{w} := 0")
            self.emit(f"while {w} < {r.randint(1, 9)} and ({self.cond()}):")
            self.depth += 1
            self.emit(f"{w} += 1")
            self.depth -= 1
            self.block(r.randint(1, 3))
        else:
            self.emit(f"print({', '.join(r.choice(self.ints) for _ in range(r.randint(1, 3)))})")

    def program(self):
        r = self.r
        out = []
        # helper functions first
        for fi in range(r.randint(1, 4)):
            name = f"h{fi}"
            np_ = r.randint(1, 3)
            params = [f"p{j}" for j in range(np_)]
            self.lines = []
            self.ints, self.floats, self.arrays = list(params), [], []
            self.ro = set(params)
            self.depth = 1
            for _ in range(r.randint(1, 5)): self.stmt()
            body = self.lines
            ret = self.iexpr()
            out.append(f"fn {name}({', '.join(p + ': int' for p in params)}) -> int:")
            out.extend(body)
            out.append(f"    {ret}")
            out.append("")
            self.fns.append((name, np_))
        self.lines = []
        self.ints, self.floats, self.arrays = [], [], []
        self.depth = 1
        for _ in range(r.randint(10, 40)): self.stmt()
        self.emit(f"print({', '.join(self.ints[-6:]) or '0'})")
        if self.floats: self.emit(f"print({', '.join(self.floats[-4:])})")
        if self.arrays: self.emit(f"print({self.arrays[-1]})")
        out.append("fn main():")
        out.extend(self.lines)
        return "\n".join(out) + "\n"


def run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=ENV)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"


def check(seed, wasm=True, keep=False):
    src = Gen(random.Random(seed)).program()
    path = os.path.join(OUT, f"p{seed}.jot")
    open(path, "w").write(src)
    outs = {}
    modes = [("debug", []), ("release", ["--release"])]
    if wasm: modes += [("wasm", ["--target", "wasm"]), ("wasm-release", ["--target", "wasm", "--release"])]
    for name, flags in modes:
        exe = os.path.join(OUT, f"p{seed}_{name}")
        code, _, err = run([JOT, "build", path, "-o", exe] + flags)
        if code != 0:
            outs[name] = f"COMPILE ERROR {err[:300]}"
            continue
        if name.startswith("wasm"):
            code, o, e = run(["node", os.path.join(ROOT, "tools", "runwasm.js"), exe + ".html"])
        else:
            code, o, e = run([exe])
        outs[name] = o + (f"[exit {code}] {e[:200]}" if code != 0 else "")
    vals = list(outs.values())
    ok = all(v == vals[0] for v in vals) and not vals[0].startswith("COMPILE ERROR")
    if not ok:
        os.rename(path, os.path.join(OUT, f"fail_{seed}.jot"))
        print(f"MISMATCH seed {seed}:")
        for k, v in outs.items(): print(f"  {k}: {v[:300]!r}")
    elif not keep:
        os.remove(path)
    for f in os.listdir(OUT):
        if f.startswith(f"p{seed}_"): os.remove(os.path.join(OUT, f))
    return ok


if __name__ == "__main__":
    args = sys.argv[1:]
    count = int(args[0]) if args and args[0].isdigit() else 50
    seed = int(args[args.index("--seed") + 1]) if "--seed" in args else random.randrange(1 << 30)
    wasm = "--no-wasm" not in args
    bad = 0
    for i in range(count):
        if not check(seed + i, wasm, "--keep" in args): bad += 1
    print(f"{count} programs, {bad} mismatches (seeds {seed}..{seed + count - 1})")
    sys.exit(1 if bad else 0)
