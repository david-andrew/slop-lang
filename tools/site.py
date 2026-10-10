#!/usr/bin/env python3
"""Build Sloppy's website into build/site: a home page, the docs (from the Markdown files) and the
playground. Static files only: serve the directory anywhere (GitHub Pages: .github/workflows).
usage: tools/site.py [output-dir]          (needs bin/sloppy, for the playground)"""
import base64, zlib, html, os, re, shutil, subprocess, sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "build", "site")
here = os.path.join(root, "tools", "site")
REPO = "https://github.com/david-andrew/sloppy-lang"

# ---- Markdown (the subset the docs use) ----

def slug(text):
    s = re.sub(r"<[^>]+>", "", text).lower()
    s = re.sub(r"[^a-z0-9 _-]", "", s).strip().replace(" ", "-")
    return re.sub(r"-+", "-", s) or "section"

LINKS = {"docs/TUTORIAL.md": "tutorial.html", "TUTORIAL.md": "tutorial.html",
         "docs/TUTORIAL_REBOUND.md": "tutorial-rebound.html", "TUTORIAL_REBOUND.md": "tutorial-rebound.html", "docs/LANGUAGE.md": "language.html", "LANGUAGE.md": "language.html", "docs/API.md": "api.html",
         "API.md": "api.html", "docs/REPORT.md": "report.html", "REPORT.md": "report.html", "README.md": "start.html",
         "../README.md": "start.html"}

def inline(t):
    # code spans first (their contents are literal)
    parts = re.split(r"(`[^`]+`)", t)
    outp = []
    for p in parts:
        if p.startswith("`") and p.endswith("`") and len(p) > 1:
            outp.append("<code>" + html.escape(p[1:-1]) + "</code>")
            continue
        p = html.escape(p, quote=False)
        def link(m):
            label, url = m.group(1), m.group(2)
            base, hash_, anchor = url.partition("#")
            if base in LINKS: url = LINKS[base] + hash_ + anchor
            elif base and not re.match(r"^(https?:|mailto:)", url) and not base.endswith(".html"):
                # a file in the repository (from docs/, ../x is x)
                if base.startswith("../"): base = base[3:]
                kind = "/blob/master/" if re.search(r"\.(md|jo|py|js)$", base) else "/tree/master/"
                url = REPO + kind + base + hash_ + anchor
            return f'<a href="{url}">{label}</a>'
        p = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", link, p)
        p = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", p)
        p = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", p)
        p = re.sub(r"(?<!\w)_(?!\s)([^_]+?)(?<!\s)_(?!\w)", r"<em>\1</em>", p)
        outp.append(p)
    return "".join(outp)

