#!/usr/bin/env python3
"""Test the language server (sloppy lsp) the way an editor uses it.
usage: tools/lsptest.py [path/to/sloppy]        (default: bin/sloppy)"""
import json, os, subprocess, sys, tempfile

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sloppy = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(root, "bin", "sloppy")


class Client:
    def __init__(self):
        self.p = subprocess.Popen([sloppy, "lsp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  env=dict(os.environ, SLOPPY_LIB=os.path.join(root, "lib")))
        self.id = 0
        self.notes = []
        self.versions = {}

    def send(self, obj):
        b = json.dumps(obj).encode()
        self.p.stdin.write(b"Content-Length: %d\r\n\r\n" % len(b) + b)
        self.p.stdin.flush()

    def recv(self):
        h = b""
        while not h.endswith(b"\r\n\r\n"):
            c = self.p.stdout.read(1)
            if not c: raise EOFError("the server exited")
            h += c
        n = int([l for l in h.decode().split("\r\n") if l.lower().startswith("content-length")][0].split(":")[1])
        return json.loads(self.p.stdout.read(n))

    def request(self, method, params):
        self.id += 1
        self.send({"jsonrpc": "2.0", "id": self.id, "method": method, "params": params})
        while True:
            m = self.recv()
            if m.get("id") == self.id and "method" not in m:
                return m.get("result", m.get("error"))
            self.notes.append(m)

    def notify(self, method, params):
        self.send({"jsonrpc": "2.0", "method": method, "params": params})

    def set_text(self, uri, text):
        v = self.versions.get(uri, 0) + 1
        self.versions[uri] = v
        if v == 1:
            self.notify("textDocument/didOpen", {"textDocument": {"uri": uri, "languageId": "sloppy", "version": 1, "text": text}})
        else:
            self.notify("textDocument/didChange", {"textDocument": {"uri": uri, "version": v}, "contentChanges": [{"text": text}]})

    def diagnostics(self, uri):
        v = self.versions[uri]
        while True:
            for i, m in enumerate(self.notes):
                p = m.get("params", {})
                if m.get("method") == "textDocument/publishDiagnostics" and p["uri"] == uri and p.get("version") == v:
                    del self.notes[i]
                    return p["diagnostics"]
            self.notes.append(self.recv())


failures = 0
count = 0


def check(name, got, want):
    global failures, count
    count += 1
    if got != want:
        failures += 1
        print(f"FAIL {name}:\n  got:  {got!r}\n  want: {want!r}")


def lc(text, off):
    pre = text[:off]
    return {"line": pre.count("\n"), "character": off - (pre.rfind("\n") + 1)}


tmp = tempfile.mkdtemp(prefix="sloppy-lsptest-")
c = Client()
caps = c.request("initialize", {"capabilities": {}})["capabilities"]
check("capabilities", sorted(k for k, v in caps.items() if v), sorted(["textDocumentSync", "hoverProvider", "definitionProvider", "referencesProvider", "documentHighlightProvider", "documentSymbolProvider", "renameProvider", "completionProvider", "signatureHelpProvider", "inlayHintProvider"]))
c.notify("initialized", {})

# ---- a program: names, types, declarations ----
prog = '''# A point in the plane
struct Point:
    x: f64      # across
    y: f64

enum Dir: left, right

# the distance between two points
dist = (a: Point, b: Point) -> f64:
    dx = a.x - b.x
    dy = a.y - b.y
    sqrt(dx * dx + dy * dy)

add = (a: int, b: int): a + b

twice = (f, x): f(f(x))

main = ():
    p = Point(1.0, 2.0)
    q = Point(x = 4.0, y = 6.0)
    d = dist(p, q)
    n = add(1, 2)
    t = twice((v: int): v * 2, 5)
    dir: Dir = .left
    xs = [1, 2, 3].map((v): v * 10)
    print(d, n, t, xs, p.dist(q), xs.len(), p.x, dir)
'''
path = os.path.join(tmp, "prog.jo")
open(path, "w").write(prog)
uri = "file://" + path
c.set_text(uri, prog)
check("no errors", c.diagnostics(uri), [])


def at(s, k=0, nth=0):
    i = -1
    for _ in range(nth + 1):
        i = prog.index(s, i + 1)
    return {"textDocument": {"uri": uri}, "position": lc(prog, i + k)}


def hover(s, k=0, nth=0):
    h = c.request("textDocument/hover", at(s, k, nth))
    return h and h["contents"]["value"]


check("hover local", hover("dx * dx"), "```sloppy\n(variable) dx: f64\n```")
check("hover field", hover("a.x", 2), "```sloppy\n(field) x: f64\n```\n---\nacross")
check("hover function", hover("dist(p"), "```sloppy\ndist = (a: Point, b: Point) -> f64\n```\n---\nthe distance between two points")
check("hover inferred result", hover("add(1"), "```sloppy\nadd = (a: int, b: int) -> int\n```")
check("hover generic", hover("twice("), "```sloppy\ntwice = (f, x)\n# here: twice(f: (int) -> int, x: int) -> int\n```")
check("hover struct", hover("Point(1"), "```sloppy\nstruct Point:\n    x: f64\n    y: f64\n```\n---\nA point in the plane")
check("hover variant", hover(".left", 1), "```sloppy\n(variant) Dir.left\n```")
check("hover method call", hover("p.dist", 2), "```sloppy\ndist = (a: Point, b: Point) -> f64\n```\n---\nthe distance between two points")
check("hover named argument", hover("x = 4.0"), "```sloppy\n(field) x: f64\n```\n---\nacross")
check("hover builtin", hover("len()"), "```sloppy\n(builtin) len\n```")
check("hover lambda parameter", hover("v * 2"), "```sloppy\n(parameter) v: int\n```")
check("hover keyword", hover("loop" if "loop" in prog else "main = ", 7), None)


def where(r):
    if r is None: return None
    if isinstance(r, list): return [where(x) for x in r]
    return (os.path.basename(r["uri"]), r["range"]["start"]["line"], r["range"]["start"]["character"])


check("definition", where(c.request("textDocument/definition", at("dist(p"))), ("prog.jo", 8, 0))
check("definition of a field", where(c.request("textDocument/definition", at("a.x", 2))), ("prog.jo", 2, 4))
check("definition of a local", where(c.request("textDocument/definition", at("d, n, t"))), ("prog.jo", 20, 4))
d = where(c.request("textDocument/definition", at("map(")))
check("definition in the library", d and (d[0], d[1] > 0), ("array.jo", True))
refs = c.request("textDocument/references", dict(at("dist(p"), context={"includeDeclaration": True}))
check("references", sorted(where(refs)), [("prog.jo", 8, 0), ("prog.jo", 20, 8), ("prog.jo", 25, 25)])
hl = c.request("textDocument/documentHighlight", at("dx = "))
check("highlights", len(hl), 3)
ren = c.request("textDocument/rename", dict(at("dist(p"), newName="distance"))
check("rename", sorted((e["range"]["start"]["line"], e["newText"]) for e in ren["changes"][uri]), [(8, "distance"), (20, "distance"), (25, "distance")])
hints = c.request("textDocument/inlayHint", {"textDocument": {"uri": uri}, "range": {"start": {"line": 0, "character": 0}, "end": {"line": 99, "character": 0}}})
check("inlay hints", sorted((h["position"]["line"], h["label"]) for h in hints), [(9, ": f64"), (10, ": f64"), (13, "-> int"), (15, "-> int"), (20, ": f64"), (21, ": int"), (22, ": int"), (24, ": int[]")])
sig = c.request("textDocument/signatureHelp", {"textDocument": {"uri": uri}, "position": lc(prog, prog.index("add(1, ") + 7)})
check("signature help", (sig["signatures"][0]["label"], sig["activeParameter"]), ("add = (a: int, b: int)", 1))
syms = c.request("textDocument/documentSymbol", {"textDocument": {"uri": uri}})
check("symbols", [(s["name"], s["kind"], [k["name"] for k in s.get("children", [])]) for s in syms],
      [("Point", 23, ["x", "y"]), ("Dir", 10, ["left", "right"]), ("dist", 12, []), ("add", 12, []), ("twice", 12, []), ("main", 12, [])])

# ---- completion ----
cpath = os.path.join(tmp, "comp.jo")
curi = "file://" + cpath
base = '''struct Ship:
    pos: vec2
    hp: int

enum Mode: idle, chase

ships: Ship[]
mode = Mode.idle

broken = (x: int) -> int:
    x + "no"

update = (dt: f64):
    loop s in ships:
        BODY
'''


def complete(body):
    src = base.replace("BODY", body)
    i = src.index("|")
    src = src.replace("|", "")
    c.set_text(curi, src)
    r = c.request("textDocument/completion", {"textDocument": {"uri": curi}, "position": lc(src, i)})
    return [x["label"] for x in r["items"]]


check("complete fields", complete("s.|")[:2], ["pos", "hp"])
check("complete in an unclosed call", complete("print(s.|")[:2], ["pos", "hp"])
check("complete in an unfinished if", complete("if s.|")[:2], ["pos", "hp"])
check("complete vector components", complete("s.pos.|")[:2], ["x", "y"])
check("complete variants", complete("mode = .|"), ["idle", "chase"])
check("complete enum type members", complete("mode = Mode.|"), ["idle", "chase"])
names = complete("sh|")
check("complete names", all(n in names for n in ["ships", "s", "dt", "Ship", "update", "print", "loop"]), True)
check("no internal names", any(n.startswith("__") for n in names), False)
check("complete array functions", all(n in complete("ships.|") for n in ["len", "push", "map", "filter"]), True)
check("nothing in comments", complete("x = 1  # s.|"), [])

# ---- errors ----
epath = os.path.join(tmp, "errs.jo")
euri = "file://" + epath
c.set_text(euri, '''helper = (x: int) -> int:
    y = x +
    y

other = (s: str):
    n: int = s
    print(n)

third = (k: int) -> int:
    k.nope

use_helper = ():
    print(helper(3))
''')
check("several errors", [(d["range"]["start"]["line"], d["message"]) for d in c.diagnostics(euri)],
      [(1, "expected an expression here"), (5, "type mismatch: expected int, found str"), (9, "int has no field 'nope'")])
c.set_text(euri, "x = 1.5\ny = x + \"s\"\n")
check("operator error", [d["message"] for d in c.diagnostics(euri)], ["operator + is not defined for f64 and str"])
c.set_text(euri, "x = 1\n")
check("errors cleared", c.diagnostics(euri), [])
# (errors found by lowering, reported once the editor is quiet)
c.set_text(euri, "total = 0\nxs = [1, 2, 3]\nys = parallel_map(xs, (x: int) -> int:\n    total += x\n    x)\nprint(ys)\n")
check("lowering: first the checker's", c.diagnostics(euri), [])
check("lowering: then lowering's", [(d["range"]["start"]["line"], d["message"][:39]) for d in c.diagnostics(euri)], [(3, "parallel_map runs this function on many")])

# ---- several files: use, errors in another file ----
open(os.path.join(tmp, "util.jo"), "w").write("# doubles\ndouble = (x: int) -> int: x * 2\n")
mpath = os.path.join(tmp, "main.jo")
muri = "file://" + mpath
msrc = "use 'util.jo'\nprint(double(21))\n"
c.set_text(muri, msrc)
check("multi-file: no errors", c.diagnostics(muri), [])
d = where(c.request("textDocument/definition", {"textDocument": {"uri": muri}, "position": lc(msrc, msrc.index("double"))}))
check("multi-file: definition", d, ("util.jo", 1, 0))
d = where(c.request("textDocument/definition", {"textDocument": {"uri": muri}, "position": lc(msrc, 6)}))
check("multi-file: use", d, ("util.jo", 0, 0))
refs = c.request("textDocument/references", {"textDocument": {"uri": muri}, "position": lc(msrc, msrc.index("double")), "context": {"includeDeclaration": True}})
check("multi-file: references", sorted(where(refs)), [("main.jo", 1, 6), ("util.jo", 1, 0)])
ren = c.request("textDocument/rename", {"textDocument": {"uri": muri}, "position": lc(msrc, msrc.index("double")), "newName": "twice"})
check("multi-file: rename", sorted((os.path.basename(u), len(es)) for u, es in ren["changes"].items()), [("main.jo", 1), ("util.jo", 1)])
# an error in the used file (not open): reported on that file
open(os.path.join(tmp, "util.jo"), "w").write("double = (x: int) -> int: x.nope\n")
uuri = "file://" + os.path.join(tmp, "util.jo")
c.set_text(muri, msrc + "\n")
check("multi-file: none in the main file", c.diagnostics(muri), [])
errs = [m["params"]["diagnostics"] for m in c.notes if m.get("method") == "textDocument/publishDiagnostics" and m["params"]["uri"] == uuri]
check("multi-file: error in the used file", [[(d["range"]["start"]["line"], d["message"]) for d in e] for e in errs][-1:], [[(0, "int has no field 'nope'")]])
open(os.path.join(tmp, "util.jo"), "w").write("double = (x: int) -> int: x * 2\n")
c.set_text(muri, msrc)
c.diagnostics(muri)
errs = [m["params"]["diagnostics"] for m in c.notes if m.get("method") == "textDocument/publishDiagnostics" and m["params"]["uri"] == uuri]
check("multi-file: fixed", errs[-1:], [[]])

# ---- a library file ----
lpath = os.path.join(root, "lib", "game", "stats.jo")
luri = "file://" + lpath
lsrc = open(lpath).read()
c.set_text(luri, lsrc)
check("library file: no errors", c.diagnostics(luri), [])
h = c.request("textDocument/hover", {"textDocument": {"uri": luri}, "position": lc(lsrc, lsrc.index("__stats_summary(120)"))})
check("library file: hover", h and h["contents"]["value"].split("\n")[1], "__stats_summary = (count: int) -> (str, str, str)")

c.request("shutdown", None)
c.notify("exit", None)
c.p.wait(timeout=5)
check("exit status", c.p.returncode, 0)
print(f"{count - failures} passed, {failures} failed")
sys.exit(1 if failures else 0)
