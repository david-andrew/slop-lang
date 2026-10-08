#!/usr/bin/env python3
"""Build the Jot playground: one self-contained web page with the compiler (compiled to
WebAssembly by itself), the standard library and examples. The page compiles and runs programs
on its own (open it from disk, or serve it anywhere).
usage: tools/playground.py [output.html]        (default: build/playground.html)"""
import base64, gzip, json, os, re, subprocess, sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "build", "playground.html")
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
jot = os.path.join(root, "bin", "jot")
env = dict(os.environ, JOT_LIB=os.path.join(root, "lib"))

# the compiler, as WebAssembly (it builds as a web page: take the module out of it)
tmp = os.path.join(root, "build", "playground-compiler")
subprocess.run([jot, "build", os.path.join(root, "compiler", "main.jot"), "--target", "wasm", "-o", tmp], check=True, env=env)
page = open(tmp + ".html").read()
wasm = base64.b64decode(re.search(r'const JOT_WASM = "([^"]*)"', page).group(1))
os.remove(tmp + ".html")
gz = lambda b: base64.b64encode(gzip.compress(b, 9)).decode()

# the standard library, at /jot/lib
lib = {}
for d, _, names in os.walk(os.path.join(root, "lib")):
    for n in sorted(names):
        full = os.path.join(d, n)
        lib["/jot/lib/" + os.path.relpath(full, os.path.join(root, "lib"))] = base64.b64encode(open(full, "rb").read()).decode()

# examples: the playground's own, then the repository's games
examples = {}
exdir = os.path.join(root, "tools", "playground", "examples")
for n in sorted(os.listdir(exdir)):
    if n.endswith(".jot"):
        examples[re.sub(r"^\d+-", "", n[:-4])] = open(os.path.join(exdir, n)).read()
for name, path in [("shapes (2D)", "examples/shapes.jot"), ("lumen (2D game)", "examples/lumen/lumen.jot"),
                   ("cube (3D)", "examples/cube.jot"), ("scene (3D)", "examples/scene3d.jot"), ("dunes (3D game)", "examples/dunes/dunes.jot")]:
    full = os.path.join(root, path)
    if os.path.exists(full): examples[name] = open(full).read()

html = open(os.path.join(root, "tools", "playground", "page.html")).read()
host = open(os.path.join(root, "tools", "playground", "host.js")).read()
html = html.replace('"/*JOT_COMPILER*/"', json.dumps(gz(wasm)))
html = html.replace('"/*JOT_LIB*/"', json.dumps(gz(json.dumps(lib).encode())))
html = html.replace("/*JOT_EXAMPLES*/", json.dumps(examples).replace("</", "<\\/"))
html = html.replace("/*JOT_HOST*/", host)
open(out, "w").write(html)
print(f"{out}: {len(html) // 1024} KB (compiler {len(wasm) // 1024} KB of WebAssembly)")
