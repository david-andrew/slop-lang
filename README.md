<p align="center">
  <img src="assets/logo-256.png" alt="Jot: a white clover blossom" width="200">
</p>

<h1 align="center">jot</h1>

<p align="center"><b>a simple game dev language</b></p>

<p align="center">
  <a href="https://github.com/david-andrew/slop-lang/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/david-andrew/slop-lang?label=release&color=2f6a7a"></a>
  <a href="https://github.com/david-andrew/slop-lang/actions/workflows/test.yml"><img alt="Tests" src="https://img.shields.io/github/actions/workflow/status/david-andrew/slop-lang/test.yml?label=tests"></a>
  <a href="https://david-andrew.github.io/slop-lang/"><img alt="Website" src="https://img.shields.io/github/actions/workflow/status/david-andrew/slop-lang/site.yml?label=website"></a>
  <a href="https://david-andrew.github.io/slop-lang/playground/"><img alt="Try it in the browser" src="https://img.shields.io/badge/playground-try%20it%20in%20the%20browser-2f6a7a"></a>
  <img alt="Platform: Linux x86-64 and the web" src="https://img.shields.io/badge/platform-linux%20x86--64%20%7C%20web-555">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-555"></a>
</p>

Jot is a small, compiled, statically typed language that feels like a scripting language,
built for making games. `jot game.jot` compiles the whole program and runs it in a blink;
`jot build game.jot` writes a fully static Linux executable, and with `target = wasm` a
single self-contained `.html` file that runs in a browser straight from disk.

```jot
# hello.jot
print("hello, world")

fib = (n: int) -> int:
    if n < 2: return n
    fib(n - 1) + fib(n - 2)

nums = [5 3 9 1]
nums.sort()
squares = nums.map((x): x * x)
add = (a: int, b: int): a + b
print(squares, add(1, _)(41), fib(30))
print(nums .* 2.5 .+ 1, sqrt.([4.0 9.0]), [1 2; 3 4] * [1 0; 0 1])
```

A complete (tiny) game:

```jot
pos = vec2(400, 300)

update = (dt: f64):
    dir = vec2(0, 0)
    if key_down(.left): dir.x -= 1
    if key_down(.right): dir.x += 1
    if key_down(.up): dir.y -= 1
    if key_down(.down): dir.y += 1
    pos += dir * f32(300 * dt)

draw = ():
    clear(rgb(0.08, 0.08, 0.12))
    circle(pos, 24, rgb(1.0, 0.6, 0.2))
    text("arrow keys", vec2(20, 20), 24, rgb(1, 1, 1))
```

## Highlights

- **Fast compiles.** About 250,000 lines per second on one core (debug builds), roughly 20x
  faster than `gcc -O0`. Hello world compiles and runs in ~10 ms. There are no incremental
  builds and no build system: build options live in the source (`build:` block).
- **Fast programs.** Release builds (`opt = release`) are within ~1.5x of `gcc -O2` on the
  benchmark set (geometric mean), with bounds checks kept on. `parallel_map` and friends use
  every core.
- **Easy.** Type inference everywhere, Python-like indentation syntax, first-class functions
  (`f = (x: int): x * 2`), closures, partial application (`f(1, _)`), generics without
  ceremony (untyped parameters), uniform call syntax (`x.f(y)` is `f(x, y)`), one `loop` for
  every kind of loop, type unions (`int | ParseError`) with `is`, optionals, unit literals
  (`120ms`, `1.2(m/s)`).
- **Numeric arrays.** numpy-style elementwise operators that broadcast (`a .* b .+ 1`,
  `f.(xs)`) and compile to one fused loop, 2-D arrays (`[1 2; 3 4]`, matrix products),
  `zeros`/`linspace`/`rand`..., struct-of-arrays storage (`soa Particle[]`), and GPU arrays
  (`gpu(xs)`): the same dotted expressions on them compile to a GPU program.
