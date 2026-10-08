# The Jot Programming Language

Jot is a small, statically typed, compiled language that feels like a scripting
language. `jot game.jot` compiles the whole program (in milliseconds) and runs it.

Design goals, in priority order:

1. **Instant compiles.** Whole-program compilation every time, no incremental builds,
   no external toolchain. The compiler emits x86-64 machine code / WebAssembly directly.
2. **Python-level ease.** Type inference everywhere, minimal ceremony, top-level
   statements are a program, no build system, batteries included for games.
3. **Predictable performance.** Values are plain data laid out like C. No GC, no hidden
   allocations behind your back, no virtual dispatch you did not ask for.
4. **Programs keep working.** Native executables are fully static (they make Linux
   syscalls directly), web builds are a single self-contained `.html` file.

---

## 1. A taste

```jot
# hello.jot
print("hello, world")

fib = (n: int) -> int:
    if n < 2: return n
    fib(n - 1) + fib(n - 2)

loop i in [0..10):
    print("fib({i}) = {fib(i)}")

nums = [5 3 9 1]
nums.sort()
squares = nums.map((x): x * x)
add = (a: int, b: int): a + b
inc = add(1, _)                # partial application
print(squares, inc(41))
print(nums .* 2, sqrt.([4.0 9.0]))     # elementwise
```

## 2. Lexical structure

* Comments start with `#` and run to end of line.
* Blocks are introduced by `:` and are either the rest of the line
  (`if x: return 1`) or an indented block on the following lines.
  Inside brackets newlines are ignored (except in array literals, where they separate rows),
  and a `:` at the end of a line opens an indented block (this is how multi-line lambdas work).
* `;` may separate statements on one line.
* Integer literals: `42`, `1_000_000`, `0xff`, `0b1010`. Float literals: `1.5`, `2.0e-3`.
  Literals take the type their context expects.
* Strings: `"text {expr} more {value:.2}"` and `'the same'` — the two quotes are
  interchangeable, and both may span lines. `{}` interpolates any expression, `{{` and `}}`
  are literal braces. Escapes: `\n \t \r \0 \\ \" \' \xNN`. Format specs follow Python:
  `[[fill]align][+][0][width][,][.precision][type]` with align `<` `>` `^` and type `x` `X`
  `b` `o` `f` `%` — `{price:>8.2}`, `{n:,}`, `{ratio:.1%}`, `{name:<12}`, `{bits:08b}`.
  Raw strings `r"no {interp} \here"`. Triple quoted `"""docstrings"""` are dedented.
* **Characters.** A one-character string where an integer is expected stands for its
  character code: `c == 'a'`, `'0'..'9'` in a match, `u8('A')`.
* **Units.** A unit right after a number (no space) converts to the SI base unit at compile
  time: `120ms` is `0.12`, `90deg` is `PI / 2`, `3km` is `3000.0`, `1.2(m/s)`,
  `9.81(m/s^2)`, `[1.2 0](m/s)`. Time `s ms us ns min h`, length `m cm mm km`, mass `kg g`,
  angle `rad deg turn`, force `N`, and long names (`10seconds`, `3meters`). Values are plain
  `f64`s (no dimension checking).

Keywords: `struct enum type if else loop in break continue return match use as const true false
none null and or xor not is let mut when defer extern test build pass` (`loop let xor is` and
`type` may still be used as field and variant names).

## 3. Variables and constants

```jot
x = 10               # declares x (there is no x yet), type inferred (int)
x = x + 1            # assigns (x exists)
let x = "text"       # always a new variable (shadows the outer x)
y: f32 = 2           # explicit type (always declares)
z: str[]             # zero value: empty array
x += 1               # compound assignment (also -= *= /= %= ^= <<= >>= and= or= xor=)
a, b = 1, 2          # several at once
const SPEED = 300.0  # compile-time constant
```

`x = value` declares `x` when no variable `x` is visible, and assigns otherwise: inside a
function, assigning to a global changes the global. At the top level of a file, `x = 1`
declares a global of that file (even if an imported file has an `x`).

Top-level variables are globals, initialized in order before `main` runs.
Top-level statements in the main file run in order, like a script.

## 4. Types

