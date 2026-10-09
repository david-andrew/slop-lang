# Jot requirements report

Generated 2026-10-08 16:42 on x86_64 Linux (8 hardware threads). Load average at start: 3.2. Times are best-of-N CPU times (user + sys) unless noted; instruction counts are exact.

## 1. Self-hosting

- C bootstrap -> jot1 -> jot2 -> jot3, jot2 == jot3 byte for byte: **yes**
- compiler: 22174 lines of Jot; standard library: 11502 lines of Jot
- `bin/jot` size: 2952 KB, built by itself in release mode

## 2. Tests

| mode | result |
|---|---|
| native, debug | 47 passed, 0 failed |
| native, release | 47 passed, 0 failed |
| web (wasm under node), debug | 41 passed, 0 failed |
| web (wasm under node), release | 41 passed, 0 failed |
| C bootstrap compiler | 17 passed, 0 failed |
| language server (`jot lsp`, driven as an editor would) | 50 passed, 0 failed |
| rendering (software renderer vs references; also on the GPU when there is a display) | 16 passed, 0 failed |
| differential fuzzing: random programs (unions, closures, soa, n-D arrays...) built 4 ways (+ the C bootstrap compiler for its subset) | 60 programs, 0 mismatches (seeds 463448809..463448868) |

## 3. Compile speed

Generated program `bench/big.jot`: 50009 lines (2000 functions, loops, structs, strings, floats), and the equivalent C program `bench/big.c` (66012 lines).

| compiler | CPU time | lines / second | instructions |
|---|---|---|---|
| jot (debug build) | 0.220 s | 227,314 | 1.34 G |
| jot (release build) | 0.500 s | 100,018 | 3.33 G |
| gcc -O0 | 6.250 s | 10,562 | |

Release builds take 2.3x the time of debug builds (requirement: at most 10x).

## 4. Script workflow (`jot file.jot`: compile + run)

| program | lines | compile + run (wall) |
|---|---|---|
| hello world | 1 | 32 ms |
| examples/lumen/lumen.jot (compile only) | 453 | 119 ms |
| examples/dunes/dunes.jot (compile only) | 430 | 190 ms |

## 5. Runtime performance vs C

Each benchmark exists as Jot and as equivalent C (`bench/rt`). Ratios are Jot time / C time (lower is better).

| benchmark | C -O2 | C -O0 | Jot release | Jot debug | release / C -O2 |
|---|---|---|---|---|---|
| fannkuch | 0.23 s | 0.43 s | 0.29 s | 1.00 s | 1.26x |
| mandel | 0.22 s | 0.40 s | 0.22 s | 0.24 s | 1.00x |
| nbody | 0.40 s | 1.54 s | 0.66 s | 2.36 s | 1.65x |
| sieve | 0.11 s | 0.26 s | 0.13 s | 0.31 s | 1.18x |
| spectral | 0.10 s | 0.39 s | 0.14 s | 0.92 s | 1.40x |

Geometric mean, Jot release / C -O2: **1.28x**.

Hot loops of a game (`bench/loops`): nanoseconds per element, Jot release vs C -O2 (the C dotted expression also makes a new array each time):

| loop | C -O2 | Jot release | ratio |
|---|---|---|---|
| aos update | 3.21 ns | 3.16 ns | 0.98x |
| soa update | 2.17 ns | 1.70 ns | 0.78x |
| struct field arrays | 1.24 ns | 0.87 ns | 0.70x |
| plain arrays | 1.22 ns | 0.75 ns | 0.61x |
| dotted new array | 1.64 ns | 1.28 ns | 0.78x |
| sin | 11.23 ns | 13.45 ns | 1.20x |
| cos | 11.42 ns | 13.78 ns | 1.21x |

Loops the compiler vectorizes (`bench/simd`, arrays that fit in the cache): nanoseconds per element. Jot uses AVX2 where the processor has it and SSE2 otherwise (`JOT_NO_AVX=1` forces SSE2), from one executable; gcc -O2 vectorizes with SSE2, the x86-64 baseline:

| loop | C -O2 | Jot (AVX2) | Jot (SSE2) | same results |
|---|---|---|---|---|
| axpy f32 | 0.212 ns | 0.112 ns | 0.193 ns | yes |
| scale f64 | 0.428 ns | 0.203 ns | 0.336 ns | yes |
| iadd i32 | 0.139 ns | 0.089 ns | 0.669 ns | yes |
| dotted f64 | 0.443 ns | 0.667 ns | 0.894 ns | yes |

Game logic (`bench/game/swarm`: 3000 agents flocking, a spatial hash, shooting, events, respawning, sorting, strings; no window), milliseconds per frame. The C version (`swarm.c`) is what a C programmer would write (buffers reused, its own random numbers):

| C -O2 | Jot release | Jot debug | release / C |
|---|---|---|---|
| 2.61 ms | 5.02 ms | 12.01 ms | 1.92x |

## 6. CPU parallelism

`parallel_map` over 1M Collatz lengths on 8 hardware threads: **4.6x** faster than `map` (results identical: true).

## 7. Native executables are static

- hello world: 8816 bytes; no program interpreter and no shared library dependencies: **yes**
- 3D game (dunes): 650 KB; static: **yes** (the GPU driver is loaded at run time if present; without one it renders in software, see section 10)
- the compiler writes machine code and ELF files itself: no assembler, linker or C toolchain is used

## 8. Web builds

- lumen: single file `lumen.html`, 438 KB, external references: 0; opened from file:// in headless Chrome: 1424 distinct colors in the frame, **renders**
- dunes: single file `dunes.html`, 465 KB, external references: 0; opened from file:// in headless Chrome: 3670 distinct colors in the frame, **renders**

## 9. Games (native, OpenGL ES 3)

| game | mode | frame CPU time (update + draw + submit) | pixels, how frames reach the screen | screenshot |
|---|---|---|---|---|
| lumen | debug | 1.92 ms | 2133x1200 pixels, wayland+libdecor dma-buf, scale 1.667 | 1938 colors |
| lumen | release | 1.56 ms | 2133x1200 pixels, wayland+libdecor dma-buf, scale 1.667 | 1938 colors |
| dunes | debug | 1.82 ms | 2133x1200 pixels, wayland+libdecor dma-buf, scale 1.667 | 7678 colors |
| dunes | release | 3.02 ms | 2133x1200 pixels, wayland+libdecor dma-buf, scale 1.667 | 7678 colors |

## 10. Without a GPU driver (software renderer)

With no OpenGL ES driver (or `JOT_SOFTWARE=1`) the same binaries draw with a multithreaded software renderer that runs the Jot shader functions on the CPU, at half resolution. Without libX11 it speaks the X11 protocol itself, and screenshot runs need no display at all. Below, frame 60 of each game rendered with no display and no GPU, compared with the GPU's frame:

| game | software frame CPU time | mean abs difference vs GPU frame (0-255) |
|---|---|---|
| cube | 3.27 ms | 0.56 |
| lumen | 18.65 ms | 1.28 |
| dunes | 65.65 ms | 1.13 |

