<p align="center">
  <img src="assets/logo-256.png" alt="Sloppy: a white clover blossom" width="200">
</p>

<h1 align="center">sloppy</h1>

<p align="center"><b>a simple game dev language</b></p>

<p align="center">
  <a href="https://github.com/david-andrew/sloppy-lang/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/david-andrew/sloppy-lang?label=release&color=2f6a7a"></a>
  <a href="https://github.com/david-andrew/sloppy-lang/actions/workflows/test.yml"><img alt="Tests" src="https://img.shields.io/github/actions/workflow/status/david-andrew/sloppy-lang/test.yml?label=tests"></a>
  <a href="https://sloppy-lang.org/"><img alt="Website" src="https://img.shields.io/github/actions/workflow/status/david-andrew/sloppy-lang/site.yml?label=website"></a>
  <a href="https://sloppy-lang.org/playground/"><img alt="Try it in the browser" src="https://img.shields.io/badge/playground-try%20it%20in%20the%20browser-2f6a7a"></a>
  <img alt="Platform: Linux and Windows on x86-64, and the web" src="https://img.shields.io/badge/platform-linux%20%7C%20windows%20%7C%20web-555">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-555"></a>
</p>

Sloppy is a small, compiled, statically typed language that feels like a scripting language,
built for making games. `sloppy game.jo` compiles the whole program and runs it in a blink;
`sloppy build game.jo` writes a standalone executable for Linux or Windows, and with
`target = wasm` a single self-contained `.html` file that runs in a browser straight from disk.

```gdscript
# hello.jo
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

```gdscript
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
- **Edit while it runs.** `sloppy watch game.jo` reloads the running game as you save: new code
  takes over between two frames, and the game keeps its state, its window and what it loaded.
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
  sun/sky lighting, shadows, fog and bloom, GPU programs written in Sloppy itself (translated to
  GLSL), PNG/WAV loading, a software audio mixer and synthesizer.
- **Programs keep working.** Native executables are static (they talk to the kernel directly);
  the GPU driver is loaded at run time when present, and without one games still run on a
  multithreaded software renderer. Web builds are one HTML file with the WebAssembly embedded. The compiler needs no assembler, linker or C toolchain.
- **Self-hosted.** The compiler is written in Sloppy (~15k lines) and compiles itself; a small
  C compiler in `stage0/` bootstraps it.

## Getting started

Install on Linux (x86-64; into `~/.sloppy`, added to your PATH; `sloppy update` installs newer releases):

```sh
curl -fsSL https://sloppy-lang.org/install | bash
```

On Windows (10 or 11, x64; into `%LOCALAPPDATA%\sloppy`, added to your PATH), in PowerShell:

```powershell
irm https://sloppy-lang.org/install.ps1 | iex
```

(On Windows, the interactive prompt and `sloppy watch` are not there yet; everything else is.)