| Type | Meaning |
|---|---|
| `int` | 64-bit signed integer (`i8 i16 i32 i64 u8 u16 u32 u64` also exist, `byte` = `u8`) |
| `f64` `f32` | floats (`1.5` is an `f64` unless the context wants an `f32`) |
| `bool` | `true` / `false` |
| `str` | immutable UTF-8 string (`+` concatenates, `*` repeats) |
| `T[]` | growable array (value semantics); `push pop insert remove extend len` ... (also `Array[T]`) |
| `T[,]` | 2-D array (see section 8) |
| `soa T[]` | array of structs stored as one array per field (see section 8) |
| `{K: V}` | hash map, insertion ordered (value semantics) |
| `(A, B)` | tuple |
| `T?` | optional: a `T` or `none` (the same as `T \| none`) |
| `A \| B` | union: an `A` or a `B` (see section 7) |
| `(A, B) -> R` | function value (may be a closure); `() -> void` returns nothing |
| `vec2 vec3 vec4 mat4` | f32 vector/matrix math types (GPU-compatible) |
| `*T` | raw pointer (low-level code only) |

`type Name = ...` names a type: `type Shape = Circle | Rect`, `type Result[T, E] = T | E`.

**Numeric conversions.** Integers widen implicitly to larger integer types of the same
signedness and to floats; `f32` and `f64` convert implicitly in both directions.
Narrowing is explicit: `int(3.7)`, `u8(x)`, `f32(x)`. `as` reinterprets bits/pointers.
Float to integer conversion truncates toward zero and saturates: NaN becomes 0 and values
beyond the integer range become its minimum or maximum (the same on every target).

**Operators.** Integer `/` truncates, `%` is remainder, integer overflow wraps. `x ^ y` is
`pow(x, y)` (right-associative and tighter than unary minus: `-2 ^ 2 == -4`).
`and or xor not` are logical on bools (`and`/`or` short-circuit) and bitwise on integers,
with low precedence (below comparisons); `& | ~ << >>` are the bitwise operators with high
precedence, so `flags & MASK == 0` is `(flags & MASK) == 0`. `x in xs` tests membership
(`x in 1..10` compares, no array is made). `a ?? b` is `a` unless it is `none`.

### Value semantics

Every type in Jot is a *value*: assignment copies. Arrays, strings and maps are
reference counted with copy-on-write, so copies are O(1) and a real copy only
happens when you mutate something that is shared. There are no reference types,
so reference cycles (and leaks) are impossible, and there is no garbage collector.

```jot
a = [1, 2, 3]
b = a           # O(1), shares storage
b.push(4)       # b is shared, so b gets its own copy here
print(a, b)     # [1, 2, 3] [1, 2, 3, 4]
```

Function parameters are borrowed (passed without copying, read-only).
Mark a parameter `mut` to let the function modify the caller's variable:

```jot
grow = (xs: mut int[]): xs.push(0)
grow(nums)
```

To modify array elements in a loop, use `loop mut`:

```jot
loop mut p in particles:
    p.pos += p.vel * dt
```

## 5. Functions

```jot
area = (w: f64, h: f64) -> f64: w * h            # the last expression is the result
clamp01 = (x: f64, lo: f64 = 0, hi: f64 = 1) -> f64:
    if x < lo: return lo
    if x > hi: return hi
    x
area(2, 3); area(h = 3, w = 2)                   # named arguments
```

A parenthesized parameter list followed by `->` or `:` is a function; the same syntax
written inside an expression is a lambda.

* The return type may be omitted; it is inferred from the body (recursive functions
  must declare it). `-> void` says explicitly that nothing is returned.
* **Untyped parameters make a function generic**: `twice = (f, x): f(f(x))` is
  instantiated for each distinct set of argument types (like a template).
* Explicit type parameters: `first[T] = (xs: T[]) -> T: xs[0]`.
* **Uniform call syntax**: `x.f(a)` is the same as `f(x, a)`. There are no methods,
  only functions; any function can be called with dot syntax on its first argument.
* Functions may be **overloaded** by parameter types. A program's own definitions take
  precedence over standard-library functions with the same signature.
* **Operators** can be overloaded: `(+) = (a: Money, b: Money) -> Money: ...`, also
  `([])` and `([]=)` for indexing.

### Functions as values, closures, partial application

