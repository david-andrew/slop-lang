# Sloppy roadmap

Where Sloppy is (v0.3.0, October 2026): a self-hosted compiler (~24k lines of Sloppy, plus a C
bootstrap) that compiles a 50k-line program in 0.18 s, runs programs at ~1.24x the time of C -O2
(release), and targets Linux x86-64, Windows x64 and the web (one .html file). It has a game
library (window, input, gamepads, 2D/3D drawing with a 2D camera, collision and particle helpers,
shadows, shaders written in Sloppy that run on the GPU or a software renderer, an audio mixer,
PNG/WAV), hot reloading (`sloppy watch`), a REPL (Linux), a language server and VS Code
extension, a playground, backtraces, DWARF, modules.

The aim stays the same: a small language that feels like Python and runs like C, for making
games, with the shortest path from an idea to something running and shippable.

Items are in priority order. Sizes: S = days, M = a week or two, L = several weeks. (This order
was revised after an outside review of the project; its verified findings are in item 1.)

## 1. Correctness first, and kept that way (ongoing)

Done in 0.3.1, from the outside review: closures can no longer form reference cycles (a local
variable that can hold functions cannot be shared with closures); a generic type that expands
without end is an error, not a compiler crash; `sloppy check` and the language server follow the
build block's target; the build block's `output` works and its mistakes are errors; `load_wav`
reads 24/32-bit and float64 files and rejects what it cannot read; `reverse(str)` keeps
characters whole; `to_int` is none for numbers that do not fit. Gates: error tests reject
compiler crashes, compiles time out, CI runs the web target in release mode and a mutation
fuzzer (`tools/fuzz_errors.py`: real programs broken at random must get an error, never a crash);
docs/COMPILER.md describes the compiler for contributors.

Left:
- An element changed through a `mut` parameter while the function also holds a copy of its
  array can be made to contain that copy (`attach(nodes[0], nodes)` storing `nodes` into the
  node): a cycle, and a write the copy sees. Copy-in/copy-out for such arguments would close it,
  at a cost to the common `update(players[i])`; decide with real game code in hand.
- Keep each bug found as a test; run the fuzzers before releases.

## 2. Finish one small game, with its tutorial (ongoing)

Done: Rebound (examples/rebound) is the flagship game: a one-file arcade game (turn a shield
around a core to catch turrets' bolts and send them back; chain blasts, bank shots, upgrades
every few turrets, a saved best score), chosen over a platformer (Lumen, retired) for being
quick to pick up and worth replaying. It plays itself behind its title; with a reaction delay
the same autopilot measured the difficulty curve (0.45 s: about 80 s survived, 0.3 s: 3 to 5
minutes). It runs on Linux, Windows and the web, on the website (sloppy-lang.org/rebound/) and in
the playground (#example=rebound, with its icon: the playground carries examples' other files).
The website has two tutorials, each eight steps that run, with links into the playground (the
tests build every step): docs/TUTORIAL.md (Firefly, a platformer) and docs/TUTORIAL_REBOUND.md
(Little Rebound, a small version of Rebound). A 3D one could follow, built on dunes.

Left: upload Rebound to itch.io (needs an account: the zip is `sloppy build --target wasm -o
rebound.zip`), play it on real machines (people, not the autopilot, for the difficulty), and
write down what was awkward. What the games showed so far: menus were missing (now
lib/game/ui.jo), saving was missing (save_data), the key that opens a menu must not also work
it (ui.jo now ignores input in a menu's first frame; `ui_ready()` for a game's own keys), and a top-level assignment to a used module's variable made a new one (fixed). A
local variable in a function with a global's name and type changes the global (as designed,
but easy to trip over in a big file: a lint that flags it may be worth having). The larger
jotw/botw-clone projects come after, as the 3D test.

## 3. Shipping essentials (alongside 2)