Or try it in the browser: [the playground](https://sloppy-lang.org/playground/). Then
[make a game](docs/TUTORIAL.md): a small platformer, built step by step.

From source:

Requirements: Linux x86-64; a C compiler is needed once, to build the bootstrap compiler.

```sh
tools/bootstrap.sh            # stage0 (C) -> sloppy1 -> sloppy2 -> sloppy3, checks sloppy2 == sloppy3, installs bin/sloppy
bin/sloppy                       # an interactive prompt
bin/sloppy examples/shapes.jo   # compile and run
bin/sloppy examples/lumen/lumen.jo          # a small complete 2D game (four valleys, menus, saves)
bin/sloppy examples/dunes/dunes.jo          # the 3D demo game
bin/sloppy watch examples/lumen/lumen.jo    # ... reloaded as you edit it, without restarting
bin/sloppy --web examples/dunes/dunes.jo    # the same game in the browser
bin/sloppy build examples/dunes/dunes.jo --target wasm -o dunes.html   # a page to keep or share
bin/sloppy test tests/unit/sample_test.jo  # run `test` blocks
bin/sloppy check file.jo        # type check only
```

`bin/sloppy` finds the standard library in `lib/` next to its own directory (or `$SLOPPY_LIB`).
Working on the compiler itself: [docs/COMPILER.md](docs/COMPILER.md).

**In the browser:** `tools/playground.py` builds `build/playground.html`, one self-contained
page (1.4 MB) with an editor, examples and the Sloppy compiler itself, compiled to WebAssembly:
programs (games included) compile in the page in well under 100 ms and run beside the editor.
Share links carry the program in the address.

## Editors

`sloppy lsp` is a language server (the Language Server Protocol, on standard input and output):
errors as you type, hover with types and doc comments, go to definition, references, rename,
completion, signature help, inlay hints for inferred types, and an outline. It is the compiler
itself answering, so it agrees with the compiler by construction.

VS Code, Cursor and VSCodium: the [Sloppy extension](https://marketplace.visualstudio.com/items?itemName=RedFoxLabs.sloppy)
(also [on Open VSX](https://open-vsx.org/extension/RedFoxLabs/sloppy)): highlighting, the language
server, and commands to run a file in a terminal or the browser, or its tests.
`code --install-extension RedFoxLabs.sloppy` installs it. Its source is `editors/vscode`;
`tools/vsix.py` packages it (`build/sloppy-<version>.vsix`).

Other editors: run `sloppy lsp` for `*.jo` files. For example, Neovim (0.11):

```lua
vim.lsp.config('sloppy', { cmd = { 'sloppy', 'lsp' }, filetypes = { 'sloppy' }, root_markers = { '.git' } })
vim.lsp.enable('sloppy')
vim.filetype.add({ extension = { jo = 'sloppy' } })
```

and Helix (`languages.toml`):

```toml
[language-server.sloppy]
command = "sloppy"
args = ["lsp"]

[[language]]
name = "sloppy"
scope = "source.sloppy"
file-types = ["jo"]
comment-token = "#"
indent = { tab-width = 4, unit = "    " }
language-servers = ["sloppy"]
```

## Documentation

The website (built by `tools/site.py`, published by `.github/workflows/site.yml`) has these
pages and the playground.

- [docs/LANGUAGE.md](docs/LANGUAGE.md) — the language
- [docs/API.md](docs/API.md) — the standard library (generated from `lib/`)
- [docs/REPORT.md](docs/REPORT.md) — measured results for the design goals (`tools/report.py`)

## Repository layout

```
compiler/      the Sloppy compiler, in Sloppy
  lex, parse, ast        source -> syntax tree
  check, expr, types     name resolution, type inference, overloading, generics
  lower                  syntax tree -> IR (register based, structured control flow)
  opt, inline            release builds: folding, CSE, check elimination, inlining
  x64, elf               IR -> x86-64 machine code -> static ELF executable
  wasm                   IR -> WebAssembly, packaged into one HTML file
  glsl                   shader functions written in Sloppy -> GLSL ES 3.00
  ide, lsp               the language server (sloppy lsp): what the checker learns, for editors
  repl                   the interactive prompt: compiles each input against a live session
stage0/        bootstrap compiler in C (compiles compiler/ once)
lib/core/      runtime, strings, arrays, maps, math, files, formatting
lib/std/       thread pool and parallel helpers, numeric arrays (nd.jo)
lib/game/      windows (Wayland, X11), input, OpenGL ES / WebGL, 2D, 3D, images, audio
lib/web/       JavaScript glue embedded into web builds
editors/       the VS Code extension (tools/vsix.py packages it)
examples/      lumen (a complete 2D game), dunes (3D), shapes, cube, scene3d
tests/         test programs with expected output (tools/runtests.py), render references
bench/         benchmarks (Sloppy and equivalent C)
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

Windows programs (`--target windows`, the default on Windows) are PE executables that import
only what finds everything else (LoadLibraryA, GetProcAddress and three more from kernel32.dll):
the rest of Windows is looked up as it is first used, as C libraries are on Linux. Games open a
Win32 window and draw with OpenGL through WGL (the same shaders: a core 4.3 context accepts them),
or with the software renderer; gamepads are XInput's, sound goes through waveOut.

On Linux, native programs are static executables that make system calls directly. Programs that
open a window load the system's libraries for it at run time with a tiny in-process loader (the
static binary maps the system dynamic linker and asks it for the libraries): libwayland-client
and libdecor in a Wayland session (so windows get the desktop's own decorations; frames are
rendered with EGL into an offscreen buffer shared with the compositor), otherwise X11; and EGL
and OpenGL ES. Nothing is loaded at all by programs that do not use graphics, and a missing
library is a run-time decision instead of a load-time failure: without an OpenGL ES driver
(or with `SLOPPY_SOFTWARE=1`) games draw with a software renderer (`lib/game/softgl.jo`) that
runs the Sloppy shader functions on the CPU in parallel, at half resolution; without
libwayland-client or libX11 the window is opened by speaking the Wayland or X11 protocol over
the socket (`lib/game/wayland.jo`, `lib/game/x11.jo`), and without libdecor the program
draws its own title bar. The
software frames match the GPU's within about 1/255 per channel (`tools/rendertest.py` checks
them against references, with no GPU or display needed).

The web backend emits WebAssembly from the same IR; the HTML file contains the module (base64)
and a small JavaScript runtime for WebGL 2, input and audio.

## License

MIT (see [LICENSE](LICENSE) and [NOTICE](NOTICE)), so programs built with Sloppy, which include its runtime and
library, can be released under any license. The logo is not covered by it; the default font
is Noto Sans, under the SIL Open Font License ([lib/game/assets/OFL.txt](lib/game/assets/OFL.txt)).