```jot
double = (x: int): x * 2
nums.map(double)
nums.map((x): x * 2)            # parameter types inferred from context
nums.each((x):
    print(x)
    print(x * x)
)
scale = (k: f64, x: f64): k * x
half = scale(0.5, _)            # partial application: `_` marks missing arguments
print(half(10))                 # 5
```

**Closures capture variables, not values**, the same way everywhere: a closure made inside a
function sees (and can change) that function's variables, just as a closure at the top level
sees and changes globals.

```jot
make_counter = () -> () -> int:
    n = 0
    ():
        n += 1
        n
c = make_counter()
c(); c()
print(c())                      # 3
```

(A variable that is never changed after a closure captures it is simply copied into the
closure; one that is changed lives in a small shared heap cell. A loop body gets fresh
variables on every iteration, so closures made in a loop each see their own.)

## 6. Control flow

```jot
if a > b: print("a") else if a == b: print("eq") else: print("b")
m = if a > b: a else: b                # if is an expression
if let v = lookup(key): print(v)       # bind the value of an optional when present

loop: ...                              # forever (until break / return)
loop x > 0: x -= 1                     # while
loop i in [0..10): ...                 # 0 to 9
loop i in 0..10: ...                   # 0 to 10: a bare range includes both ends
loop i in 0,2..10: ...                 # 0 2 4 6 8 10
loop i in 10,9..1: ...                 # counting down
loop x in xs: ...
loop k, v in table: ...                # unpacks: map entries, or an array of pairs
loop mut x in xs: x *= 2               # x is the element itself
loop let job = queue.next(): ...       # while the optional has a value
break / continue / return
defer close(f)                         # runs when the enclosing block exits
```

**Ranges.** `a..b` includes both ends. Brackets choose: `[a..b]` both, `[a..b)` without `b`,
`(a..b]` without `a`, `(a..b)` neither. `a..` is open (counting up forever). `[a, b..c]`
(or `a,b..c` after `in`) steps by `b - a`. A range used as a value is the array of its numbers:
`[0, 3..9]` is `[0, 3, 6, 9]`. In index brackets: `xs[2..5)`, `xs[2..]`, `xs[..3)`, `xs[end]`
(the last element), `xs[1..end-1]`.

**Combined loops.** Bindings and conditions join with `and` / `or` in one loop header:

```jot
loop i in 0.. and v in values: ...             # counts alongside: stops when values runs out
loop i in 0.. and v in values and v ^ 2 < limit: ...   # also stops at the first false condition
loop a in xs or b in ys: ...                   # until both run out; a finished one gives none
loop (a in xs or b in ys) and ok(): ...
```

Iterators joined with `and` advance together until one runs out; joined with `or` they advance
until all have run out (the variables of finished ones are `none`, so they are optionals).
`loop i, x in xs` does not count: two names before `in` always unpack.

**Comprehensions** are a loop inside brackets; `if` filters, nested loops flatten:

```jot
squares = [loop i in [1..5]: i ^ 2]
evens = [loop n in [0..10): if n % 2 == 0: n]
pairs = [loop i in [0..3): loop j in [0..3): (i, j)]
```

**Match:**

```jot
match value:
    0: print("zero")
    1, 2: print("small")
    3..9: print("medium")
    'a'..'z': print("a letter code")
    _: print("big")
```

## 7. Structs, unions, enums, optionals, tuples

```jot
struct Player:
    name: str
    pos: vec2
    hp = 100                   # field with a default

p = Player("ann", vec2(0, 0))
q = Player(name = "bob", pos = vec2(1, 2), hp = 50)
p.pos.x += 1

struct Stack[T]:               # generic struct
    items: T[]

enum Dir: north, east, south, west     # simple enum
d = Dir.north
if d == .north: ...                     # `.name` when the type is known
```

**Unions** hold a value of one of several types. `is` tests which, and a variable that has
been tested *is* that type where the test holds — in the `if`, after an `if` that returns or
breaks, on the right of `and`, and in `match` arms:

```jot
struct Circle: r: f64
struct Rect: w: f64; h: f64
type Shape = Circle | Rect

area = (s: Shape) -> f64:
    if s is Circle: return PI * s.r ^ 2
    s.w * s.h                           # s is a Rect here

describe = (v: int | str) -> str:
    match v:
        int: "the number {v + 1}"
        str: "the text {v}"

parse_int = (s: str) -> int | ParseError: ...
r = parse_int(text)
if r is ParseError: return r
print(r + 1)                            # r is an int
```

