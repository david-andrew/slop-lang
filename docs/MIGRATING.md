# Moving programs to the current syntax

The first version of Jot's syntax looked more like Python with `fn` and `:=`. The current one
is described in [LANGUAGE.md](LANGUAGE.md). The changes, old → new:

| first version | now |
|---|---|
| `x := 5` | `x = 5` (declares when there is no `x`; `let x = 5` always declares) |
| `fn add(a: int, b: int) -> int: a + b` | `add = (a: int, b: int) -> int: a + b` |
| `fn first[T](xs: [T]) -> T` | `first[T] = (xs: T[]) -> T` |
| `fn +(a: V, b: V) -> V` | `(+) = (a: V, b: V) -> V` |
| `extern fn f(x: float)` | `extern f = (x: f64)` |
| `fn(x): x * 2` | `(x): x * 2` |
| `[int]`, `[[f32]]` | `int[]`, `f32[][]` |
| `fn(int) -> str` (type) | `(int) -> str` |
| `float` | `f64` |
| `for x in xs:` | `loop x in xs:` |
| `for i in 0..n:` | `loop i in [0..n):` (a bare `0..n` now includes `n`) |
| `for i in 0..=n:` | `loop i in 0..n:` |
| `for i, x in xs:` | `loop i in 0.. and x in xs:` (`loop a, b in` unpacks) |
| `while cond:` | `loop cond:` |
| `while v := next():` | `loop let v = next():` |
| `if v := lookup(k):` | `if let v = lookup(k):` |
| `[x * x for x in xs if x > 0]` | `[loop x in xs: if x > 0: x * x]` |
| `[v; n]` | `fill(v, n)` |
| `xs[a..b]` (end excluded) | `xs[a..b)` |
| `a ** b` | `a ^ b` |
| `a ^ b` (xor) | `a xor b` |
| `x ^= y` | `x xor= y` (`x ^= y` is now power) |
| `'a'` (char literal) | `'a'` is a string; used where an integer is expected it is the character code |
| `"{"` in single quotes | `'{{'` (single-quoted strings interpolate too) |
| `import util` | `use 'util.jot'` (a path relative to the file) or `import util` |
| captured variables are copies | closures share the variables they capture |

## The converter

`tools/migrate/convert.py` rewrites files in place, keeping comments and layout:

    python3 tools/migrate/convert.py --globals lib file.jot other.jot

`--globals DIR` lists directories whose top-level names count as globals (so that assignments
to them inside functions stay assignments). Most programs need nothing else.

One thing syntax alone cannot tell is whether `for i, x in xs` counts (an array) or unpacks
(a map). The converter keeps such loops as `loop i, x in xs`; on an array the compiler then
reports `loop a, b in xs unpacks pairs ... write loop i in 0.. and x in xs`, and the fix is that
one line. (The first-version compiler built with `JOT_MIGRATE=1` can list these loops in
advance: pass its output with `--info file`.)

Things to check by hand afterwards:

* `^` in the old code meant xor; the converter rewrites each one, but read the results in
  long expressions (`a ^ b ^ c` becomes `(a xor b) xor c`).
* Bare ranges outside `for` loops now include their end: `xs[2..5]` has 4 elements.
* A closure that captured a variable which changes later now sees the change.
