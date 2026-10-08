#!/usr/bin/env python3
"""Differential fuzzing: generate random (well-defined) Jot programs and check that debug,
release and web builds print the same thing.

usage: tools/fuzz.py [count] [--seed N] [--no-wasm] [--keep]
Failing programs are saved to build/fuzz/fail_<seed>.jot.
"""
import os, random, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOT = os.path.join(ROOT, "bin", "jot")
JOT0 = os.path.join(ROOT, "stage0", "jot0")      # the C bootstrap compiler: an independent implementation
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
        self.strs = []      # str variables
        self.structs = []   # P variables
        self.parrs = []     # [P] arrays (never empty)
        self.closures = []  # fn(int) -> int values
        self.maps = []      # {int: int} maps
        self.vecs = []      # (name, lanes) of vec2/vec3/vec4 variables
        self.varrs = []     # (name, lanes) of arrays of 3 vectors
        self.depth = 0
        self.use_vec = rnd.random() < 0.5     # half the programs stay in the bootstrap compiler's subset
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
            if c < 0.8 and self.strs: return f"len({r.choice(self.strs)})"
            if c < 0.84 and self.structs: return f"{r.choice(self.structs)}.a"
            if c < 0.87 and self.closures: return f"{r.choice(self.closures)}({self.iexpr(d + 2)})"
            if c < 0.9 and self.maps: return f"({r.choice(self.maps)}.get({self.iexpr(d + 2)}) ?? -1)"
            if c < 0.92 and self.parrs:
                a = r.choice(self.parrs)
                return f"{a}[abs({self.iexpr(d + 2)}) % {a}.len()].a"
            return str(r.choice([0, 1, 2, 3, 7, -1, -5, 100, 255, 1000, -32768, 65537, 2147483647, -2147483648]))
        op = r.choice(["+", "-", "*", "/", "%", "&", "|", "^", "<<", ">>", "call", "neg", "if", "min", "cmpsel", "float", "match"])
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
        if op == "float" and self.floats: return f"fi({r.choice(self.floats)} * 3.0) % 100000"
        if op == "match" and d <= 1 and self.ints:
            arms = []
            vals = r.sample(range(-3, 12), r.randint(1, 5))
            for v in vals: arms.append(f"{v}: {self.iexpr(4)}")
            if r.random() < 0.5: arms.append(f"20..30: {self.iexpr(4)}")
            arms.append(f"_: {self.iexpr(4)}")
            return "(match " + r.choice(self.ints) + ":\n" + "".join("    " * (self.depth + 2) + arm + "\n" for arm in arms) + "    " * (self.depth + 1) + ")"
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

    def vlit(self, n):
        r = self.r
        return f"vec{n}({', '.join(r.choice(['0.5', '1.0', '-2.0', '3.25', '0.125', '-0.75', '8.0']) for _ in range(n))})"

    def vexpr(self, n, d=0):
        r = self.r
        if d > 2 or r.random() < 0.3:
            c = r.random()
            same = [v for v, k in self.vecs if k == n]
            arrs = [v for v, k in self.varrs if k == n]
            if c < 0.5 and same: return r.choice(same)
            if c < 0.7 and arrs: return f"{r.choice(arrs)}[abs({self.iexpr(3)}) % 3]"
            return self.vlit(n)
        op = r.choice(["+", "-", "*", "s*", "*s", "/s", "s-", "/v"])
        a = self.vexpr(n, d + 1)
        sc = f"f32({self.fexpr(3)})"
        if op in "+-*": return f"({a} {op} {self.vexpr(n, d + 1)})"
        if op == "s*": return f"({sc} * {a})"
        if op == "*s": return f"({a} * {sc})"
        if op == "s-": return f"({sc} - {a})"
        if op == "/v": return f"({a} / {self.vlit(n)})"
        return f"({a} / (abs({sc}) + 1.0))"

    def vstmt(self):
        r = self.r
        n = r.randint(2, 4)
        c = r.random()
        same = [v for v, k in self.vecs if k == n]
        arrs = [v for v, k in self.varrs if k == n]
        if c < 0.3 or not same:
            v = self.fresh("v")
            self.emit(f"{v} := {self.vexpr(n)}")
            self.vecs.append((v, n))
        elif c < 0.45:
            v = self.fresh("va")
            self.emit(f"{v} := [{self.vexpr(n, 2)}, {self.vexpr(n, 2)}, {self.vexpr(n, 2)}]")
            self.varrs.append((v, n))
        elif c < 0.65:
            v = r.choice(same)
            self.emit(f"{v} {r.choice(['=', '+=', '-=', '*='])} {self.vexpr(n)}")
        elif c < 0.8 and arrs:
            a = r.choice(arrs)
            i = f"abs({self.iexpr(3)}) % 3"
            self.emit(f"{a}[{i}] = {a}[{i}] * {self.vexpr(n, 2)} + {self.vexpr(n, 2)}")
            self.emit(f"print({a})")
        else:
            self.emit(f"print({r.choice(same)})")

    def cond(self, d=0):
        r = self.r
        c = r.random()
        if c < 0.6: return f"{self.iexpr(d + 1)} {r.choice(['<', '<=', '>', '>=', '==', '!='])} {self.iexpr(d + 1)}"
        if c < 0.75 and self.floats: return f"{self.fexpr(d + 1)} < {self.fexpr(d + 1)}"
        if c < 0.8 and len(self.strs) > 1: return f"{r.choice(self.strs)} {r.choice(['==', '!=', '<'])} {r.choice(self.strs)}"
        if c < 0.9: return f"({self.cond(d + 2)}) {r.choice(['and', 'or'])} ({self.cond(d + 2)})"
        return f"not ({self.cond(d + 2)})"

    # ---------------- statements ----------------
    def block(self, n):
        saved = (list(self.ints), list(self.floats), list(self.arrays), list(self.strs), list(self.structs), list(self.parrs), list(self.closures), list(self.maps), list(self.vecs), list(self.varrs))
        self.depth += 1
        for _ in range(n): self.stmt()
        if not self.lines[-1].strip() or self.lines[-1].endswith(":"): self.emit("pass")
        self.depth -= 1
        self.ints, self.floats, self.arrays, self.strs, self.structs, self.parrs, self.closures, self.maps, self.vecs, self.varrs = saved

    def stmt(self):
        r = self.r
        if self.use_vec and r.random() < 0.1:
            self.vstmt()
            return
        if r.random() < 0.04 and self.arrays and self.depth < 3:
            a = r.choice(self.arrays)
            v = self.fresh("b")
            op = r.choice(["or", "and"])
            self.emit(f"{v} := mh({self.iexpr(2)}, {a}, macc) {op} mh({self.iexpr(2)}, {r.choice(self.arrays)}, macc)")
            self.emit(f"print({v}, {a}, macc.len())")
            return
        if r.random() < 0.05 and self.arrays and self.depth < 3:
            # index loops over a whole array (their bounds checks may be removed)
            arr = r.choice(self.arrays)
            k = self.fresh("j")
            acc = self.fresh("sum")
            self.emit(f"{acc} := 0")
            if r.random() < 0.5:
                self.emit(f"for {k} in 0..{arr}.len(): {acc} += {arr}[{k}] * {r.randint(1, 5)}")
            else:
                n = self.fresh("n")
                self.emit(f"{n} := {arr}.len()")
                self.emit(f"for {k} in 0..{n}: {acc} ^= {arr}[{k}]")
            self.emit(f"print({acc})")
            return
        c = r.random()
        if c < 0.2 or not self.ints:
            v = self.fresh("i")
            self.emit(f"{v} := {self.iexpr()}")
            self.ints.append(v)
        elif c < 0.3:
            v = self.fresh("fl")
            self.emit(f"{v} := {self.fexpr()}")
            self.floats.append(v)
        elif c < 0.38:
            v = self.fresh("a")
            n = r.randint(1, 6)
            self.emit(f"{v} := [{', '.join(self.iexpr(2) for _ in range(n))}]")
            self.arrays.append(v)
        elif c < 0.42 and r.random() < 0.5:
            self.new_value()
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

    def new_value(self):
        r = self.r
        k = r.randint(0, 5)
        if k == 0:
            v = self.fresh("s")
            self.emit(f'{v} := "{r.choice(["ab", "", "xyz", "hello"])}" + "{{{self.iexpr(2)}}}"')
            self.strs.append(v)
        elif k == 1 and self.strs:
            v = r.choice(self.strs)
            self.emit(f'if len({v}) < 40: {v} = {v} + "{r.choice("abc")}"')
            self.emit(f"print({v}, len({v}), {v}.find(\"a\"), {v}[0..min(2, len({v}))])")
        elif k == 2:
            v = self.fresh("q")
            self.emit(f"{v} := P({self.iexpr(2)}, {self.fexpr(2)})")
            self.structs.append(v)
            if r.random() < 0.5:
                self.emit(f"{v}.a += {self.iexpr(2)}")
                self.emit(f"print({v})")
        elif k == 3:
            v = self.fresh("pa")
            self.emit(f"{v} := [P({self.iexpr(2)}, 1.5), P({self.iexpr(2)}, -2.0)]")
            self.parrs.append(v)
            if r.random() < 0.6:
                self.emit(f"for mut it in {v}:")
                self.emit(f"    it.a = it.a * 3 + {self.iexpr(3)}")
                self.emit(f"    it.b = it.b * 0.5")
            self.emit(f"print({v})")
        elif k == 4:
            v = self.fresh("cl")
            cap = self.iexpr(2)
            self.emit(f"{v}k := {cap}")
            self.emit(f"{v} := fn(x: int) -> int: x * 3 + {v}k")
            self.closures.append(v)
        else:
            v = self.fresh("m")
            self.emit(f"{v}: {{int: int}} = {{}}")
            self.emit(f"for mk in 0..{r.randint(1, 20)}: {v}[(mk * 7) % 13] = mk + {self.iexpr(3)}")
            self.emit(f"print({v}.len())")
            self.maps.append(v)

    def program(self):
        r = self.r
        out = ["struct P:", "    a: int", "    b: float", "",
               "# takes an array and a mut array: used inside and/or, where temporaries are conditional",
               "fn mh(n: int, xs: [int], acc: mut [int]) -> bool:",
               "    if acc.len() < 50: acc.push(n + xs.len())",
               "    n % 3 == 0", "",
               "# float to int where every compiler agrees (the C bootstrap compiler does not saturate)",
               "fn fi(x: float) -> int:",
               "    if x == x and abs(x) < 1000000000000000.0: return int(x)",
               "    0", ""]
        # helper functions first
        for fi in range(r.randint(1, 4)):
            name = f"h{fi}"
            np_ = r.randint(1, 3)
            params = [f"p{j}" for j in range(np_)]
            self.lines = []
            self.ints, self.floats, self.arrays = list(params), [], []
            self.strs, self.structs, self.parrs, self.closures, self.maps = [], [], [], [], []
            self.vecs, self.varrs = [], []
            self.ro = set(params)
            self.depth = 1
            self.emit("macc: [int]")
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
        self.strs, self.structs, self.parrs, self.closures, self.maps = [], [], [], [], []
        self.vecs, self.varrs = [], []
        self.depth = 1
        self.emit("macc: [int]")
        for _ in range(r.randint(10, 40)): self.stmt()
        if self.vecs: self.emit(f"print({', '.join(v for v, _ in self.vecs[-4:])})")
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
    # the bootstrap compiler shares no code with the self-hosted one, so it catches mistakes all
    # of the self-hosted builds make alike (when the program stays within its language subset)
    if os.path.exists(JOT0) and "vec" not in src:
        exe = os.path.join(OUT, f"p{seed}_jot0")
        code, _, err = run([JOT0, path, "-o", exe])
        if code == 0:
            code, o, e = run([exe])
            outs["jot0"] = o + (f"[exit {code}] {e[:200]}" if code != 0 else "")
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