Done (0.3.1): `save_data`/`load_data` (a per-user place on desktop, the browser's storage on the
web; PROGRAM_NAME and the build block's `name`); `load_wav` rejects what it cannot read; web
builds as an itch.io-ready zip (`-o game.zip`); program icons (`icon = "icon.png"`: the Windows
.exe's icon and window icon, the page's favicon); the error convention (`T | SomeError`, passed on
with `if r is SomeError: return r`) in the language reference.

Left:
- Linux window icons (X11's _NET_WM_ICON; Wayland desktops take icons from .desktop files).
- A whole asset directory embedded at once (`embed` takes one file).
- A serializer (structs <-> text) for saves and settings, if hand-written formats keep recurring.
- Sugar for passing errors on (a `try`), if code shows the two-line pattern is too much.

## 4. Windows, in separate steps

- a. Check on real hardware (S): window, OpenGL on Intel/AMD/NVIDIA drivers, DPI scaling,
  fullscreen, raw mouse, XInput, sound (never heard yet), alt-tab, minimize.
- b. Done (0.3.1): `sloppy watch` on Windows (each build in a process of its own given the link
  map; the program's pipes passed as handles; files watched by their write times). Left: a
  panic in reloaded code names the wrong function in its backtrace.
- c. The interactive prompt on Windows (S, on b's machinery).
- d. Debugging (M): unwind tables (.pdata/.xdata) so Windows' tools can walk the stack, then
  CodeView/PDB line info for Visual Studio, WinDbg and RemedyBG.
- Code signing is out of reach for now; document what SmartScreen shows and how to get past it.

## 5. Game library gaps (L, in pieces, as the game needs them)

Already there: a 2D camera, AABB/circle collision helpers, particles, a sun with shadows,
instancing, SDF text with a built-in font, menus (ui.jo). Done: sprite sheets and animations
(grids, or Aseprite's JSON with its tags), tilemaps (from text, or Tiled's JSON with groups,
objects and compressed layers) with drawing of what is on screen and box movement that stops at
tiles (examples/tiles.jo), JSON (parse_json/to_json), base64. Missing:
- Assets: OGG Vorbis (music), TTF/OTF fonts (into the SDF atlas), JPEG, glTF 2.0 meshes
  (skinning later), Tiled's external tilesets (.tsj; embedded ones work).
- 2D: slopes and one-way platforms in tilemaps, tweening, camera follow/shake helpers.
- 3D: free/orbit camera controllers, frustum culling, skyboxes.
- Debug panels (ui.jo has menus).
- Networking (UDP; WebSocket/WebRTC on the web) — later.

## 6. Everyday tools (M)

- `sloppy fmt`, and format on save in the extension.
- Debugging recipes: a VS Code launch configuration for gdb/lldb with the DWARF already emitted,
  and pretty-printers for arrays, strings and optionals.
- Profiling: name Sloppy functions and lines in `perf` (and a frame-time view for games).
- Packages, minimally: another person's Sloppy code by git URL or path in the `build:` block,
  pinned by commit; no registry.
- Language server: quick fixes for common errors, workspace symbols, semantic highlighting.

## 7. Language (M, ongoing)

Keep it small; fill the gaps real programs hit:
- Constraints for generic code (today errors appear only where a generic is used).
- Fixed-size array lengths as generic parameters (`T[N]`).
- Text: bytes vs code points vs what is displayed, made clear in the API; formatting polish.
- A consistency review, then a written list of what is stable, before any 1.0.

## 8. Compiler maintainability (ongoing, never a rewrite)

expr.jo and lower.jo are ~4k lines each, much state is global, and AST nodes reuse generic fields.
Split large files by feature when touching them, keep configuration in one place (item 1's
target bug came from two copies of it), and document invariants per phase.

## 9. Performance (ongoing)

- Measure the finished game first: allocation churn and frame-time spikes matter more than the
  synthetic benchmarks.
- Then the remaining gap to C -O2 in release builds (fannkuch 1.5x, spectral 1.4x, nbody 1.3x).
- Compile speed stays first: debug builds are the default; track compile time in CI.

## 10. More platforms (L each, later)

- arm64: a new encoder and calling conventions, register reservations that are x86-specific
  today, and per-OS system call numbers in the runtime. Linux on arm64 first.
- macOS after that: Mach-O with ad hoc code signatures, a Cocoa window, Metal (or OpenGL 4.1),
  CoreAudio, GameController.

## 11. Community (S, ongoing)

An examples gallery (each runnable in the browser), a changelog per release, issue templates.

## Not planned for now

Tracing garbage collection (item 1 still has to settle closure cycles), exceptions, inheritance,
a JIT, a central package registry, consoles (their SDKs are under NDA).