def markdown(src):
    lines = src.split("\n")
    out, toc = [], []
    i = 0
    para = []
    seen = set()

    def flush():
        nonlocal para
        if para:
            text = ""
            for k, l in enumerate(para):
                # (two trailing spaces: a line break)
                text += inline(l.rstrip()) + ("<br>" if l.endswith("  ") and k < len(para) - 1 else " ")
            out.append("<p>" + text.strip() + "</p>")
            para = []

    def lists(i):
        # a list starting at line i (bullets or numbers, nested by indentation)
        items, kind = [], None
        base = len(lines[i]) - len(lines[i].lstrip())
        while i < len(lines):
            l = lines[i]
            m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", l)
            if not m or len(m.group(1)) < base:
                if l.strip() and items and len(l) - len(l.lstrip()) > base:
                    items[-1][1].append(l.strip())
                    i += 1
                    continue
                break
            ind = len(m.group(1))
            if ind > base:
                sub, i = lists(i)
                items[-1][2].append(sub)
                continue
            kind = kind or ("ol" if m.group(2)[0].isdigit() else "ul")
            items.append([m.group(3), [], []])
            i += 1
        h = f"<{kind}>" + "".join("<li>" + inline(" ".join([t] + more)) + "".join(subs) + "</li>" for t, more, subs in items) + f"</{kind}>"
        return h, i

    while i < len(lines):
        l = lines[i]
        if l.startswith("```"):
            flush()
            lang = l[3:].strip()
            body = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                body.append(lines[i])
                i += 1
            i += 1
            # Sloppy code is fenced as gdscript: GitHub has no grammar for Sloppy, and GDScript's
            # (Godot's language) is the closest it has; here it gets Sloppy's own highlighting
            cls = "sloppy" if lang in ("sloppy", "gdscript") else lang or "plain"
            out.append(f'<pre><code class="{cls}">' + html.escape("\n".join(body)) + "</code></pre>")
            # a whole program (the tutorial's steps start with "# step"): a link that opens it in
            # the playground (its share-link form: #code=<deflated, base64url>)
            if cls == "sloppy" and body and body[0].startswith("# step"):
                z = zlib.compressobj(9, zlib.DEFLATED, -15)
                code = base64.urlsafe_b64encode(z.compress("\n".join(body).encode()) + z.flush()).decode().rstrip("=")
                out.append(f'<p class="play"><a href="../playground/#code={code}">Run it in the playground</a></p>')
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", l)
        if m:
            flush()
            n = len(m.group(1))
            text = inline(m.group(2))
            s = slug(m.group(2))
            while s in seen: s += "-"
            seen.add(s)
            if n in (2, 3): toc.append((n, s, re.sub(r"<[^>]+>", "", text)))
            out.append(f'<h{n} id="{s}"><a class="anchor" href="#{s}">{text}</a></h{n}>')
            i += 1
            continue
        if re.match(r"^<(p|h[1-6]|div|img|a|table|details|picture)\b", l):
            # raw HTML: as it is (until an empty line), images relative to the site's root
            flush()
            block = []
            while i < len(lines) and lines[i].strip():
                block.append(lines[i])
                i += 1
            out.append(re.sub(r'src="assets/', 'src="../assets/', "\n".join(block)))
            continue
        if l.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, body = rows[0], [r for r in rows[1:] if not all(re.match(r"^:?-+:?$", c) for c in r)]
            t = "<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
            t += "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
            out.append(t + "</tbody></table>")
            continue
        if re.match(r"^\s*([-*]|\d+\.)\s+", l) and not re.match(r"^\s*-{3,}\s*$", l):
            flush()
            h, i = lists(i)
            out.append(h)
            continue
        if l.startswith(">"):
            flush()
            q = []
            while i < len(lines) and lines[i].startswith(">"):
                q.append(lines[i][1:].strip())
                i += 1
            out.append("<blockquote><p>" + inline(" ".join(q)) + "</p></blockquote>")
            continue
        if re.match(r"^\s*-{3,}\s*$", l):
            flush()
            out.append("<hr>")
            i += 1
            continue
        if not l.strip():
            flush()
            i += 1
            continue
        para.append(l)
        i += 1
    flush()
    return "\n".join(out), toc

# ---- pages ----

def nav(here_page, prefix):
    items = [("Docs", "docs/start.html"), ("Tutorial", "docs/tutorial.html"), ("Language", "docs/language.html"), ("Library", "docs/api.html"),
             ("Playground", "playground/"), ("Report", "docs/report.html")]
    links = "".join(f'<a class="{"on" if p == here_page else ""}" href="{prefix}{p}">{n}</a>' for n, p in items)
    return (f'<nav class="top"><a class="brand" href="{prefix}index.html"><img src="{prefix}icon-64.png" alt="">Sloppy</a>'
            f'<div class="links">{links}</div><div class="spacer"></div><a href="{REPO}">GitHub</a></nav>')

SITE = "https://sloppy-lang.org"
DESCRIPTION = ("A small, statically typed language for making games that feels like Python and runs like C. "
               "It compiles in milliseconds, to a native Linux or Windows executable or a single web page.")

# what chat apps and social sites show for a link (Open Graph, and Twitter's cards); the
# image is assets/social.png (1200x630)
def preview_meta(title, description, path):
    t, d = html.escape(title, quote=True), html.escape(description, quote=True)
    return (f'<meta name="description" content="{d}">'
            f'<meta property="og:type" content="website"><meta property="og:site_name" content="Sloppy">'
            f'<meta property="og:title" content="{t}"><meta property="og:description" content="{d}">'
            f'<meta property="og:url" content="{SITE}/{path}">'
            f'<meta property="og:image" content="{SITE}/social.png"><meta property="og:image:width" content="1200">'
            f'<meta property="og:image:height" content="630">'
            f'<meta property="og:image:alt" content="sloppy: a simple game dev language">'
            f'<meta name="twitter:card" content="summary_large_image"><meta name="theme-color" content="#2f6a7a">')

