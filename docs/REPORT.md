# Jot requirements report

Generated 2026-10-07 18:52 on x86_64 Linux (8 hardware threads). Load average at start: 1.7. Times are best-of-N CPU times (user + sys) unless noted; instruction counts are exact.

## 1. Self-hosting

- C bootstrap -> jot1 -> jot2 -> jot3, jot2 == jot3 byte for byte: **yes**
- compiler: 13141 lines of Jot; standard library: 5472 lines of Jot
- `bin/jot` size: 1842 KB, built by itself in release mode

## 2. Tests

| mode | result |
|---|---|
| native, debug | 16 passed, 0 failed |
| native, release | 16 passed, 0 failed |
| web (wasm under node), debug | 15 passed, 0 failed |
| web (wasm under node), release | 15 passed, 0 failed |
| C bootstrap compiler | 11 passed, 0 failed |

## 3. Compile speed

Generated program `bench/big.jot`: 50009 lines (2000 functions, loops, structs, strings, floats), and the equivalent C program `bench/big.c` (66012 lines).

| compiler | CPU time | lines / second | instructions |
|---|---|---|---|
| jot (debug build) | 0.220 s | 227,314 | 1.64 G |
| jot (release build) | 0.500 s | 100,018 | 3.76 G |
| tcc | 0.040 s | 1,650,300 | 0.29 G |
| gcc -O0 | 4.950 s | 13,336 | |

Release builds take 2.3x the time of debug builds (requirement: at most 10x).

## 4. Script workflow (`jot file.jot`: compile + run)

| program | lines | compile + run (wall) |
|---|---|---|
| hello world | 1 | 10 ms |
| examples/lumen/lumen.jot (compile only) | 314 | 32 ms |
| examples/dunes/dunes.jot (compile only) | 267 | 32 ms |

## 5. Runtime performance vs C

Each benchmark exists as Jot and as equivalent C (`bench/rt`). Ratios are Jot time / C time (lower is better).

| benchmark | C -O2 | C -O0 | Jot release | Jot debug | release / C -O2 |
|---|---|---|---|---|---|
| fannkuch | 0.18 s | 0.40 s | 0.73 s | 1.08 s | 4.06x |
| mandel | 0.21 s | 0.38 s | 0.24 s | 0.23 s | 1.14x |
| nbody | 0.36 s | 1.39 s | 0.68 s | 2.45 s | 1.89x |
| sieve | 0.12 s | 0.27 s | 0.16 s | 0.33 s | 1.33x |
| spectral | 0.10 s | 0.40 s | 0.32 s | 1.11 s | 3.20x |

Geometric mean, Jot release / C -O2: **2.06x**.

## 6. CPU parallelism

`parallel_map` over 1M Collatz lengths on 8 hardware threads: **4.3x** faster than `map` (results identical: true).

## 7. Native executables are static

- hello world: 8816 bytes; no program interpreter and no shared library dependencies: **yes**
- 3D game (dunes): 335 KB; static: **yes** (the GPU driver is loaded at run time if present; without one the program reports it and exits cleanly)
- the compiler writes machine code and ELF files itself: no assembler, linker or C toolchain is used

## 8. Web builds

- lumen: single file `lumen.html`, 338 KB, external references: 0; opened from file:// in headless Chrome: 1277 distinct colors in the frame, **renders**
- dunes: single file `dunes.html`, 343 KB, external references: 0; opened from file:// in headless Chrome: 3439 distinct colors in the frame, **renders**

## 9. Games (native, OpenGL ES 3)

| game | mode | frame CPU time (update + draw + submit) | screenshot |
|---|---|---|---|
| lumen | debug | 1.66 ms | 1325 colors |
| lumen | release | 1.71 ms | 1280 colors |
| dunes | debug | 2.69 ms | 1569 colors |
| dunes | release | 2.98 ms | 1567 colors |

