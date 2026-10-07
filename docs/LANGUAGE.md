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

fn fib(n: int) -> int:
    if n < 2: return n
    fib(n - 1) + fib(n - 2)

for i in 0..10:
    print("fib({i}) = {fib(i)}")

nums := [5, 3, 9, 1]
nums.sort()
squares := nums.map(fn(x): x * x)
add := fn(a: int, b: int): a + b
inc := add(1, _)               # partial application
print(squares, inc(41))
```

## 2. Lexical structure

* Comments start with `#` and run to end of line.
* Blocks are introduced by `:` and are either the rest of the line
  (`if x: return 1`) or an indented block on the following lines.
  Inside brackets newlines are ignored, except that a `:` at the end of a line
  opens an indented block (this is how multi-line lambdas work).
* `;` may separate statements on one line.
* Integer literals: `42`, `1_000_000`, `0xff`, `0b1010`, `'a'` (character code).
* Float literals: `1.5`, `2.0e-3`. Literals take the type their context expects.
* Strings: `"text {expr} more {value:.2}"` — `{}` interpolates any expression,
  `{{` and `}}` are literal braces. Escapes: `\n \t \r \0 \\ \" \' \xNN`.
  Raw strings `r"no {interp} \here"`. Triple quoted `"""multi-line"""` strings.

Keywords: `fn struct enum if else for in while break continue return match
import as const true false none null and or not mut when defer extern test build`.

## 3. Variables and constants

```jot
x := 10              # new variable, type inferred (int)
y: f32 = 2           # explicit type
z: [str]             # zero value: empty array
x = x + 1            # assignment
x += 1               # compound assignment
const SPEED = 300.0  # compile-time constant
```

Top-level variables are globals, initialized in order before `main` runs.
Top-level statements in the main file run in order, like a script.

## 4. Types

| Type | Meaning |
|---|---|
| `int` | 64-bit signed integer (`i8 i16 i32 i64 u8 u16 u32 u64` also exist, `byte` = `u8`) |
| `float` | 64-bit float (`f32`, `f64` also exist) |
| `bool` | `true` / `false` |
| `str` | immutable UTF-8 string (`+` concatenates, `*` repeats) |
| `[T]` | growable array (value semantics) |
| `{K: V}` | hash map, insertion ordered (value semantics) |
| `(A, B)` | tuple |
| `T?` | optional: a `T` or `none` |
| `fn(A, B) -> R` | function value (may be a closure) |
| `vec2 vec3 vec4 mat4` | f32 vector/matrix math types (GPU-compatible) |
| `*T` | raw pointer (low-level code only) |

**Numeric conversions.** Integers widen implicitly to larger integer types of the same
signedness and to floats; `f32` and `f64` convert implicitly in both directions.
Narrowing is explicit: `int(3.7)`, `u8(x)`, `f32(x)`. `as` reinterprets bits/pointers.

Integer `/` truncates, `%` is remainder. Integer overflow wraps.

### Value semantics

Every type in Jot is a *value*: assignment copies. Arrays, strings and maps are
reference counted with copy-on-write, so copies are O(1) and a real copy only
happens when you mutate something that is shared. There are no reference types,
so reference cycles (and leaks) are impossible, and there is no garbage collector.

```jot
a := [1, 2, 3]
b := a          # O(1), shares storage
b.push(4)       # b is shared, so b gets its own copy here
print(a, b)     # [1, 2, 3] [1, 2, 3, 4]
```

Function parameters are borrowed (passed without copying, read-only).
Mark a parameter `mut` to let the function modify the caller's variable:

```jot
fn grow(xs: mut [int]): xs.push(0)
grow(nums)
```

To mutate array elements in a loop, use `for mut`:

```jot
for mut p in particles:
    p.pos += p.vel * dt
```

## 5. Functions

```jot
fn area(w: float, h: float) -> float: w * h     # last expression is the result
fn clamp01(x: float, lo: float = 0, hi: float = 1) -> float:
    if x < lo: return lo
    if x > hi: return hi
    x
area(2, 3); area(h = 3, w = 2)                   # named arguments
```

