# Jot syntax, revision 2 (design notes)

Decisions for the requested syntax changes, mostly following Dewy's semantics where the request
pointed there. Where a request left a choice open, the choice and the reason are noted. None of
these changes affects compile speed measurably: everything is decided by local token lookahead
(the lexer records matching bracket positions, so "is this `(...)` followed by `->` or `:`" is
O(1)), and the new library features (n-d arrays, units) are only compiled when used.

## Declarations

    x = 5                 # declares x (no visible x) or assigns (x visible) — like Python/Dewy
    let x = 5             # always a new binding (shadows an outer x)
    const LIMIT = 10      # constant
    count: int = 0        # an annotation always declares
    names: str[]          # declared, empty

`:=` is gone. Assigning to a visible global from inside a function assigns the global (as
closures do; see Closures).

## Functions

    add = (a: int, b: int = 2) -> int: a + b
    area = (r: f64) -> f64:
        PI * r ^ 2
    twice = (f, x): f(f(x))              # untyped parameters: generic
    first[T] = (xs: T[]) -> T: xs[0]     # explicit type parameters
    squares = xs.map((x): x * x)         # the same syntax is the lambda syntax
    (+) = (a: Money, b: Money) -> Money: Money(a.cents + b.cents)    # operators
    @lib("libm.so.6")
    extern cbrt = (x: f64) -> f64

A parenthesized parameter list followed by `->` or `:` is a function; otherwise `(...)` is a
grouping or tuple. Function types are written `(int, str) -> bool`.

## Loops

One keyword. The header is a condition, a binding `name in iterable`, or several of those
joined with `and` / `or`:

    loop: ...                                   # forever
    loop n > 0: ...                             # while
    loop i in [0..10): ...                      # for
    loop k, v in table: ...                     # unpacking (maps: key, value)
    loop mut p in particles: p.x += p.vx        # elements by reference
    loop i in 0.. and v in values: ...          # enumerate: zip, stops when one runs out
    loop i in 0.. and v in values and v ^ 2 < limit: ...   # also stops at the first false condition
    loop a in xs or b in ys: ...                # until all run out; exhausted ones give none (T?)

In a loop header `name in X` always binds; use parentheses for a membership test there.

Comprehensions are a loop inside brackets; an `if` without `else` filters, nested loops flatten:

    squares = [loop i in [1..5]: i ^ 2]
    evens = [loop n in [0..10): if n % 2 == 0: n]
    pairs = [loop i in [0..3): loop j in [0..3): (i, j)]

(The colon may be left out when the value starts on the same line: `[loop i in xs i * 2]`.)

## Ranges

    1..10        # both ends included
    [1..10]      # the same
    [0..n)       # end excluded
    (0..1]  (0..1)
    0..          # open (iterating counts up forever)
    0,2..20      # step 2: 0 2 4 ... 20   (bare after `in`; elsewhere inside brackets: [0,2..20])
    10,9..0      # counting down

Index brackets double as range brackets, and `end` is the last index:

    xs[2..5)     xs[2..]     xs[..3)     xs[end]     xs[1..end-1]

## Arrays

    xs: int[] = [1 2 3]          # elements separated by spaces or commas
    ys = [xs... 4 5]             # spread
    grid = [1 2; 3 4]            # rows with ; or newlines: a 2-d array, type int[,]
    zeros(3)  ones(2, 3)  fill(7, 4)  linspace(0, 1, 5)  rand(3, 3)  eye(3)

Inside array brackets a space separates elements, so `[a -b]` has two elements and `[a - b]`
one (as in MATLAB); `f(x)` / `xs[i]` must be written without a space before `(` / `[` there.
`[x; n]` (repeat) is replaced by `fill(x, n)`.

Arithmetic follows Julia: `a + b`, `a - b` on same-shaped arrays, `2 * a`, `m * v` matrix
products; dotted operators broadcast elementwise with singleton dimensions (numpy rules):
`.+ .- .* ./ .^ .% .== .< ...`, and `f.(xs)` maps a function over arrays. `Array[T]` is another
spelling of `T[]`.

Struct-of-arrays storage: `particles: soa Particle[]` keeps each field in its own array while
`particles[i].x`, `push`, loops etc. work as for any array.

## Operators

`^` is power (right-associative, tighter than unary minus: `-2^2 == -4`). `and or xor not` are
logical on bools (short-circuit) and bitwise on integers, with low precedence (below
comparisons). The symbols `& | ~` are bitwise with high precedence (above comparisons), so
`flags & MASK == 0` means `(flags & MASK) == 0`. `|` between types makes a union. Compound
forms: `+= -= *= /= %= ^= &= |= and= or= xor= <<= >>=`.

## Types

`int` (64-bit), `i8 i16 i32 i64 u8 u16 u32 u64`, `f32 f64` (no `float`; literals like `1.5` are
`f64` unless the context wants `f32`), `bool`, `str`, `T[]`, `T[,]`, `{K: V}`, `(A, B)`,
`(A) -> R`, `T?` (= `T | none`), `A | B`.

Unions instead of payload enums:

    struct Circle: r: f64
    struct Rect: w: f64; h: f64
    Shape = Circle | Rect                 # a type alias
    area = (s: Shape) -> f64:
        if s is Circle: return PI * s.r ^ 2  # `is` tests and narrows
        s.w * s.h
    parse = (text: str) -> int | ParseError: ...

Plain enums (`enum Dir: up, down, left, right`) stay.

## Units

A unit directly after a number (no space) converts to the base unit at compile time:

    sleep(120ms)     # 0.12 (seconds)
    speed = 1.2(m/s)
    turn(90deg)      # radians
    v = [1.2 0](m/s)

Time `s ms us ns min h`, length `m cm mm km`, mass `kg g`, angle `rad deg turn`, force `N`;
derived units in parentheses with `* / ^`. Long names work too (`10seconds`, `3meters`).
Values are plain `f64`s (no dimension checking for now).

## Strings

`"..."` and `'...'` are the same; both may span lines; `{expr}` interpolates. A one-character
literal used where an integer is expected is its character code (`c == 'a'`), which replaces
char literals. `"""..."""` (dedented) remains for docstrings; `r"..."` is raw.

## Modules

    use 'util.jot'            # a file, relative to this one
    use 'gfx/shapes.jot'
    use thread                # standard library modules by name

## Closures

Closures capture variables, not values, the same everywhere: a closure created in a function
sees and can change that function's variables exactly as a top-level closure sees and changes
globals. (Variables that are never changed after the closure is created are copied into it, so
the common case costs nothing extra.)
