# Jot requirements report

Generated 2026-10-07 19:06 on x86_64 Linux (8 hardware threads). Load average at start: 1.2. Times are best-of-N CPU times (user + sys) unless noted; instruction counts are exact.

## 1. Self-hosting

- (bootstrap skipped with --quick)
- compiler: 13521 lines of Jot; standard library: 5472 lines of Jot
- `bin/jot` size: 1790 KB, built by itself in release mode

## 2. Tests

| mode | result |
|---|---|
| native, debug | 18 passed, 0 failed |
| native, release | 18 passed, 0 failed |
| web (wasm under node), debug | 17 passed, 0 failed |
| web (wasm under node), release | 17 passed, 0 failed |
| C bootstrap compiler | 13 passed, 0 failed |

## 3. Compile speed

Generated program `bench/big.jot`: 50009 lines (2000 functions, loops, structs, strings, floats), and the equivalent C program `bench/big.c` (66012 lines).

| compiler | CPU time | lines / second | instructions |
|---|---|---|---|
| jot (debug build) | 0.200 s | 250,045 | 1.57 G |
| jot (release build) | 0.490 s | 102,059 | 3.74 G |
| tcc | 0.030 s | 2,200,400 | 0.29 G |
| gcc -O0 | 4.800 s | 13,752 | |

Release builds take 2.4x the time of debug builds (requirement: at most 10x).

## 4. Script workflow (`jot file.jot`: compile + run)

| program | lines | compile + run (wall) |
|---|---|---|
| hello world | 1 | 9 ms |
| examples/lumen/lumen.jot (compile only) | 314 | 30 ms |
| examples/dunes/dunes.jot (compile only) | 267 | 32 ms |

## 5. Runtime performance vs C

Each benchmark exists as Jot and as equivalent C (`bench/rt`). Ratios are Jot time / C time (lower is better).

| benchmark | C -O2 | C -O0 | Jot release | Jot debug | release / C -O2 |
|---|---|---|---|---|---|
| fannkuch | 0.17 s | 0.39 s | 0.34 s | 1.06 s | 2.00x |
| mandel | 0.21 s | 0.38 s | 0.22 s | 0.22 s | 1.05x |
| nbody | 0.35 s | 1.36 s | 0.53 s | 2.51 s | 1.51x |
| sieve | 0.12 s | 0.27 s | 0.14 s | 0.34 s | 1.17x |
| spectral | 0.10 s | 0.39 s | 0.19 s | 1.14 s | 1.90x |

Geometric mean, Jot release / C -O2: **1.48x**.

## 6. CPU parallelism

`parallel_map` over 1M Collatz lengths on 8 hardware threads: **4.1x** faster than `map` (results identical: true).

## 7. Native executables are static

- hello world: 8816 bytes; no program interpreter and no shared library dependencies: **yes**
- 3D game (dunes): 333 KB; static: **yes** (the GPU driver is loaded at run time if present; without one the program reports it and exits cleanly)
- the compiler writes machine code and ELF files itself: no assembler, linker or C toolchain is used

## 8. Web builds

- lumen: single file `lumen.html`, 338 KB, external references: 0
- dunes: single file `dunes.html`, 343 KB, external references: 0

## 9. Games (native, OpenGL ES 3)

| game | mode | frame CPU time (update + draw + submit) | screenshot |
|---|---|---|---|
| lumen | debug | 0.57 ms | 1277 colors |
| lumen | release | 0.42 ms | 1277 colors |
| dunes | debug | 1.03 ms | 1566 colors |
| dunes | release | 1.00 ms | 1564 colors |

