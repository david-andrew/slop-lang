#!/usr/bin/env python3
"""Tests of `sloppy watch`: run programs under it, change their files, and check what they print.

usage: tools/watchtest.py [compiler]  (games run headless, in the software renderer)"""
import os, re, subprocess, sys, tempfile, threading, time

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sloppy = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "bin", "sloppy.exe" if os.name == "nt" else "sloppy")
env = dict(os.environ, SLOPPY_LIB=os.path.join(root, "lib"), SLOPPY_SOFTWARE="1", SLOPPY_FRAMES="1000000")


class Watch:
    def __init__(self, d, main, game=True):
        e = dict(env)
        if game:
            e["SLOPPY_SCREENSHOT"] = os.path.join(d, "shot.png")
        self.p = subprocess.Popen([sloppy, "watch", main], cwd=d, env=e, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self.lines = []
        self.seen = 0
        self.lock = threading.Lock()
        threading.Thread(target=self.read, daemon=True).start()

    def read(self):
        for line in self.p.stdout:
            with self.lock:
                self.lines.append(line.rstrip("\n"))

    def expect(self, pattern, timeout=20):
        """wait for a line (after the last one matched) matching pattern; returns its match"""
        rx = re.compile(pattern)
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                while self.seen < len(self.lines):
                    line = self.lines[self.seen]
                    self.seen += 1
                    m = rx.search(line)
                    if m:
                        return m
            time.sleep(0.02)
        raise AssertionError(f"no line matching {pattern!r}; output:\n" + "\n".join(self.lines[-40:]))

    def command(self, c):
        self.p.stdin.write(c + "\n")
        self.p.stdin.flush()

    def quit(self):
        try:
            self.command("q")
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()


def write(d, name, text):
    # (a new inode, the way editors save: the watcher must see renames too)
    tmp = os.path.join(d, "." + name + ".tmp")
    with open(tmp, "w", newline="") as f:          # (byte for byte: no \r\n on Windows)
        f.write(text)
    os.replace(tmp, os.path.join(d, name))


GAME = """\
speed = 2.0
x = 0.0
xs = [1, 2, 3]
update = (dt: f64):
    x += speed
    if frame_number() % 10 == 0: print("tick x={x} label={label()} pick={pick()}")
    sleep(0.005)
label = () -> str: "one"
pick = () -> int: xs[1]
draw = ():
    clear(BLACK)
    circle(vec2(f32(x), 300), 20, WHITE)
"""


def test_game(d):
    write(d, "g.jo", GAME)
    w = Watch(d, "g.jo")
    try:
        w.expect(r"tick .* label=one pick=2")
        # a function changes: the game keeps its state (x goes on)
        x0 = float(w.expect(r"tick x=([0-9.]+)").group(1))
        write(d, "g.jo", GAME.replace('"one"', '"two"'))
        w.expect(r"reloaded in \d+ ms: label")
        m = w.expect(r"tick x=([0-9.]+) label=two")
        assert float(m.group(1)) > x0, "state was lost"
        # a global's declaration changes: it is set again; others keep their values
        g2 = GAME.replace('"one"', '"two"').replace("speed = 2.0", "speed = 1000.0")
        write(d, "g.jo", g2)
        w.expect(r"set again: speed")
        a = float(w.expect(r"tick x=([0-9.]+)").group(1))
        b = float(w.expect(r"tick x=([0-9.]+)").group(1))
        assert b - a >= 9000, f"speed not set again ({a} -> {b})"
        # new functions and globals
        g3 = g2.replace("pick = () -> int: xs[1]", "bonus = 40\npick = () -> int: xs[1] + extra()\nextra = () -> int: bonus + 2")
        write(d, "g.jo", g3)
        w.expect(r"reloaded in \d+ ms: pick; new: bonus")
        w.expect(r"pick=44")
        # a panic pauses the game; fixing it goes on
        g4 = g3.replace("xs[1] + extra()", "xs[7] + extra()")
        write(d, "g.jo", g4)
        w.expect(r"panic: g.jo:\d+: index 7 out of bounds")
        w.expect(r"paused")
        # an error keeps the game as it was
        write(d, "g.jo", g4.replace('"two"', '"two" +'))
        w.expect(r"error: ")
        w.expect(r"keeps running the last version")
        write(d, "g.jo", g3.replace('"two"', '"three"'))
        w.expect(r"going on")
        w.expect(r"tick .* label=three pick=44")
        # restart: a fresh start
        w.command("r")
        w.expect(r"tick x=1000.0 label=three")
    finally:
        w.quit()


def test_modules_release(d):
    write(d, "helper.jo", 'helper_name = () -> str: "h1"\nscale = (x: int) -> int: x * 2\n')
    main = """\
build:
    opt = release
use 'helper.jo'
counter = 0
hook: (int) -> int = (a: int) -> int: a + 1
update = (dt: f64):
    counter = hook(counter)
    if frame_number() % 10 == 0: print("tick counter={counter} name={helper_name()} scale={scale(3)}")
    sleep(0.005)
draw = (): clear(BLACK)
"""
    write(d, "m.jo", main)
    w = Watch(d, "m.jo")
    try:
        w.expect(r"name=h1 scale=6")
        write(d, "helper.jo", 'helper_name = () -> str: "h2"\nscale = (x: int) -> int: x * 2\n')
        w.expect(r"reloaded")
        w.expect(r"name=h2 scale=6")
        write(d, "m.jo", main.replace("a + 1", "a + 1000"))
        w.expect(r"set again: hook")
        a = int(w.expect(r"counter=(\d+)").group(1))
        b = int(w.expect(r"counter=(\d+)").group(1))
        assert b - a >= 9000, f"the new lambda does not run ({a} -> {b})"
    finally:
        w.quit()


MIGRATE = """\
struct Agent:
    id: int
    hp: int
    pos: vec2
    tags: str[]
struct Node:
    v: int
    kids: Node[]
agents: Agent[]
boss = Agent(id = 99, hp = 500, pos = vec2(1, 2), tags = ["big"])
by_id: {int: Agent} = {}
tree = Node(1, [Node(2, []), Node(3, [Node(4, [])])])
loop i in [0..3):
    agents.push(Agent(id = i, hp = 100 - i, pos = vec2(f32(i), 0), tags = ["t{i}"]))
    by_id[i] = agents[i]
sumtree = (n: Node) -> int:
    s = n.v
    loop k in n.kids: s += sumtree(k)
    s
update = (dt: f64):
    loop mut a in agents: a.pos.x += 1.0
    if frame_number() % 10 == 0: print("tick {show()}")
    sleep(0.005)
show = () -> str: "n={agents.len()} id={agents[2].id} hp={agents[2].hp} moved={agents[2].pos.x > 5.0} tag={agents[1].tags[0]} boss={boss.hp} map={by_id[1].hp} tree={sumtree(tree)}"
draw = (): clear(BLACK)
"""


def test_migrate(d):
    # the layout of a struct the game holds changes: the values are kept, field by field
    write(d, "g.jo", MIGRATE)
    w = Watch(d, "g.jo")
    try:
        w.expect(r"tick n=3 id=2 hp=98 moved=\w+ tag=t1 boss=500 map=99 tree=10")
        g2 = MIGRATE.replace("""struct Agent:
    id: int
    hp: int
    pos: vec2
    tags: str[]""", """struct Agent:
    pos: vec2
    name: str = "anon"
    hp: f64
    id: int
    tags: str[]
    level = 7""").replace("""struct Node:
    v: int
    kids: Node[]""", """struct Node:
    w: int = 5
    kids: Node[]
    v: int""").replace('show = () -> str: "', 'show = () -> str: "{agents[2].name} {agents[2].level} {tree.kids[1].kids[0].w} ')
        write(d, "g.jo", g2)
        w.expect(r"kept, in their new layout: agents, boss, by_id, tree")
        w.expect(r"tick anon 7 5 n=3 id=2 hp=98.0 moved=true tag=t1 boss=500.0 map=99.0 tree=10")
    finally:
        w.quit()


FIXED = """\
struct Inv:
    slots: int[3]
    pos: vec2[2]
inv = Inv()
loop i in [0..3): inv.slots[i] = 10 + i
inv.pos[1] = vec2(5, 6)
update = (dt: f64):
    inv.pos[0].x += 1.0
    if frame_number() % 10 == 0: print("tick {show()}")
    sleep(0.005)
show = () -> str: "slots={inv.slots} p1={inv.pos[1]} moved={inv.pos[0].x > 3.0}"
draw = (): clear(BLACK)
"""


def test_migrate_fixed(d):
    # fixed-size arrays in a struct whose layout changes: element by element, new ones zero
    write(d, "g.jo", FIXED)
    w = Watch(d, "g.jo")
    try:
        w.expect(r"tick slots=\[10, 11, 12\] p1=vec2\(5.0, 6.0\)")
        write(d, "g.jo", FIXED.replace("slots: int[3]", "slots: f64[4]"))
        w.expect(r"kept, in their new layout: inv")
        w.expect(r"tick slots=\[10.0, 11.0, 12.0, 0.0\] p1=vec2\(5.0, 6.0\) moved=true")
    finally:
        w.quit()


def test_assets(d):
    # a file a global's declaration names, and the functions a GPU program is made from
    src = open(os.path.join(root, "examples", "cube.jo")).read()
    src = src.replace("update = (dt: f64): t += dt", "update = (dt: f64):\n    t += dt\n    if frame_number() % 10 == 0: print(\"tick level={len(level)} prog={prog.prog}\")\n    sleep(0.005)")
    src += 'level = embed("level.txt")\n'
    write(d, "level.txt", "hello level\n")
    write(d, "g.jo", src)
    w = Watch(d, "g.jo")
    try:
        p0 = int(w.expect(r"tick level=12 prog=(\d+)").group(1))
        write(d, "level.txt", "a longer level text\n")
        w.expect(r"set again: level")
        w.expect(r"tick level=20")
        write(d, "g.jo", src.replace("pulse = 0.85 + 0.15", "pulse = 0.5 + 0.5"))
        w.expect(r"reloaded in \d+ ms: cube_fs; set again: prog")
        p1 = int(w.expect(r"tick level=20 prog=(\d+)").group(1))
        assert p1 != p0, "the GPU program was not made again"
    finally:
        w.quit()


def test_restarts(d):
    # what a running game cannot take: top-level statements (a hint), update/draw appearing
    src = 'n = 0\nprint("start")\nupdate = (dt: f64):\n    n += 1\n    if n % 10 == 0: print("tick")\n    sleep(0.005)\n'
    write(d, "g.jo", src)
    w = Watch(d, "g.jo")
    try:
        w.expect(r"^start")
        w.expect(r"tick")
        write(d, "g.jo", src.replace('print("start")', 'print("start again")'))
        w.expect(r"top-level statements changed")
        write(d, "g.jo", src.replace('print("start")', 'print("start again")') + "draw = (): clear(BLACK)\n")
        w.expect(r"update or draw was added or removed")
        w.expect(r"^start again")
    finally:
        w.quit()


def test_program(d):
    # without update/draw: run again from the start on each change
    write(d, "p.jo", 'print("run one")\n')
    w = Watch(d, "p.jo", game=False)
    try:
        w.expect(r"run one")
        w.expect(r"the program ended \(exit status 0\)")
        write(d, "p.jo", 'print("run two")\n')
        w.expect(r"run two")
    finally:
        w.quit()


tests = [test_game, test_modules_release, test_migrate, test_migrate_fixed, test_assets, test_restarts, test_program]
passed = failed = 0
for t in tests:
    with tempfile.TemporaryDirectory() as d:
        try:
            t(d)
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"FAIL {t.__name__}: {e}")
print(f"{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
