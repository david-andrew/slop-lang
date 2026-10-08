# Jot requirements report

Generated 2026-10-08 00:38 on x86_64 Linux (8 hardware threads). Load average at start: 3.8. Times are best-of-N CPU times (user + sys) unless noted; instruction counts are exact.

## 1. Self-hosting

- C bootstrap -> jot1 -> jot2 -> jot3, jot2 == jot3 byte for byte: **yes**
- compiler: 16532 lines of Jot; standard library: 8851 lines of Jot
- `bin/jot` size: 2212 KB, built by itself in release mode

## 2. Tests

| mode | result |
|---|---|
| native, debug | 36 passed, 0 failed |
| native, release | 36 passed, 0 failed |
| web (wasm under node), debug | 35 passed, 0 failed |
| web (wasm under node), release | 35 passed, 0 failed |
| C bootstrap compiler | 16 passed, 0 failed |
| rendering (software renderer vs references; also on the GPU when there is a display) | 14 passed, 0 failed |
| differential fuzzing: random programs built 4 ways + by the C bootstrap compiler | 60 programs, 0 mismatches (seeds 653316428..653316487) |

## 3. Compile speed

Generated program `bench/big.jot`: 50009 lines (2000 functions, loops, structs, strings, floats), and the equivalent C program `bench/big.c` (66012 lines).

| compiler | CPU time | lines / second | instructions |
|---|---|---|---|
| jot (debug build) | 0.200 s | 250,045 | 1.44 G |
| jot (release build) | 0.490 s | 102,059 | 3.81 G |
| tcc | 0.030 s | 2,200,400 | 0.29 G |
| gcc -O0 | 4.880 s | 13,527 | |

Release builds take 2.4x the time of debug builds (requirement: at most 10x).

## 4. Script workflow (`jot file.jot`: compile + run)

| program | lines | compile + run (wall) |
|---|---|---|
| hello world | 1 | 14 ms |
| examples/lumen/lumen.jot (compile only) | 452 | 51 ms |
| examples/dunes/dunes.jot (compile only) | 430 | 52 ms |

## 5. Runtime performance vs C

Each benchmark exists as Jot and as equivalent C (`bench/rt`). Ratios are Jot time / C time (lower is better).

| benchmark | C -O2 | C -O0 | Jot release | Jot debug | release / C -O2 |
|---|---|---|---|---|---|
| fannkuch | 0.17 s | 0.39 s | 0.31 s | 1.02 s | 1.82x |
| mandel | 0.21 s | 0.37 s | 0.22 s | 0.22 s | 1.05x |
| nbody | 0.35 s | 1.35 s | 0.52 s | 2.25 s | 1.49x |
| sieve | 0.11 s | 0.27 s | 0.14 s | 0.31 s | 1.27x |
| spectral | 0.09 s | 0.37 s | 0.16 s | 1.07 s | 1.78x |

Geometric mean, Jot release / C -O2: **1.45x**.

## 6. CPU parallelism

`parallel_map` over 1M Collatz lengths on 8 hardware threads: **3.3x** faster than `map` (results identical: true).

## 7. Native executables are static

- hello world: 8816 bytes; no program interpreter and no shared library dependencies: **yes**
- 3D game (dunes): 551 KB; static: **yes** (the GPU driver is loaded at run time if present; without one it renders in software, see section 10)
- the compiler writes machine code and ELF files itself: no assembler, linker or C toolchain is used

## 8. Web builds

- lumen: single file `lumen.html`, 414 KB, external references: 0; opened from file:// in headless Chrome: 1422 distinct colors in the frame, **renders**
- dunes: single file `dunes.html`, 415 KB, external references: 0; opened from file:// in headless Chrome: 3675 distinct colors in the frame, **renders**

## 9. Games (native, OpenGL ES 3)

| game | mode | frame CPU time (update + draw + submit) | screenshot |
|---|---|---|---|
| lumen | debug | 1.28 ms | 1407 colors |
| lumen | release | 1.19 ms | 1407 colors |
| dunes | debug | 1.33 ms | 4297 colors |
| dunes | release | 1.27 ms | 4297 colors |

## 10. Without a GPU driver (software renderer)

With no OpenGL ES driver (or `JOT_SOFTWARE=1`) the same binaries draw with a multithreaded software renderer that runs the Jot shader functions on the CPU, at half resolution. Without libX11 it speaks the X11 protocol itself, and screenshot runs need no display at all. Below, frame 60 of each game rendered with no display and no GPU, compared with the GPU's frame:

| game | software frame CPU time | mean abs difference vs GPU frame (0-255) |
|---|---|---|
| cube | 3.84 ms | 0.56 |
| lumen | 26.01 ms | 1.28 |
| dunes | 128.32 ms | 1.13 |

