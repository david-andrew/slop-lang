# Jot requirements report

Generated 2026-10-07 19:30 on x86_64 Linux (8 hardware threads). Load average at start: 1.5. Times are best-of-N CPU times (user + sys) unless noted; instruction counts are exact.

## 1. Self-hosting

- C bootstrap -> jot1 -> jot2 -> jot3, jot2 == jot3 byte for byte: **yes**
- compiler: 13523 lines of Jot; standard library: 5952 lines of Jot
- `bin/jot` size: 1829 KB, built by itself in release mode

## 2. Tests

| mode | result |
|---|---|
| native, debug | 20 passed, 0 failed |
| native, release | 20 passed, 0 failed |
| web (wasm under node), debug | 19 passed, 0 failed |
| web (wasm under node), release | 19 passed, 0 failed |
| C bootstrap compiler | 13 passed, 0 failed |

## 3. Compile speed

Generated program `bench/big.jot`: 50009 lines (2000 functions, loops, structs, strings, floats), and the equivalent C program `bench/big.c` (66012 lines).

| compiler | CPU time | lines / second | instructions |
|---|---|---|---|
| jot (debug build) | 0.220 s | 227,314 | 1.59 G |
| jot (release build) | 0.510 s | 98,057 | 3.79 G |
| tcc | 0.040 s | 1,650,300 | 0.29 G |
| gcc -O0 | 5.150 s | 12,818 | |

Release builds take 2.3x the time of debug builds (requirement: at most 10x).

## 4. Script workflow (`jot file.jot`: compile + run)

| program | lines | compile + run (wall) |
|---|---|---|
| hello world | 1 | 10 ms |
| examples/lumen/lumen.jot (compile only) | 452 | 36 ms |
| examples/dunes/dunes.jot (compile only) | 427 | 36 ms |

## 5. Runtime performance vs C

Each benchmark exists as Jot and as equivalent C (`bench/rt`). Ratios are Jot time / C time (lower is better).

| benchmark | C -O2 | C -O0 | Jot release | Jot debug | release / C -O2 |
|---|---|---|---|---|---|
| fannkuch | 0.17 s | 0.39 s | 0.35 s | 1.06 s | 2.06x |
| mandel | 0.21 s | 0.38 s | 0.22 s | 0.22 s | 1.05x |
| nbody | 0.36 s | 1.38 s | 0.52 s | 2.51 s | 1.44x |
| sieve | 0.12 s | 0.28 s | 0.15 s | 0.36 s | 1.25x |
| spectral | 0.10 s | 0.38 s | 0.19 s | 1.16 s | 1.90x |

Geometric mean, Jot release / C -O2: **1.49x**.

## 6. CPU parallelism

`parallel_map` over 1M Collatz lengths on 8 hardware threads: **4.1x** faster than `map` (results identical: true).

## 7. Native executables are static

- hello world: 8816 bytes; no program interpreter and no shared library dependencies: **yes**
- 3D game (dunes): 376 KB; static: **yes** (the GPU driver is loaded at run time if present; without one the program reports it and exits cleanly)
- the compiler writes machine code and ELF files itself: no assembler, linker or C toolchain is used

## 8. Web builds

- lumen: single file `lumen.html`, 385 KB, external references: 0; opened from file:// in headless Chrome: 1422 distinct colors in the frame, **renders**
- dunes: single file `dunes.html`, 382 KB, external references: 0; opened from file:// in headless Chrome: 3875 distinct colors in the frame, **renders**

## 9. Games (native, OpenGL ES 3)

| game | mode | frame CPU time (update + draw + submit) | screenshot |
|---|---|---|---|
| lumen | debug | 1.70 ms | 1424 colors |
| lumen | release | 1.42 ms | 1428 colors |
| dunes | debug | 1.64 ms | 4300 colors |
| dunes | release | 1.49 ms | 4295 colors |