- **Predictable.** Plain value semantics: arrays, strings and maps are reference counted with
  copy-on-write, so there is no garbage collector, no reference cycles and no hidden aliasing.
- **Batteries for games.** Windows and input, 2D drawing with SDF text, a 3D renderer with
  sun/sky lighting, shadows, fog and bloom, GPU programs written in Jot itself (translated to
  GLSL), PNG/WAV loading, a software audio mixer and synthesizer.
- **Programs keep working.** Native executables are static (they talk to the kernel directly);
  the GPU driver is loaded at run time when present, and without one games still run on a
  multithreaded software renderer. Web builds are one HTML file with the WebAssembly embedded. The compiler needs no assembler, linker or C toolchain.
- **Self-hosted.** The compiler is written in Jot (~15k lines) and compiles itself; a small
  C compiler in `stage0/` bootstraps it.

## Getting started

Install (Linux x86-64; into `~/.jot`, added to your PATH; run again, or `jot upgrade`, to upgrade):

```
curl -fsSL https://david-andrew.github.io/slop-lang/install | bash
```

Or try it in the browser: [the playground](https://david-andrew.github.io/slop-lang/playground/).

From source:

Requirements: Linux x86-64; a C compiler is needed once, to build the bootstrap compiler.

```
tools/bootstrap.sh            # stage0 (C) -> jot1 -> jot2 -> jot3, checks jot2 == jot3, installs bin/jot
bin/jot                       # an interactive prompt
bin/jot examples/shapes.jot   # compile and run
bin/jot examples/lumen/lumen.jot          # the 2D demo game
bin/jot examples/dunes/dunes.jot          # the 3D demo game
bin/jot --web examples/dunes/dunes.jot    # the same game in the browser
bin/jot build examples/dunes/dunes.jot --target wasm -o dunes.html   # a page to keep or share
bin/jot test tests/unit/sample_test.jot  # run `test` blocks
bin/jot check file.jot        # type check only
```

`bin/jot` finds the standard library in `lib/` next to its own directory (or `$JOT_LIB`).

**In the browser:** `tools/playground.py` builds `build/playground.html`, one self-contained
page (1.4 MB) with an editor, examples and the Jot compiler itself, compiled to WebAssembly:
programs (games included) compile in the page in well under 100 ms and run beside the editor.
Share links carry the program in the address.

## Editors

`jot lsp` is a language server (the Language Server Protocol, on standard input and output):
errors as you type, hover with types and doc comments, go to definition, references, rename,
completion, signature help, inlay hints for inferred types, and an outline. It is the compiler
itself answering, so it agrees with the compiler by construction.

VS Code: `tools/vsix.py` packages the extension in `editors/vscode` (highlighting, the language
server, and commands to run a file in a terminal or the browser, or its tests);
`code --install-extension build/jot-0.1.0.vsix` installs it.

Other editors: run `jot lsp` for `*.jot` files. For example, Neovim (0.11):

```lua
vim.lsp.config('jot', { cmd = { 'jot', 'lsp' }, filetypes = { 'jot' }, root_markers = { '.git' } })
vim.lsp.enable('jot')
vim.filetype.add({ extension = { jot = 'jot' } })
```

and Helix (`languages.toml`):

```toml
[language-server.jot]
command = "jot"
args = ["lsp"]

[[language]]
name = "jot"
scope = "source.jot"
file-types = ["jot"]
comment-token = "#"
indent = { tab-width = 4, unit = "    " }
language-servers = ["jot"]
```

## Documentation

The website (built by `tools/site.py`, published by `.github/workflows/site.yml`) has these
pages and the playground.

- [docs/LANGUAGE.md](docs/LANGUAGE.md) — the language
- [docs/API.md](docs/API.md) — the standard library (generated from `lib/`)
- [docs/REPORT.md](docs/REPORT.md) — measured results for the design goals (`tools/report.py`)

## Repository layout

```
compiler/      the Jot compiler, in Jot
  lex, parse, ast        source -> syntax tree
  check, expr, types     name resolution, type inference, overloading, generics
  lower                  syntax tree -> IR (register based, structured control flow)
  opt, inline            release builds: folding, CSE, check elimination, inlining
  x64, elf               IR -> x86-64 machine code -> static ELF executable
  wasm                   IR -> WebAssembly, packaged into one HTML file
  glsl                   shader functions written in Jot -> GLSL ES 3.00
  ide, lsp               the language server (jot lsp): what the checker learns, for editors
  repl                   the interactive prompt: compiles each input against a live session
stage0/        bootstrap compiler in C (compiles compiler/ once)
lib/core/      runtime, strings, arrays, maps, math, files, formatting
lib/std/       thread pool and parallel helpers, numeric arrays (nd.jot)
lib/game/      windows (Wayland, X11), input, OpenGL ES / WebGL, 2D, 3D, images, audio
lib/web/       JavaScript glue embedded into web builds
editors/       the VS Code extension (tools/vsix.py packages it)
examples/      demos: lumen (2D), dunes (3D), shapes, cube, scene3d
tests/         test programs with expected output (tools/runtests.py), render references
bench/         benchmarks (Jot and equivalent C)
tools/         bootstrap, test runner, render test, differential fuzzer, language server test,
               headless GNOME screenshots (gnomeshot.py), the web playground (playground.py,
               playground/), the website (site.py, site/), report, profiler, instruction counter
```

Testing: `tools/runtests.py` runs the test programs in each mode (native/web, debug/release,
and with the C bootstrap compiler); `tools/rendertest.py` checks software-rendered frames
against references; `tools/fuzz.py` generates random programs and compares five builds of
each — native and web, debug and release, and the independent C bootstrap compiler, which
catches mistakes the four self-hosted builds would share.

## How it works

The compiler parses and type-checks the whole program (the standard library is always
included and only what is used gets compiled), lowers it to a compact IR, and generates
machine code directly: a linear-scan register allocator and an x86-64 encoder write the ELF
file in one pass. Release builds additionally run an IR optimizer — constant folding, copy
propagation, common-subexpression and redundant-load elimination keyed by memory class,
bounds-check and copy-on-write-check elimination, inlining of small functions, and folding of
array indexing into x86 addressing modes.

Native programs are static executables that make Linux system calls directly. Programs that
open a window load the system's libraries for it at run time with a tiny in-process loader (the
static binary maps the system dynamic linker and asks it for the libraries): libwayland-client
and libdecor in a Wayland session (so windows get the desktop's own decorations; frames are
rendered with EGL into an offscreen buffer shared with the compositor), otherwise X11; and EGL
and OpenGL ES. Nothing is loaded at all by programs that do not use graphics, and a missing
library is a run-time decision instead of a load-time failure: without an OpenGL ES driver
(or with `JOT_SOFTWARE=1`) games draw with a software renderer (`lib/game/softgl.jot`) that
runs the Jot shader functions on the CPU in parallel, at half resolution; without
libwayland-client or libX11 the window is opened by speaking the Wayland or X11 protocol over
the socket (`lib/game/wayland.jot`, `lib/game/x11.jot`), and without libdecor the program
draws its own title bar. The
software frames match the GPU's within about 1/255 per channel (`tools/rendertest.py` checks
them against references, with no GPU or display needed).

The web backend emits WebAssembly from the same IR; the HTML file contains the module (base64)
and a small JavaScript runtime for WebGL 2, input and audio.

## License

MIT (see [LICENSE](LICENSE)), so programs built with Jot, which include its runtime and
library, can be released under any license. The logo is not covered by it; the default font
is Noto Sans, under the SIL Open Font License ([lib/game/assets/OFL.txt](lib/game/assets/OFL.txt)).
