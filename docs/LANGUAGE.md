# The Sloppy Programming Language

Sloppy is a small, statically typed, compiled language that feels like a scripting
language. `sloppy game.jo` compiles the whole program (in milliseconds) and runs it.

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

```gdscript
# hello.jo
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

### The interactive prompt

`sloppy` with no file starts an interactive prompt. Type declarations and statements; they run
as you enter them, and the value of an expression at the end of an input is shown:

```
>>> xs = [3 1 2]
>>> xs.sort()
>>> xs .* 10
[10, 20, 30]
>>> f = (n: int):
...     n * n
...
>>> f(12)
144
```

A line ending with `:` starts a block and an empty line ends it. Names stay declared, and
declaring one again replaces it (code entered before keeps the old one). Each input is compiled
to machine code that runs in a session process, so it runs as fast as a program does. If an
input has errors, or panics, or crashes, or is stopped with ctrl-c, the session is exactly as it
was before it. `:type expr` shows an expression's type, tab completes names (including fields
after a `.`), up and down recall earlier lines, and ctrl-d or `exit` leaves. Input can also be
piped in (`sloppy < script.txt`).

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

```gdscript
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
| `T[N]` | fixed-size array: N elements stored in place (in a struct, a variable, a shader's uniforms) |
| `T[,]` | n-dimensional array (see section 8) |
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

Every type in Sloppy is a *value*: assignment copies. Arrays, strings and maps are
reference counted with copy-on-write, so copies are O(1) and a real copy only
happens when you mutate something that is shared. There are no reference types,
so reference cycles (and leaks) are impossible, and there is no garbage collector.

```gdscript
a = [1, 2, 3]
b = a           # O(1), shares storage
b.push(4)       # b is shared, so b gets its own copy here
print(a, b)     # [1, 2, 3] [1, 2, 3, 4]
```

Function parameters are borrowed (passed without copying, read-only).
Mark a parameter `mut` to let the function modify the caller's variable:

```gdscript
grow = (xs: mut int[]): xs.push(0)
grow(nums)
```

To modify array elements in a loop, use `loop mut`:

```gdscript
loop mut p in particles:
    p.pos += p.vel * dt
```

### Fixed-size arrays

`T[N]` holds exactly N elements, stored in place: inside a struct, a variable or a shader's
uniforms, with no separate allocation. N is a number or a constant (`const SLOTS = 8`, then
`int[SLOTS]`). They are made from a literal with N elements, from `[]` (all zeros, which is also
what a field or variable without a value starts as) or from `fill(x, N)`:

```gdscript
struct Inventory:
    slots: int[8]                   # zeros
    hands: str[2]                   # ""
corners: vec2[4] = [vec2(0, 0), vec2(1, 0), vec2(1, 1), vec2(0, 1)]
inv = Inventory()
inv.slots[3] = 42                   # bounds-checked; a constant index is checked when compiling
loop mut c in corners: c *= 2.0
print(corners.len(), inv.slots == fill(0, 8))
```

They index, loop (`loop x in xs`, `loop mut x in xs`), compare with `==`, print and work as
map keys like `T[]`. A copy copies the elements. Where a `T[]` is expected (`sum(xs)`, a
parameter `xs: T[]`) a fixed-size array is passed as a new array holding a copy; `push`,
`pop` and the other functions that change the length need a `T[]`.

### Maps

`{K: V}` maps keys to values and keeps them in insertion order. `m[k]` reads a value (a
missing key is an error; `m.get(k)` gives an optional, `m.get(k, default)` a default) and
`m[k] = v` sets one. Changing the value in place, `m[k] += 1`, `m[k].push(x)`,
`m[k].hp -= 5`, `m[k][i] = x` or `loop mut x in m[k]`, works on the stored value and adds a
missing key first, with V's zero value (for a struct, its default field values):

```gdscript
counts: {str: int} = {}
loop w in words: counts[w] += 1
groups: {int: str[]} = {}
loop w in words: groups[len(w)].push(w)
loop k, v in counts: print("{k}: {v}")
```

`m.has(k)`, `m.remove(k)`, `m.keys()`, `m.values()` and `m.len()` do what they say.

## 5. Functions

```gdscript
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

```gdscript
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

```gdscript
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

```gdscript
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

**Panics.** An index out of bounds, `!` on `none`, a division by zero, a failed `assert` or
`panic("message")` stops the program with the message and where each function on the way
was called from (the frames of the runtime left out):

```
panic: hit an enemy that was already defeated
    in hit (game.jo:6)
    called from fight (game.jo:9)
    called from update (game.jo:31)
```

A stack overflow (a function that calls itself without end) and a crash in code using raw
pointers or C are reported the same way. (Release builds inline small functions: their frames
show as the line of the call. In a web page the browser's console has the JavaScript stack.)

**Debuggers and profilers.** Executables written by `sloppy build` carry DWARF line tables and
function names, so gdb works with the `.jo` source (`break game.jo:31`, `bt`, `next`, `list`)
and perf and other profilers report functions and lines.

**Combined loops.** Bindings and conditions join with `and` / `or` in one loop header:

```gdscript
loop i in 0.. and v in values: ...             # counts alongside: stops when values runs out
loop i in 0.. and v in values and v ^ 2 < limit: ...   # also stops at the first false condition
loop a in xs or b in ys: ...                   # until both run out; a finished one gives none
loop (a in xs or b in ys) and ok(): ...
```

Iterators joined with `and` advance together until one runs out; joined with `or` they advance
until all have run out (the variables of finished ones are `none`, so they are optionals).
`loop i, x in xs` does not count: two names before `in` always unpack.

**Comprehensions** are a loop inside brackets; `if` filters, nested loops flatten:

```gdscript
squares = [loop i in [1..5]: i ^ 2]
evens = [loop n in [0..10): if n % 2 == 0: n]
pairs = [loop i in [0..3): loop j in [0..3): (i, j)]
```

**Match:**

```gdscript
match value:
    0: print("zero")
    1, 2: print("small")
    3..9: print("medium")
    'a'..'z': print("a letter code")
    _: print("big")
```

## 7. Structs, unions, enums, optionals, tuples

```gdscript
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

```gdscript
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

Ruling a member out narrows to the others: after `if s is Circle: return` in a function taking
`Circle | Rect | Tri`, `s` is a `Rect | Tri`, and in an `if`/`else if`/`else` chain each branch
knows what the earlier tests excluded. A `match` arm listing several types (`int, str: ...`)
sees their union, and `_:` the members no earlier arm matched. Fields and globals narrow the same
way as variables (`if self.target is Enemy: self.target.hp -= 1`); assigning a member to a field
narrows it to that member, and passing the value on as a `mut` argument forgets what was known.
Assigning another member to a narrowed variable makes it the whole union again. A union fits
any union that has all of its members (`int | str` passes for `int | str | f64`), and a generic
parameter inside a union stands for the members the union does not name: `value_or[T] = (r: T |
Err, d: T) -> T` called with an `int | str | Err` has `T = int | str`. A union value prints as
the value it holds. `T | none` is `T?`.

**Optionals:**

```gdscript
best: int? = none
if let v = lookup(key): print(v)        # bind when present
if best is int: print(best + 1)         # `is` works on optionals too
n = lookup(key) ?? 0                    # default
k = lookup(key)!                        # unwrap or panic
```

**Tuples:**

```gdscript
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

```gdscript
xs = linspace(0, 1, 5)
ys = 3.0 .* xs .^ 2 .+ 1.0       # one loop
mask = xs .> 0.5                 # bool[]
roots = sqrt.(xs)
```

(Plain `+` on 1-D arrays concatenates, as for lists.)

**n-dimensional arrays** (`T[,]`). How many dimensions an array has is part of its value, as
in numpy: `T[,]`, `T[,,]` ... all name the same type (the commas are for the reader), and
`m.shape` holds the dimensions. Rows are separated by `;` or line breaks; `[a; b]` stacks arrays
(1-D arrays become rows, n-dimensional ones gain a dimension).

```gdscript
m = [1.0 2.0; 3.0 4.0]
grid = [0 1 0
        1 1 1]
rows = [a; b]                    # stack arrays a and b as rows
print(m[1, 0], m.shape)          # 3.0 [2, 2]
m[0, 1] = 5.0
v = m * [1.0, 1.0]               # matrix times vector
p = m * transpose(m)             # matrix product
k = m .* 2.0 .+ [10.0 20.0]      # broadcasting a row
cube = zeros(4, 4, 4)            # 3-D
cube[1, 2, 3] = 1.0
layers = cube .* reshape([1.0, 2.0, 3.0, 4.0], 4, 1, 1)   # broadcasting along the first axis
```

Ranges among the indexes select parts: `m[i, ..]` is row `i`, `m[.., j]` column `j`,
`m[1..2, 3..]` a block (ranges include both ends; `a..` runs to the end of the axis, and indexes
left out at the end mean whole axes). A part is an array of its own; assigning to one writes into
the array: `m[.., 0] = xs`, `m[0, ..] = 0.0`. `sum(m, axis)`, `mean`, `min` and `max` reduce along
one axis (`sum(m, 0)` adds up the rows: one sum per column).

```gdscript
img = zeros(480, 640, 3)
img[.., .., 0] = 1.0             # the red channel
top = img[0..239, ..]
brightness = sum(img, 2)            # (480x640)
```

`zeros`, `ones`, `rand` (uniform in [0, 1)) and `randn` (normal) take 1 to 4 dimensions (with
one, they make a plain `f64[]`); also `eye(n)`, `linspace(a, b, n)`, `reshape(xs, dims...)` or
`reshape(xs, shape)`, `ndarray(data, shape)`, `transpose` (reverses the axes), `row(m, i)`,
`col(m, j)`, `flatten`, `size`, `ndim`, `len` (the first dimension), `sum`, `mean`, `min`,
`max`, `dot`, `norm`. On 2-D arrays `+ -` work elementwise on equal shapes and `*` is the matrix product.
Indexing with the wrong number of indexes, and shapes that do not broadcast, are errors when
the program runs, with the shapes in the message.

**Struct-of-arrays.** `ps: soa Particle[]` is used exactly like `Particle[]` — `push`, `pop`,
`remove`, `len`, `ps[i]`, `ps[i].x += 1`, `loop p in ps`, `loop mut p in ps`, conversion from
`Particle[]` — but keeps each field in an array of its own. A loop variable stands for the
element itself: `p.x` reads (or, in `loop mut`, writes) only the `x` array, so a loop that looks
at two fields of a large struct touches only those two arrays. Using `p` as a whole value reads
every field. `ps.x` is the whole field array, for elementwise math:

```gdscript
ps: soa Particle[] = make_particles()
loop mut p in ps:
    p.pos += p.vel * dt                 # reads vel, writes pos: no other field is touched
ps.age = ps.age .+ dt
```

**GPU arrays.** `gpu(xs)` copies an array to GPU memory and `cpu(g)` copies it back. A dotted
expression whose arrays are GPU arrays runs on the GPU as one fragment program, generated from
the expression at compile time — functions applied with `f.(g)` are translated to GLSL like
shader functions, and the numbers in the expression become uniforms:

```gdscript
g = gpu(rand(4_000_000))
h = wave.(g) .* 0.5 .+ g          # one GPU program
ys = cpu(h)
```

GPU arrays have the shape of the array they were made from (up to 4 dimensions) and broadcast
like arrays on the CPU; `cpu(g)` gives an array of that shape. Values on the GPU are `f32`, or `i32`
for arrays made from integers: integer arithmetic keeps integer semantics (`7 / 2` is 3, `%` keeps
the dividend's sign, as on the CPU), and mixing integers with floats gives floats. `sum`, `mean`,
`min` and `max` run on the GPU (float sums add in `f32`, pairwise: about 1e-7 relative error).
Arrays may hold as many values as the GPU's largest texture times four (a billion on a typical
desktop GPU). GPU memory is reused automatically once no copy of a GPU array is left. Native programs use OpenGL
ES (no window needed), web builds WebGL 2. Where neither can render to float textures (no
driver, `SLOPPY_SOFTWARE=1`, an old browser) the same expressions run on the CPU, so programs work
everywhere; `gpu_available()` tells which.

## 9. Modules

A module is a file: `'physics.jo'` (relative to the importing file) or a standard-library
module by name (`thread`). There are three ways to bring one in:

```gdscript
import 'physics.jo'                         # physics.step(b), physics.Body: the names under the module's
import 'physics.jo' as ph                   # ph.step(b)
from 'physics.jo' import step, Body, gravity as g     # just these names, as they are (or renamed)
use 'physics.jo'                            # all its names, as they are
```

`import` keeps a module's names apart and is the one to reach for in a program of several
files; `from ... import` picks names (a long list can go in parentheses over several lines);
`use` suits a small program split into files that share one set of names. Names starting with
`_` are private to their file: `use` leaves them out, while `physics._helper` and
`from 'physics.jo' import _helper` reach them deliberately. A module's own functions with an
imported function's name are overloads of it; any other clash is an error (rename with `as`).
`use` and imports are not transitive: a file sees the names of the modules it brings in itself.

The core standard library (strings, arrays, maps, math, vectors, files, numeric arrays, and
the game/graphics/audio API) is always available without importing.

## 10. Compile-time features

```gdscript
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

`sloppy test file.jo` runs the file's top-level code, then each `test` block in order,
reporting `test name ... ok` per block; the first failing `assert` stops the run with its
message and location.

**Release builds.** `opt = release` (or `sloppy build --release`) inlines refcount, uniqueness
and bounds-check fast paths and runs the optimizer (constant folding, copy propagation,
common subexpressions, redundant load and bounds-check elimination, inlining, keeping small
vectors in registers). Debug builds compile faster; both have identical behavior, including
bounds checks.

In release builds, `b = xs[i]` where `b` is only read (and nothing changes `xs` while `b` is
used) is the element itself, not a copy: reading a few fields of a big struct in an array
costs only those reads. A loop whose bounds checks index by the loop variable checks the
whole range once, up front (and runs as before when that test fails, so a failing check
still stops it where it always did). A loop that does the same arithmetic to element `i` of
arrays of numbers (`ys[i] = ys[i] + a * xs[i]`, a dotted expression, `loop mut x in xs`
with `+ - * /`) runs several elements at a time: 256-bit AVX2 instructions where the processor
has them, else SSE2, chosen when the program starts (`SLOPPY_NO_AVX=1` forces SSE2). Every
element gets the same operations in the same order as one at a time, so the results are
identical on every machine (sums over a loop keep their order and are not vectorized).

Array indexing is always checked, except where the check cannot fail: in
`loop i in [0..xs.len())` (or `[0..n)` with `n = xs.len()`, or `xs = fill(v, n)` and
`[0..n)`, starting from any expression that cannot be negative) `xs[i]` has no check, as long
as the function never resizes `xs` — writing its elements is fine. So the usual index loop
costs what it would in C.

## 11. Parallelism

Data-parallel helpers run a function over many elements on all CPU cores (fork-join):

```gdscript
lengths = parallel_map(words, (w): expensive(w))      # [loop x in xs: f(x)]
parallel_update(particles, (p): step(p, dt))          # xs[i] = f(xs[i]) in place
rows = parallel_range(height, (y): render_row(y))     # [loop i in [0..n): f(i)]
```

The function runs on many threads at once: it may read anything, but it must not change
globals or the variables it captured (that would be a data race). Return results instead. The
compiler checks this, also in the functions it calls, and names the variable. (Writing through a
raw pointer is left to the program: it is how disjoint parts of one buffer are filled in parallel.)
Web builds run the same code on one thread.

## 12. Programs and the game loop

A program runs its top-level statements, then `main()` if defined.
If the program defines `update(dt: f64)` and/or `draw()`, a window opens and they are
called every frame (this is also how programs run in the browser).

```gdscript
pos = vec2(100, 100)

update = (dt: f64):
    if key_down(.right): pos.x += 200 * dt

draw = ():
    clear(rgb(0.1, 0.1, 0.15))
    circle(pos, 20, rgb(1, 0.5, 0.2))
```

**Input.** `key_down(k)` is true while a key is held, `key_pressed(k)` / `key_released(k)` in
the frame it goes down or up, and `key_typed(k)` when pressed and again as it repeats while held
(at the desktop's repeat rate: for moving through text or menus). `text_input()` is the text
typed this frame, repeats included. Likewise `mouse_down`, `mouse_pressed`, `mouse_pos()`,
`mouse_wheel()`, and gamepads (`gamepad_down`, `left_stick()`); `input_axis()` combines arrows,
WASD and the left stick. For mouse look, `mouse_lock()` hides the pointer and keeps it in the
window while `mouse_delta()` reports how far it moved (Wayland, X11 and browsers, where the
lock starts at the next click and Escape ends it); `mouse_lock(false)` lets it go.

**Fullscreen and the clipboard.** `set_fullscreen(true)`, `toggle_fullscreen()` and
`is_fullscreen()` (in a browser, the page asks for fullscreen; it leaves on Escape).
`clipboard()` reads the system clipboard's text and `set_clipboard(s)` replaces it. A web page
may read the clipboard only as something is pasted, so there `clipboard()` is the text last
pasted (ctrl+V) into the page; the X11 fallback without libX11 keeps the text within the program.

**Window size.** `window("Title", 1280, 720)` (called for you with those defaults) sets the
window's starting size and the program's 2D coordinate space: 2D drawing and `mouse_pos()` are in
those units however large the window becomes — resized, maximized, or a browser page, which the
game fills — scaled to fit and centered. A window of another shape shows more around that
area: `visible_rect()` is the part of the plane on screen (draw backgrounds over it),
`screen_size()` is the size given to `window()`, `pixel_size()` the real size. 3D rendering
uses the whole window.

**Screens of any size and shape.** 2D drawing is in units of the size given to `window()` (the
design size), whatever the window's real size; `screen_fit` says how that area fits a window
of another shape, and the render resolution says how many pixels draw it:

```gdscript
screen_fit(.expand)       # (default) scaled to fit, centered; a wider or taller window shows more
                          # around it (visible_rect() is what is shown)
screen_fit(.letterbox)    # just the design area, with bars (letterbox_color(c))
screen_fit(.crop)         # the design area fills the window; what sticks out is cut off
screen_fit(.stretch)      # stretched to the window (shapes distort)
screen_fit(.native)       # no scaling: one unit per window pixel

render_resolution(640, 360)   # draw at a fixed resolution, scaled up (sharp pixels, whole steps;
                              # smooth = true, whole = false for other looks)
pixel_art()                   # the same at the design size: window("game", 320, 180) + pixel_art()
                              # is a 320 x 180 pixel game (its window opens 4 times larger)
render_scale(0.5)             # draw at half the window's resolution (fewer pixels: faster)
```

`mouse_pos()` is in the same 2D units, and 3D follows the same picture (a letterboxed game's 3D
view has the design area's shape). `SLOPPY_FIT=letterbox` and `SLOPPY_RESOLUTION=320x180` try a mode
on any game without changing it.

Window sizes are in the desktop's logical units, and frames are rendered at the display's real
resolution: on a screen scaled by 1.67, a 1280x720 window has 2133x1200 pixels, so text and edges
stay sharp (in the browser too). The rendered frame goes to the compositor without being copied
through the CPU.

Native games open a Wayland window when `WAYLAND_DISPLAY` is set and an X11 window otherwise
(`SLOPPY_PLATFORM=x11|wayland` chooses). Windows have the desktop's own decorations: on GNOME they
are drawn by libdecor (with GTK, as other apps' title bars are), elsewhere by the compositor
(xdg-decoration) or the X11 window manager; without libdecor (or with `SLOPPY_LIBDECOR=0`) the
program draws a plain title bar itself. A window's title is the program's name unless
`window(title)` gives one. Everything a game loads at run time is optional: without
libwayland-client (or with `SLOPPY_WAYLAND=protocol`) it speaks the Wayland protocol itself, and
without libX11 the X11 protocol. They use the system's OpenGL ES driver when there is
one. Without it (or with `SLOPPY_SOFTWARE=1`) the same program draws with the built-in software
renderer, which runs your shader functions (see `make_shader`) on the CPU; `soft_rendering()`
tells the program which is in use, e.g. to draw fewer particles. Frames are rendered at half
resolution (`SLOPPY_SOFT_SCALE=1` for full resolution) and paced to 60 per second.

**Frame statistics.** `show_stats()` (or `SLOPPY_STATS=1`, or `?stats` at the end of a web page's
address) draws an overlay with the frame rate, a graph of recent frame times, the CPU time of
`update` + `draw`, the time spent handing frames to the screen, and how many frames took much
longer than usual (stutter). `SLOPPY_STATS=log` (`?stats=log`) prints the same numbers every two
seconds, and each long frame as it happens. In a web page, `env(name)` reads the page's URL
parameters, so `?SLOPPY_STATS=1` and `?stats` are the same. Files in a web page (`read_file`,
`write_file`, `list_dir`) are the page's own, in memory (`sloppy.files` in JavaScript); a web build
run under node (`tools/runwasm.js page.html args...`) uses the real ones and gets the arguments.

Environment variables for testing and tuning: `SLOPPY_SCREENSHOT=out.png` (with `SLOPPY_FRAMES=n`)
saves frame n and exits — the clock then advances exactly 1/60 s per frame, so the image is
reproducible, and with `SLOPPY_SOFTWARE=1` no display is needed at all; `SLOPPY_INPUT="5:space+,9:space-"`
presses and releases keys at given frames; `SLOPPY_THREADS=n` caps the threads used by the
parallel functions; `SLOPPY_SCALE=1` renders at the logical size and lets the compositor scale
it up; `SLOPPY_FRAME_STATS=1` (with `SLOPPY_SCREENSHOT`) reports frame times and how frames reach the
screen.

```
sloppy file.jo [args]     compile and run (wasm target: opens the browser)
sloppy watch file.jo      run it, and reload it while its files change
sloppy --web file.jo      compile for the web and open it in the browser
sloppy build file.jo      write the executable / .html
sloppy test file.jo       run `test` blocks
sloppy check file.jo      type check only
sloppy update             install the latest release (when this is not it)
```

**Reloading while it runs.** `sloppy watch game.jo` runs the game and keeps watching the files it
is built from. Each time one is saved the game is rebuilt and the running game takes the new
code between two frames, without starting over: the window stays open and every global keeps
its value (the player where they are, the level as it is, what is loaded on the GPU), so a
change to how something moves or looks shows at once.

- Changed and new functions take effect at the next frame, also in function values and closures
  the game keeps (a lambda that captures other variables than before is a new one: closures made
  earlier keep running the old code).
- A global is set again from its declaration when that declaration changes (`speed = 300.0`
  after `speed = 200.0`), when a file it names changes (`player = load_texture(embed("player.png"))`
  after the image is saved), or when the functions of a GPU program it makes do
  (`sky = make_shader(shader(sky_vs, sky_fs))`). New globals are set when they appear.
  Top-level statements and `main` do not run again.
- When a struct the game holds changes (a field added, removed, reordered, or of another numeric
  type), the values are kept: each is converted to the new layout field by field (by name),
  through arrays, optionals, maps and nested structs; a new field starts at its default (a
  literal default; otherwise zero).
- A build with errors leaves the game running as it was, with the errors over it and in the
  terminal. A panic in `update` or `draw` pauses the game with the message on the screen; saving
  a fix goes on from there.
- `r` (and enter) in the terminal starts the program again from the beginning (`sloppy watch` says
  when an edit needs it: top-level statements that changed); `q` quits. A game that gains or
  loses `update` or `draw` is started again by itself.
- A program without `update`/`draw` is run again from the start each time its files change.

`sloppy watch` runs native builds (Linux), in debug or release mode as the build block says.

## 13. Calling C

Native programs can call functions from system shared libraries; the library is loaded the
first time one of its functions is called, so a missing library only matters to code that
actually uses it (check with `lib_available("libfoo.so.1")`).

```gdscript
@lib("libm.so.6")
extern cbrt = (x: f64) -> f64

@lib("libGLESv2.so.2")
@symbol("glClear")                 # the C name, when the Sloppy name differs
extern gl_clear_native = (mask: u32)
```

Arguments and results must be scalars or pointers; `cfn(...) -> T` is the type of a C function
pointer, and `@cabi` makes a Sloppy function callable from C.
