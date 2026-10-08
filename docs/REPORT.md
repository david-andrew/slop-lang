# Jot requirements report

Generated 2026-10-08 08:57 on x86_64 Linux (8 hardware threads). Load average at start: 1.2. Times are best-of-N CPU times (user + sys) unless noted; instruction counts are exact.

## 1. Self-hosting

- C bootstrap -> jot1 -> jot2 -> jot3, jot2 == jot3 byte for byte: **yes**
- compiler: 17284 lines of Jot; standard library: 10448 lines of Jot
- `bin/jot` size: 2323 KB, built by itself in release mode

## 2. Tests

| mode | result |
|---|---|
| native, debug | 41 passed, 0 failed |
| native, release | 41 passed, 0 failed |
| web (wasm under node), debug | 37 passed, 0 failed |
| web (wasm under node), release | 37 passed, 0 failed |
| C bootstrap compiler | 17 passed, 0 failed |
| rendering (software renderer vs references; also on the GPU when there is a display) | 14 passed, 0 failed |
| differential fuzzing: random programs (unions, closures, soa, n-D arrays...) built 4 ways (+ the C bootstrap compiler for its subset) | 60 programs, 0 mismatches (seeds 511387671..511387730) |

## 3. Compile speed

Generated program `bench/big.jot`: 50009 lines (2000 functions, loops, structs, strings, floats), and the equivalent C program `bench/big.c` (66012 lines).

| compiler | CPU time | lines / second | instructions |
|---|---|---|---|
| jot (debug build) | 0.180 s | 277,828 | 1.45 G |
| jot (release build) | 0.470 s | 106,402 | 3.76 G |
| gcc -O0 | 4.560 s | 14,476 | |

Release builds take 2.6x the time of debug builds (requirement: at most 10x).

## 4. Script workflow (`jot file.jot`: compile + run)

| program | lines | compile + run (wall) |
|---|---|---|
| hello world | 1 | 14 ms |
| examples/lumen/lumen.jot (compile only) | 453 | 54 ms |
| examples/dunes/dunes.jot (compile only) | 430 | 54 ms |

## 5. Runtime performance vs C

Each benchmark exists as Jot and as equivalent C (`bench/rt`). Ratios are Jot time / C time (lower is better).

| benchmark | C -O2 | C -O0 | Jot release | Jot debug | release / C -O2 |
|---|---|---|---|---|---|
| fannkuch | 0.17 s | 0.37 s | 0.35 s | 0.96 s | 2.06x |
| mandel | 0.20 s | 0.36 s | 0.21 s | 0.21 s | 1.05x |
| nbody | 0.33 s | 1.31 s | 0.50 s | 2.15 s | 1.52x |
| sieve | 0.10 s | 0.25 s | 0.13 s | 0.29 s | 1.30x |
| spectral | 0.09 s | 0.35 s | 0.17 s | 1.01 s | 1.89x |

Geometric mean, Jot release / C -O2: **1.52x**.

Hot loops of a game (`bench/loops`): nanoseconds per element, Jot release vs C -O2 (the C dotted expression also makes a new array each time):

| loop | C -O2 | Jot release | ratio |
|---|---|---|---|
| aos update | 2.99 ns | 3.66 ns | 1.22x |
| soa update | 2.18 ns | 2.26 ns | 1.04x |
| struct field arrays | 1.12 ns | 1.18 ns | 1.05x |
| plain arrays | 1.12 ns | 1.54 ns | 1.38x |
| dotted new array | 1.57 ns | 2.31 ns | 1.47x |
| sin | 10.20 ns | 17.05 ns | 1.67x |
| cos | 10.70 ns | 17.07 ns | 1.60x |

## 6. CPU parallelism

`parallel_map` over 1M Collatz lengths on 8 hardware threads: **4.6x** faster than `map` (results identical: true).

## 7. Native executables are static

- hello world: 8816 bytes; no program interpreter and no shared library dependencies: **yes**
- 3D game (dunes): 604 KB; static: **yes** (the GPU driver is loaded at run time if present; without one it renders in software, see section 10)
- the compiler writes machine code and ELF files itself: no assembler, linker or C toolchain is used

## 8. Web builds

- lumen: single file `lumen.html`, 444 KB, external references: 0; opened from file:// in headless Chrome: 1424 distinct colors in the frame, **renders**
- dunes: single file `dunes.html`, 474 KB, external references: 0; opened from file:// in headless Chrome: 3676 distinct colors in the frame, **renders**

## 9. Games (native, OpenGL ES 3)

| game | mode | frame CPU time (update + draw + submit) | pixels, how frames reach the screen | screenshot |
|---|---|---|---|---|
| lumen | debug | 2.81 ms | 2133x1200 pixels, wayland dma-buf, scale 1.667 | 1938 colors |
| lumen | release | 2.50 ms | 2133x1200 pixels, wayland dma-buf, scale 1.667 | 1938 colors |
| dunes | debug | 3.48 ms | 2133x1200 pixels, wayland dma-buf, scale 1.667 | 7678 colors |
| dunes | release | 3.10 ms | 2133x1200 pixels, wayland dma-buf, scale 1.667 | 7678 colors |

## 10. Without a GPU driver (software renderer)

With no OpenGL ES driver (or `JOT_SOFTWARE=1`) the same binaries draw with a multithreaded software renderer that runs the Jot shader functions on the CPU, at half resolution. Without libX11 it speaks the X11 protocol itself, and screenshot runs need no display at all. Below, frame 60 of each game rendered with no display and no GPU, compared with the GPU's frame:

| game | software frame CPU time | mean abs difference vs GPU frame (0-255) |
|---|---|---|
| cube | 2.36 ms | 0.56 |
| lumen | 17.16 ms | 1.28 |
| dunes | 65.26 ms | 1.13 |