Assigning another member to a narrowed variable makes it the whole union again. A union
value prints as the value it holds. `T | none` is `T?`.

**Optionals:**

```jot
best: int? = none
if let v = lookup(key): print(v)        # bind when present
if best is int: print(best + 1)         # `is` works on optionals too
n = lookup(key) ?? 0                    # default
k = lookup(key)!                        # unwrap or panic
```

**Tuples:**

```jot
pair = (1, "one")
a, b = pair
print(pair.0)
```

(Enums whose variants carry fields, `enum Shape: circle(r: f64), rect(w: f64, h: f64)`, also
exist; unions are usually simpler.)

## 8. Arrays for numeric work

Inside array brackets elements are separated by spaces or commas: `[1 2 3]`, `[a, b]`.
(There, `[a -b]` has two elements and `[a - b]` one, as in MATLAB, and `f(x)` / `xs[i]` are
written without a space before `(` / `[`.) `[xs... 4 5]` spreads an array into a literal and
`fill(x, n)` repeats a value.

**Elementwise operations.** The dotted operators `.+ .- .* ./ .% .^ .== .!= .< .<= .> .>=`
apply element by element, and `f.(xs)` applies any function to each element. Arrays of
different shapes broadcast like numpy: a scalar, or a dimension of length 1, stretches to fit.
A whole dotted expression runs as one loop, without temporary arrays:

```jot
xs = linspace(0, 1, 5)
ys = 3.0 .* xs .^ 2 .+ 1.0       # one loop
mask = xs .> 0.5                 # bool[]
roots = sqrt.(xs)
```

(Plain `+` on 1-D arrays concatenates, as for lists.)

**2-D arrays** (`T[,]`): rows are separated by `;` or line breaks.

```jot
m = [1.0 2.0; 3.0 4.0]
grid = [0 1 0
        1 1 1]
rows = [a; b]                    # stack arrays a and b as rows
print(m[1, 0], shape(m), m.rows, m.cols)
m[0, 1] = 5.0
v = m * [1.0, 1.0]               # matrix times vector
p = m * transpose(m)             # matrix product
k = m .* 2.0 .+ [10.0 20.0]      # broadcasting a row
```

`zeros(n)`, `zeros(r, c)`, `ones`, `eye(n)`, `rand(n)` / `rand(r, c)` (uniform in [0, 1)),
`randn` (normal), `linspace(a, b, n)`, `reshape(xs, r, c)`, `transpose`, `row(m, i)`,
`col(m, j)`, `flatten`, `sum`, `mean`, `dot`, `norm`. On 2-D arrays `+ -` work elementwise on
equal shapes and `*` is the matrix product.

**Struct-of-arrays.** `ps: soa Particle[]` behaves like `Particle[]` — `push`, `pop`,
`remove`, `len`, `ps[i]`, `ps[i].x += 1`, `loop p in ps`, conversion from `Particle[]` — but
keeps each field in an array of its own, so code that looks at one field reads only that
field's memory. `ps.x` is the whole field array:

```jot
ps: soa Particle[] = make_particles()
ps.x = ps.x .+ ps.vx .* dt
```

**GPU arrays.** `gpu(xs)` copies an array to GPU memory and `cpu(g)` copies it back. A dotted
expression whose arrays are GPU arrays runs on the GPU as one fragment program, generated from
the expression at compile time — functions applied with `f.(g)` are translated to GLSL like
shader functions, and the numbers in the expression become uniforms:

```jot
g = gpu(rand(4_000_000))
h = wave.(g) .* 0.5 .+ g          # one GPU program
ys = cpu(h)
```

Values on the GPU are `f32`, and arrays in one expression must have the same length. GPU
memory is reused automatically once no copy of a GPU array is left. Where there is no GPU (no
OpenGL ES driver, `JOT_SOFTWARE=1`, or a web build, for now) the same expressions run on the CPU,
so programs work everywhere; `gpu_available()` tells which.

## 9. Modules

