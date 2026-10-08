# Jot requirements report

Generated 2026-10-08 13:56 on x86_64 Linux (8 hardware threads). Load average at start: 1.2. Times are best-of-N CPU times (user + sys) unless noted; instruction counts are exact.

## 1. Self-hosting

- C bootstrap -> jot1 -> jot2 -> jot3, jot2 == jot3 byte for byte: **yes**
- compiler: 20357 lines of Jot; standard library: 11472 lines of Jot
- `bin/jot` size: 2860 KB, built by itself in release mode

## 2. Tests

| mode | result |
|---|---|
| native, debug | 43 passed, 0 failed |
| native, release | 43 passed, 0 failed |
| web (wasm under node), debug | 37 passed, 0 failed |
| web (wasm under node), release | 37 passed, 0 failed |
| C bootstrap compiler | 17 passed, 0 failed |
| language server (`jot lsp`, driven as an editor would) | 50 passed, 0 failed |
| rendering (software renderer vs references; also on the GPU when there is a display) | 16 passed, 0 failed |
| differential fuzzing: random programs (unions, closures, soa, n-D arrays...) built 4 ways (+ the C bootstrap compiler for its subset) | 60 programs, 0 mismatches (seeds 5354762..5354821) |

## 3. Compile speed

Generated program `bench/big.jot`: 50009 lines (2000 functions, loops, structs, strings, floats), and the equivalent C program `bench/big.c` (66012 lines).

| compiler | CPU time | lines / second | instructions |
|---|---|---|---|
| jot (debug build) | 0.210 s | 238,138 | 1.45 G |
| jot (release build) | 0.510 s | 98,057 | 3.77 G |
| gcc -O0 | 5.060 s | 13,046 | |

Release builds take 2.4x the time of debug builds (requirement: at most 10x).

## 4. Script workflow (`jot file.jot`: compile + run)

| program | lines | compile + run (wall) |
|---|---|---|
| hello world | 1 | 17 ms |
| examples/lumen/lumen.jot (compile only) | 453 | 64 ms |
| examples/dunes/dunes.jot (compile only) | 430 | 63 ms |

## 5. Runtime performance vs C

Each benchmark exists as Jot and as equivalent C (`bench/rt`). Ratios are Jot time / C time (lower is better).

| benchmark | C -O2 | C -O0 | Jot release | Jot debug | release / C -O2 |
|---|---|---|---|---|---|
| fannkuch | 0.18 s | 0.40 s | 0.38 s | 1.03 s | 2.11x |
| mandel | 0.21 s | 0.40 s | 0.24 s | 0.25 s | 1.14x |
| nbody | 0.35 s | 1.35 s | 0.53 s | 2.22 s | 1.51x |
| sieve | 0.11 s | 0.26 s | 0.13 s | 0.31 s | 1.18x |
| spectral | 0.10 s | 0.38 s | 0.18 s | 1.05 s | 1.80x |

Geometric mean, Jot release / C -O2: **1.51x**.

Hot loops of a game (`bench/loops`): nanoseconds per element, Jot release vs C -O2 (the C dotted expression also makes a new array each time):

| loop | C -O2 | Jot release | ratio |
|---|---|---|---|
| aos update | 3.07 ns | 3.76 ns | 1.22x |
| soa update | 2.20 ns | 2.31 ns | 1.05x |
| struct field arrays | 1.20 ns | 1.21 ns | 1.01x |
| plain arrays | 1.16 ns | 1.59 ns | 1.37x |
| dotted new array | 1.52 ns | 2.44 ns | 1.61x |
| sin | 10.56 ns | 17.95 ns | 1.70x |
| cos | 10.95 ns | 17.96 ns | 1.64x |

## 6. CPU parallelism

`parallel_map` over 1M Collatz lengths on 8 hardware threads: **4.7x** faster than `map` (results identical: true).

## 7. Native executables are static

- hello world: 8816 bytes; no program interpreter and no shared library dependencies: **yes**
- 3D game (dunes): 667 KB; static: **yes** (the GPU driver is loaded at run time if present; without one it renders in software, see section 10)
- the compiler writes machine code and ELF files itself: no assembler, linker or C toolchain is used

## 8. Web builds

- lumen: single file `lumen.html`, 435 KB, external references: 0; opened from file:// in headless Chrome: 1421 distinct colors in the frame, **renders**
- dunes: single file `dunes.html`, 463 KB, external references: 0; opened from file:// in headless Chrome: 3678 distinct colors in the frame, **renders**

## 9. Games (native, OpenGL ES 3)

| game | mode | frame CPU time (update + draw + submit) | pixels, how frames reach the screen | screenshot |
|---|---|---|---|---|
| lumen | debug | 2.48 ms | 2133x1200 pixels, wayland+libdecor dma-buf, scale 1.667 | 1938 colors |
| lumen | release | 2.09 ms | 2133x1200 pixels, wayland+libdecor dma-buf, scale 1.667 | 1938 colors |
| dunes | debug | 3.34 ms | 2133x1200 pixels, wayland+libdecor dma-buf, scale 1.667 | 7678 colors |
| dunes | release | 2.78 ms | 2133x1200 pixels, wayland+libdecor dma-buf, scale 1.667 | 7678 colors |

## 10. Without a GPU driver (software renderer)

With no OpenGL ES driver (or `JOT_SOFTWARE=1`) the same binaries draw with a multithreaded software renderer that runs the Jot shader functions on the CPU, at half resolution. Without libX11 it speaks the X11 protocol itself, and screenshot runs need no display at all. Below, frame 60 of each game rendered with no display and no GPU, compared with the GPU's frame:

| game | software frame CPU time | mean abs difference vs GPU frame (0-255) |
|---|---|---|
| cube | 2.48 ms | 0.56 |
| lumen | 20.67 ms | 1.28 |
| dunes | 78.29 ms | 1.13 |

