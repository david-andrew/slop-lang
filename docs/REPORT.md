# Jot requirements report

Generated 2026-10-07 21:16 on x86_64 Linux (8 hardware threads). Load average at start: 9.2. Times are best-of-N CPU times (user + sys) unless noted; instruction counts are exact.

## 1. Self-hosting

- C bootstrap -> jot1 -> jot2 -> jot3, jot2 == jot3 byte for byte: **yes**
- compiler: 14003 lines of Jot; standard library: 7805 lines of Jot
- `bin/jot` size: 1864 KB, built by itself in release mode

## 2. Tests

| mode | result |
|---|---|
| native, debug | 25 passed, 0 failed |
| native, release | 25 passed, 0 failed |
| web (wasm under node), debug | 24 passed, 0 failed |
| web (wasm under node), release | 24 passed, 0 failed |
| C bootstrap compiler | 13 passed, 0 failed |

## 3. Compile speed

Generated program `bench/big.jot`: 50009 lines (2000 functions, loops, structs, strings, floats), and the equivalent C program `bench/big.c` (66012 lines).

| compiler | CPU time | lines / second | instructions |
|---|---|---|---|
| jot (debug build) | 0.320 s | 156,278 | 1.39 G |
| jot (release build) | 0.830 s | 60,252 | 3.76 G |
| tcc | 0.060 s | 1,100,200 | 0.29 G |
| gcc -O0 | 7.940 s | 8,314 | |

Release builds take 2.6x the time of debug builds (requirement: at most 10x).

## 4. Script workflow (`jot file.jot`: compile + run)

| program | lines | compile + run (wall) |
|---|---|---|
| hello world | 1 | 19 ms |
| examples/lumen/lumen.jot (compile only) | 452 | 77 ms |
| examples/dunes/dunes.jot (compile only) | 430 | 77 ms |

## 5. Runtime performance vs C

Each benchmark exists as Jot and as equivalent C (`bench/rt`). Ratios are Jot time / C time (lower is better).

| benchmark | C -O2 | C -O0 | Jot release | Jot debug | release / C -O2 |
|---|---|---|---|---|---|
| fannkuch | 0.22 s | 0.48 s | 0.49 s | 1.79 s | 2.23x |
| mandel | 0.21 s | 0.42 s | 0.26 s | 0.30 s | 1.24x |
| nbody | 0.51 s | 2.18 s | 0.87 s | 4.27 s | 1.71x |
| sieve | 0.14 s | 0.31 s | 0.21 s | 0.45 s | 1.50x |
| spectral | 0.18 s | 0.66 s | 0.39 s | 1.70 s | 2.17x |

Geometric mean, Jot release / C -O2: **1.73x**.

## 6. CPU parallelism

`parallel_map` over 1M Collatz lengths on 8 hardware threads: **3.4x** faster than `map` (results identical: true).

## 7. Native executables are static

- hello world: 8816 bytes; no program interpreter and no shared library dependencies: **yes**
- 3D game (dunes): 519 KB; static: **yes** (the GPU driver is loaded at run time if present; without one it renders in software, see section 10)
- the compiler writes machine code and ELF files itself: no assembler, linker or C toolchain is used

## 8. Web builds

- lumen: single file `lumen.html`, 414 KB, external references: 0; opened from file:// in headless Chrome: 1430 distinct colors in the frame, **renders**
- dunes: single file `dunes.html`, 415 KB, external references: 0; opened from file:// in headless Chrome: 3518 distinct colors in the frame, **renders**

## 9. Games (native, OpenGL ES 3)

| game | mode | frame CPU time (update + draw + submit) | screenshot |
|---|---|---|---|
| lumen | debug | 2.35 ms | 1407 colors |
| lumen | release | 2.76 ms | 1407 colors |
| dunes | debug | 2.29 ms | 4297 colors |
| dunes | release | 1.91 ms | 4297 colors |

## 10. Without a GPU driver (software renderer)

With no OpenGL ES driver (or `JOT_SOFTWARE=1`) the same binaries draw with a multithreaded software renderer that runs the Jot shader functions on the CPU, at half resolution. Without libX11 it speaks the X11 protocol itself, and screenshot runs need no display at all. Below, frame 60 of each game rendered with no display and no GPU, compared with the GPU's frame:

| game | software frame CPU time | mean abs difference vs GPU frame (0-255) |
|---|---|---|
| cube | 6.35 ms | 0.56 |
| lumen | 66.83 ms | 1.28 |
| dunes | 324.96 ms | 1.13 |

