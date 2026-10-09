# Sloppy roadmap

Where Sloppy is (v0.3.0, October 2026): a self-hosted compiler (~24k lines of Sloppy, plus a C
bootstrap) that compiles a 50k-line program in 0.18 s, runs programs at ~1.24x the time of C -O2
(release), and targets Linux x86-64, Windows x64 and the web (one .html file). It has a game
library (window, input, gamepads, 2D/3D drawing with a 2D camera, collision and particle helpers,
shadows, shaders written in Sloppy that run on the GPU or a software renderer, an audio mixer,
PNG/WAV), hot reloading (`sloppy watch`, Linux), a REPL (Linux), a language server and VS Code
extension, a playground, backtraces, DWARF, modules.

The aim stays the same: a small language that feels like Python and runs like C, for making
games, with the shortest path from an idea to something running and shippable.

Items are in priority order. Sizes: S = days, M = a week or two, L = several weeks. (This order
was revised after an outside review of the project; its verified findings are in item 1.)

## 1. Correctness first, and kept that way (M, then ongoing)

What Sloppy already promises has to hold before more is built on it. Verified problems:

- **Closures can form reference cycles that leak**: an array of closures that capture the array
  itself is never freed (`fs: (() -> int)[]; f = () -> int: fs.len(); fs.push(f)` leaks 3
  allocations per call). The docs say cycles cannot happen. Decide the rule (forbid a closure
  from capturing a container it is stored in, weak captures, or a cycle collector for closure
  environments only), test it, and correct the docs now.
- **The compiler overflows its stack** printing a type that expands without end
  (`struct Box[T]: child: Box[T[]][]`, then `print(Box[int]())`): bound generic expansion and
  report an error at the source.
- **`sloppy check` and the language server ignore `target = windows`** (they only set up the
  wasm target), so `when TARGET == "windows"` branches are checked the wrong way round. One
  shared target/configuration setup for build, check and the LSP.
- **The `build:` block's `output` option is ignored**, and misspelled keys (`targte`) are
  accepted silently. One parser for the build block, with errors for unknown keys.
- **24-bit WAV files load as silence**: support 24-bit PCM, and reject formats that are not
  supported with a clear error instead of zeros.
- **`reverse(str)` reverses bytes**, which breaks UTF-8: reverse code points.
- **`to_int` wraps out-of-range input** (`to_int("18446744073709551616")` is `0`): return none.

And the gates that keep it this way:
- Error tests must see a compiler diagnostic, never an internal panic; every compile in the test
  runner has a timeout; CI also runs the web target in release mode.
- Fuzz malformed and unusual programs (the existing fuzzer only makes valid ones) and keep each
  crash found as a test.
- A short contributor guide to the compiler: its phases, what state each owns, how to add a test.

## 2. Finish one small game, with its tutorial (M, ongoing)

One jam-sized 2D game, finished: title screen, a beginning and an end, restart, menus, music and
sounds, saved settings and progress; playable on Linux, Windows and the web from one source, and
uploaded somewhere real (itch.io). Write the website tutorial as the game is built, step by step,
runnable in the playground. Everything it trips over feeds the items below and re-ranks them;
limitations it works around are written down rather than allowed to grow it into an engine.
(The larger jotw/botw-clone projects come after, as the 3D test.)

## 3. Shipping essentials (M, alongside 2)

- Saves that last: a per-user save directory on desktop, and on the web storage that survives a
  reload (today `write_file` in the browser only keeps data in memory); a simple serializer
  (structs <-> text) for saves and settings.
- Assets that fail loudly: loaders validate their input and say what is wrong and where.
- `sloppy build` makes an upload-ready bundle per platform: one executable with a whole asset
  directory embedded, an icon (Windows resource), and for the web an itch.io-ready .zip.
- An error-handling convention for this kind of code (`T | Error` with a short way to pass an
  error up), since loading and saving are where errors happen.

## 4. Windows, in separate steps

- a. Check on real hardware (S): window, OpenGL on Intel/AMD/NVIDIA drivers, DPI scaling,
  fullscreen, raw mouse, XInput, sound (never heard yet), alt-tab, minimize.
- b. `sloppy watch` on Windows (M): hot reload is what most sets Sloppy apart for games, and most
  game developers use Windows. Process control without fork (CreateProcess, shared memory, a pipe
  protocol) in place of ptrace/fork/inotify.
- c. The interactive prompt on Windows (S, on b's machinery).
- d. Debugging (M): unwind tables (.pdata/.xdata) so Windows' tools can walk the stack, then
  CodeView/PDB line info for Visual Studio, WinDbg and RemedyBG.
- Code signing is out of reach for now; document what SmartScreen shows and how to get past it.

## 5. Game library gaps (L, in pieces, as the game needs them)

Already there: a 2D camera, AABB/circle collision helpers, particles, a sun with shadows,
instancing, SDF text with a built-in font. Missing:
- Assets: OGG Vorbis (music), TTF/OTF fonts (into the SDF atlas), sprite sheets/atlases, JPEG,
  glTF 2.0 meshes (skinning later).
- 2D: sprite animation, tilemaps (Tiled import), swept collision, tweening, camera follow/shake.
- 3D: free/orbit camera controllers, frustum culling, skyboxes.
- Immediate-mode UI for menus and debug panels.
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