def page(title, body, here_page, prefix, extra_head="", description=DESCRIPTION):
    path = "" if here_page == "index.html" else here_page
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>{preview_meta(title, description, path)}
<link rel="icon" href="{prefix}icon-32.png"><link rel="stylesheet" href="{prefix}style.css">{extra_head}
</head><body>{nav(here_page, prefix)}
{body}
<footer>Sloppy &middot; <a href="{REPO}">source on GitHub</a> &middot; <a href="{REPO}/blob/master/LICENSE">MIT license</a></footer>
<script src="{prefix}highlight.js"></script>
<script>for (const c of document.querySelectorAll("pre code.sloppy")) c.innerHTML = sloppyHighlight(c.textContent, 0).replace(/\\n$/, "");</script>
</body></html>
"""

DOCS = [("start.html", "README.md", "Getting started"), ("tutorial.html", "docs/TUTORIAL.md", "Make a game"),
        ("tutorial-rebound.html", "docs/TUTORIAL_REBOUND.md", "Make an arcade game"),
        ("language.html", "docs/LANGUAGE.md", "The language"),
        ("api.html", "docs/API.md", "Standard library"), ("report.html", "docs/REPORT.md", "Report")]
DOC_DESCRIPTIONS = {
    "start.html": "Install Sloppy, a simple game dev language, and write your first program and game.",
    "tutorial.html": "Make a small platformer in Sloppy, step by step: moving, jumping, platforms, a camera, menus, saving, glow and music.",
    "tutorial-rebound.html": "Make a small arcade game in Sloppy, step by step: angles, many things at once, chain reactions, upgrades and synthesized sound.",
    "language.html": "The Sloppy language: types, functions, structs and unions, numeric arrays, modules, parallelism, the game loop and calling C.",
    "api.html": "Everything in Sloppy's standard library: strings, maps, math, files, threads, windows, input, 2D and 3D drawing, shaders and audio.",
    "report.html": "Measured results for Sloppy's design goals: compile speed, program speed against C, and executable size."}

def build_docs():
    os.makedirs(os.path.join(out, "docs"), exist_ok=True)
    for name, src, title in DOCS:
        text = open(os.path.join(root, src)).read()
        body, toc = markdown(text)
        pages = "".join(f'<a class="{"on" if n == name else ""}" href="{n}">{t}</a>' for n, _, t in DOCS)
        tocs = "".join(f'<a class="h{n}" href="#{s}">{t}</a>' for n, s, t in toc)
        main = f'<div class="doc"><aside><div class="pages">{pages}</div><div class="toc">{tocs}</div></aside><main>{body}</main></div>'
        here_page = "docs/" + name
        open(os.path.join(out, "docs", name), "w").write(page(f"{title} | Sloppy", main, here_page, "../", description=DOC_DESCRIPTIONS[name]))

HOME = """
<section class="hero">
  <div>
    <h1><span>sloppy</span>: a simple game dev language</h1>
    <p class="lead">A small, statically typed language that feels like Python and runs like C. One command
    compiles and runs your program in milliseconds, as a native Linux or Windows executable or as a single web page.</p>
    <pre class="install"><code><span class="c"># Linux</span>
curl -fsSL https://sloppy-lang.org/install | bash
<span class="c"># Windows (PowerShell)</span>
irm https://sloppy-lang.org/install.ps1 | iex</code></pre>
    <div class="buttons"><a class="btn primary" href="playground/">Try it in your browser</a>
    <a class="btn" href="docs/start.html">Get started</a><a class="btn" href="docs/tutorial.html">Make a game</a><a class="btn" href="docs/language.html">The language</a></div>
  </div>
  <div class="art"><img class="logo" src="logo-512.png" alt="a white clover blossom">
  <pre><code class="sloppy">pos = vec2(400, 300)

update = (dt: f64):
    pos += input_axis() * f32(300 * dt)

draw = ():
    clear(rgb(0.08, 0.08, 0.12))
    circle(pos, 24, rgb(1.0, 0.6, 0.2))
    text("arrow keys", vec2(20, 20), 24, WHITE)</code></pre></div>
</section>
<section class="features">
  <div class="feature"><h3>Instant compiles</h3><p>About 250,000 lines a second. Hello world compiles and runs in about 10 ms; there is no build system, options live in the source.</p></div>
  <div class="feature"><h3>Fast programs</h3><p>Release builds run within about 1.5&times; of gcc -O2, with bounds checks on. <code>parallel_map</code> uses every core; GPU arrays run on the GPU.</p></div>
  <div class="feature"><h3>Easy</h3><p>Type inference everywhere, indentation syntax, closures, partial application, generics without ceremony, unions, value semantics with no garbage collector.</p></div>
  <div class="feature"><h3>Made for games</h3><p>Windows, input, 2D drawing, a 3D renderer with shadows and bloom, shaders written in Sloppy, audio, pixel art and any screen shape, all built in.</p></div>
  <div class="feature"><h3>Runs anywhere it lands</h3><p>Native programs are static executables with no dependencies; web builds are one HTML file. Graphics drivers are optional: there is a software renderer.</p></div>
  <div class="feature"><h3>Self-hosted</h3><p>The compiler is written in Sloppy and compiles itself, even in this site's playground, where it runs as WebAssembly.</p></div>