* The return type may be omitted; it is inferred from the body (recursive functions
  must declare it).
* **Untyped parameters make a function generic**: `fn twice(f, x): f(f(x))` is
  instantiated for each distinct set of argument types (like a template).
* Explicit generics: `fn first[T](xs: [T]) -> T: xs[0]`.
* **Uniform call syntax**: `x.f(a)` is the same as `f(x, a)`. There are no methods,
  only functions; any function can be called with dot syntax on its first argument.
* Functions may be **overloaded** by parameter types. A program's own definitions take
  precedence over standard-library functions with the same signature.
* **Operators** can be overloaded by defining `fn +(a: T, b: T) -> T`.

### Functions as values, closures, partial application

```jot
double := fn(x: int): x * 2
nums.map(double)
nums.map(fn(x): x * 2)          # parameter types inferred from context
nums.each(fn(x):
    print(x)
    print(x * x)
)
scale := fn(k: float, x: float): k * x
half := scale(0.5, _)           # partial application: `_` marks missing arguments
print(half(10))                 # 5
```

Closures capture local variables **by value** at creation time; captured values are
read-only. Globals are not captured: a closure sees their current value.

## 6. Control flow

```jot
if a > b: print("a") else if a == b: print("eq") else: print("b")
m := if a > b: a else: b               # if is an expression

while x > 0: x -= 1
for i in 0..10: ...                    # 0 to 9
for i in 0..=10: ...                   # 0 to 10
for x in xs: ...
for i, x in xs: ...                    # with index
for k, v in map: ...
for mut x in xs: x *= 2                # x aliases the element
break / continue / return
defer close(f)                         # runs when the enclosing block exits

match value:
    0: print("zero")
    1, 2: print("small")
    3..10: print("medium")
    _: print("big")
```

## 7. Structs, enums, optionals, tuples

```jot
struct Player:
    name: str
    pos: vec2
    hp := 100                  # field with default

p := Player("ann", vec2(0, 0))
q := Player(name = "bob", pos = vec2(1, 2), hp = 50)
p.pos.x += 1

enum Dir: north, east, south, west     # simple enum
d := Dir.north
if d == .north: ...                     # `.name` when the type is known

enum Shape:
    circle(r: float)
    rect(w: float, h: float)
    empty

fn area(s: Shape) -> float:
    match s:
        circle(r): PI * r * r
        rect(w, h): w * h
        empty: 0

struct Stack[T]:                        # generic struct
    items: [T]

best: int? = none
if v := lookup(key): print(v)            # bind when present
n := lookup(key) ?? 0                    # default
k := lookup(key)!                        # unwrap or panic

pair := (1, "one")
a, b := pair
print(pair.0)
```

## 8. Modules

`import util` loads `util.jot` next to the importing file (or from the standard
library) and makes its names available as `util.name`. `import util as u` renames.
The core standard library (strings, arrays, maps, math, vectors, files, and the
game/graphics/audio API) is always available without importing.

## 9. Compile-time features

```jot
build:                          # build options live in the source
    target = wasm               # native (default) | wasm
    opt = release               # debug | release
    output = "mygame"

when TARGET == "wasm":          # compile-time conditional; the dead branch is not compiled
    ...
else:
    ...

logo := embed("logo.png")       # file contents baked into the program as [u8]

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

## 10. Programs and the game loop

A program runs its top-level statements, then `main()` if defined.
If the program defines `update(dt: float)` and/or `draw()`, a window opens and they are
called every frame (this is also how programs run in the browser).

```jot
pos := vec2(100, 100)

fn update(dt: float):
    if key_down(.right): pos.x += 200 * dt

fn draw():
    clear(rgb(0.1, 0.1, 0.15))
    circle(pos, 20, rgb(1, 0.5, 0.2))
```

## 11. Command line

```
jot file.jot [args]     compile and run (wasm target: opens the browser)
jot build file.jot      write the executable / .html
jot test file.jot       run `test` blocks
jot check file.jot      type check only
```
