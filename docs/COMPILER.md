# How the compiler is put together

A guide for working on Sloppy itself: where things are, what state each part owns, and how to
check a change. The compiler is written in Sloppy (`compiler/`, ~24k lines); `stage0/` is a
C compiler for a subset of Sloppy that builds it the first time.

## Building

```sh
tools/bootstrap.sh       # stage0 (C) -> sloppy1 -> sloppy2 -> sloppy3; sloppy2 == sloppy3; bin/sloppy
bin/sloppy build compiler/main.jo -o bin/sloppy.new && mv bin/sloppy.new bin/sloppy   # after a change
```

Rebuild `bin/sloppy` after changing the compiler (the tests use it), and run the bootstrap
before committing: the compiler's own code must stay within what `stage0` understands (for
example, a closure may not change a variable it captured, and some newer library functions
are missing there). The library (`lib/`) is read at every compile, so library changes need no
rebuild.

## The pipeline

| step | files | what it does |
|---|---|---|
| lex | `lex.jo` | source text to tokens, with INDENT/DEDENT for blocks |
| parse | `parse.jo`, `ast.jo` | tokens to AST nodes |
| check | `check.jo`, `expr.jo`, `types.jo` | modules and scopes, type inference, overloads, generic instances; rewrites nodes in place |
| lower | `lower.jo`, `ir.jo` | typed AST to IR: reference counting, copy-on-write, closures, formatting |
| optimize | `opt.jo`; release only: `inline.jo`, `loops.jo` | folding, copy propagation, dead code; inlining, loop versioning and vectorizing |
| code | `x64.jo`, `wasm.jo`, `glsl.jo` | register allocation and x86-64 encoding; WebAssembly; shaders as GLSL |
| write | `elf.jo`, `pe.jo`, `dwarf.jo` | Linux and Windows executables, debug information |
| drive | `main.jo` | the command line, targets and the build block, the order of the above |
| editors | `ide.jo`, `lsp.jo` | what a check learned, as lines; the language server |
| live | `repl.jo`, `watch.jo` | the interactive prompt; hot reloading (Linux) |

Functions are compiled one at a time from the roots (`main`, top-level code, exports): lowering a
call queues its callee (`lf_of_inst`), so only what is used is compiled, the standard library
included.

## State

The compiler is a batch program: most state is global and lives for one compile.

- **Nodes** (`ast.jo`): one array, referred to by index; node 0 means none. The fields `a`, `b`,
  `c`, `aux`, `sval`, `ival` mean different things for different kinds: the parser function
  that makes a kind (`mk(.kind, ...)` in `parse.jo`) shows what goes where. The checker rewrites nodes in place (a conversion
  moves the old content to a fresh node and wraps it).
- **Types** (`types.jo`): one array; concrete types are interned, so equal types have equal
  ids. Structs, enums and unions are `StructInfo`s with their fields.
- **Positions**: `mkpos(file, offset)`; `files[]` holds the sources. Errors go through
  `fatal(pos, msg)`, which prints `file:line:col: error: msg` and exits with status 1 (or, in the
  language server, records the error). `ice(msg)` is for states that cannot happen.
- **Function instances** (`fns`, `check.jo`): one per function and set of type arguments; the
  lowering queue (`lfuncs`) refers to them.
- **Target settings** (`target_wasm`, `target_windows`, `ptr_size`): set once by `setup_target`
  (`main.jo`) for building, checking and the language server alike.

The language server, the prompt and `sloppy watch` check in a fresh process each time (fork on
Linux; on Windows the language server starts `sloppy lsp --child`), so global state never has
to be reset.

## Tests

| command | what |
|---|---|
| `python3 tools/runtests.py --compiler sloppy [--release] [--target wasm\|windows] [pattern]` | programs in `tests/t` against their `.out`; then `tests/backtrace`, `tests/unit` (`sloppy test`), `tests/errors`, `tests/repl` |
| `python3 tools/runtests.py` | the same programs through the C bootstrap compiler |
| `python3 tools/lsptest.py` | the language server, driven as an editor does |
| `python3 tools/rendertest.py --no-gpu` | games rendered by the software renderer against reference frames |
| `python3 tools/watchtest.py` | hot reloading |
| `python3 tools/fuzz.py 100` | random valid programs, built four ways, must agree |
| `python3 tools/fuzz_errors.py 2000` | real programs broken at random: the compiler must give an error, never crash |

Adding a test:
- a program: `tests/t/name.jo` and its expected output `tests/t/name.out` (output after a
  panic ends with `[exit 101] panic: ...`). Add `# requires: sloppy` near the top if the C
  bootstrap compiler cannot build it.
- an error: `tests/errors/name.jo` whose first line is `# error: <part of the message>`; the
  compiler must exit with status 1 and that message (a crash fails the test).
- a backtrace: `tests/backtrace/name.jo` with all of stderr in `.out`.

Windows programs are tested under Wine locally (`--target windows`, see the runner) and on
Windows itself in CI.

## Looking inside

- `sloppy build file.jo --ir`: the IR of each function as it is emitted.
- `sloppy build file.jo --time`: time per phase.
- `SLOPPY_STOP=lex|parse sloppy check file.jo`: stop early.
- `SLOPPY_RASTAT=1` / `SLOPPY_RADUMP=<function>`: register allocation statistics / decisions.
- `sloppy lsp --dump file.jo`: the lines a check writes for the language server.
- A compiler crash prints a backtrace with Sloppy line numbers, like any Sloppy program.