</section>
<section class="showcase">
  <a href="rebound/"><img src="assets/rebound.png" alt="Rebound: a shield arcs around a glowing core; a chain of blasts runs through a line of turrets"></a>
  <div>
    <h2>Rebound</h2>
    <p>A complete arcade game in one file of Sloppy. Turn the shield to catch the turrets' bolts and send
    them back: blasts set off the turrets beside them, catches near the shield's edge bank off to other
    turrets, and every few turrets you choose an upgrade. Menus, settings, a saved best score, and sound
    made by the built-in synthesizer.</p>
    <div class="buttons"><a class="btn primary" href="rebound/">Play it</a><a class="btn" href="playground/#example=rebound">Change it in the playground</a>
    <a class="btn" href="https://github.com/david-andrew/sloppy-lang/blob/master/examples/rebound/rebound.jo">Read the source</a></div>
  </div>
</section>
<section class="strip">
  <h2>Numbers, arrays, and the rest</h2>
  <pre><code class="sloppy">fib = (n: int) -> int:
    if n < 2: return n
    fib(n - 1) + fib(n - 2)

nums = [5 3 9 1]
nums.sort()
add = (a: int, b: int): a + b
print(nums.map((x): x * x), add(1, _)(41), fib(30))
print(nums .* 2.5 .+ 1, sqrt.([4.0 9.0]), [1 2; 3 4] * [1 0; 0 1])</code></pre>
  <p>Editors: <code>sloppy lsp</code> is a language server (and there is a <a href="https://marketplace.visualstudio.com/items?itemName=RedFoxLabs.sloppy">VS Code / Cursor extension</a>). An interactive prompt: run <code>sloppy</code> with no file.</p>
</section>
"""

def main():
    if os.path.exists(out): shutil.rmtree(out)
    os.makedirs(out)
    shutil.copy(os.path.join(here, "style.css"), out)
    for f in ["icon-32.png", "icon-64.png", "logo-512.png", "social.png"]: shutil.copy(os.path.join(root, "assets", f), out)
    shutil.copytree(os.path.join(root, "assets"), os.path.join(out, "assets"))
    shutil.copy(os.path.join(root, "tools", "playground", "highlight.js"), out)
    open(os.path.join(out, "index.html"), "w").write(page("Sloppy: a simple game dev language", HOME, "index.html", ""))
    build_docs()
    os.makedirs(os.path.join(out, "playground"))
    subprocess.run([sys.executable, os.path.join(root, "tools", "playground.py"), os.path.join(out, "playground", "index.html")], check=True)
    # (the playground's title leads back to the site)
    pg = os.path.join(out, "playground", "index.html")
    t = open(pg).read().replace('<h1><span>Sloppy</span> playground</h1>', '<h1><a href="../" style="color:inherit"><span>Sloppy</span></a> playground</h1>', 1)
    t = t.replace('<title>Sloppy playground</title>', '<title>Sloppy playground</title><link rel="icon" href="../icon-32.png">'
                  + preview_meta("Sloppy playground", "Write and run Sloppy programs and games in your browser: the compiler itself runs here, as WebAssembly.", "playground/"), 1)
    open(pg, "w").write(t)
    # Rebound, to play (sloppy-lang.org/rebound/)
    os.makedirs(os.path.join(out, "rebound"))
    subprocess.run([os.path.join(root, "bin", "sloppy"), "build", os.path.join(root, "examples", "rebound", "rebound.jo"), "--target", "wasm",
                    "-o", os.path.join(out, "rebound", "index.html")], check=True, env=dict(os.environ, SLOPPY_LIB=os.path.join(root, "lib")))
    # curl -fsSL .../install | bash
    shutil.copy(os.path.join(root, "tools", "install.sh"), os.path.join(out, "install"))
    # irm https://sloppy-lang.org/install.ps1 | iex
    shutil.copy(os.path.join(root, "tools", "install.ps1"), os.path.join(out, "install.ps1"))
    open(os.path.join(out, ".nojekyll"), "w").close()
    print(out)

main()
