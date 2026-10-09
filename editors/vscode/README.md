# Sloppy for VS Code

Support for the [Sloppy](../../README.md) language:

- highlighting
- errors as you type (several at once, when they are in different functions)
- hover: types, signatures and doc comments
- go to definition (also into the standard library), find references, highlight uses, rename
- completion: names in scope, fields and functions after `.`, enum variants after a bare `.`
- signature help while typing arguments
- inlay hints: the inferred types of variables and function results
- outline (document symbols)
- run the file in a terminal (Ctrl+F5, or the run button), in the browser, or its tests

The language features come from the compiler itself: `sloppy lsp` is a language server that any
editor with LSP support can use.

## Installing

```
tools/vsix.py                                  # writes build/sloppy-0.1.0.vsix
code --install-extension build/sloppy-0.1.0.vsix
```

The extension runs `bin/sloppy` when the Sloppy repository is open in VS Code, otherwise `sloppy` from
the PATH; the setting `sloppy.path` overrides both.