`use 'util.jot'` loads a file relative to the importing file and makes its names available
directly; standard-library modules are named without quotes (`use thread`).
`import util` makes them available as `util.name` (`import util as u` renames).
The core standard library (strings, arrays, maps, math, vectors, files, numeric arrays, and
the game/graphics/audio API) is always available without importing.

## 10. Compile-time features

```jot
build:                          # build options live in the source
    target = wasm               # native (default) | wasm
    opt = release               # debug | release
    output = "mygame"

when TARGET == "wasm":          # compile-time conditional; the dead branch is not compiled
    ...
else:
    ...

logo = embed("logo.png")        # file contents baked into the program as u8[]

test "math works":
    assert(1 + 1 == 2)
```

`jot test file.jot` runs the file's top-level code, then each `test` block in order,
reporting `test name ... ok` per block; the first failing `assert` stops the run with its
message and location.

**Release builds.** `opt = release` (or `jot build --release`) inlines refcount, uniqueness
and bounds-check fast paths and runs the optimizer (constant folding, copy propagation,
common subexpressions, redundant load and bounds-check elimination). Debug builds compile
faster; both have identical behavior, including bounds checks.

Array indexing is always checked, except where the check cannot fail: in
`loop i in [0..xs.len())` (or `[0..n)` with `n = xs.len()`, or `xs = fill(v, n)` and
`[0..n)`, starting from any expression that cannot be negative) `xs[i]` has no check, as long
as the function never resizes `xs` — writing its elements is fine. So the usual index loop
costs what it would in C.

## 11. Parallelism

Data-parallel helpers run a function over many elements on all CPU cores (fork-join):

```jot
lengths = parallel_map(words, (w): expensive(w))      # [loop x in xs: f(x)]
parallel_update(particles, (p): step(p, dt))          # xs[i] = f(xs[i]) in place
rows = parallel_range(height, (y): render_row(y))     # [loop i in [0..n): f(i)]
```

The function runs on many threads at once: it may read anything, but it must not change
globals or the variables it captured (that would be a data race). Return results instead.
Web builds run the same code on one thread.

## 12. Programs and the game loop

A program runs its top-level statements, then `main()` if defined.
If the program defines `update(dt: f64)` and/or `draw()`, a window opens and they are
called every frame (this is also how programs run in the browser).

```jot
pos = vec2(100, 100)

update = (dt: f64):
    if key_down(.right): pos.x += 200 * dt

draw = ():
    clear(rgb(0.1, 0.1, 0.15))
    circle(pos, 20, rgb(1, 0.5, 0.2))
```

Native games open a Wayland window when `WAYLAND_DISPLAY` is set and an X11 window otherwise
(`JOT_PLATFORM=x11|wayland` chooses). They use the system's OpenGL ES driver when there is
one. Without it (or with `JOT_SOFTWARE=1`) the same program draws with the built-in software
renderer, which runs your shader functions (see `make_shader`) on the CPU; `soft_rendering()`
tells the program which is in use, e.g. to draw fewer particles. Frames are rendered at half
resolution (`JOT_SOFT_SCALE=1` for full resolution) and paced to 60 per second.

Environment variables for testing and tuning: `JOT_SCREENSHOT=out.png` (with `JOT_FRAMES=n`)
saves frame n and exits — the clock then advances exactly 1/60 s per frame, so the image is
reproducible, and with `JOT_SOFTWARE=1` no display is needed at all; `JOT_INPUT="5:space+,9:space-"`
presses and releases keys at given frames; `JOT_THREADS=n` caps the threads used by the
parallel functions.

```
jot file.jot [args]     compile and run (wasm target: opens the browser)
jot build file.jot      write the executable / .html
jot test file.jot       run `test` blocks
jot check file.jot      type check only
```

## 13. Calling C

Native programs can call functions from system shared libraries; the library is loaded the
first time one of its functions is called, so a missing library only matters to code that
actually uses it (check with `lib_available("libfoo.so.1")`).

```jot
@lib("libm.so.6")
extern cbrt = (x: f64) -> f64

@lib("libGLESv2.so.2")
@symbol("glClear")                 # the C name, when the Jot name differs
extern gl_clear_native = (mask: u32)
```

Arguments and results must be scalars or pointers; `cfn(...) -> T` is the type of a C function
pointer, and `@cabi` makes a Jot function callable from C.
