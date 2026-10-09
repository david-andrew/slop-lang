# Sloppy for VS Code

Support for [Sloppy](https://sloppy-lang.org), a small compiled language for making games that
feels like a scripting language:

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

## The compiler

The extension needs the `sloppy` compiler (Linux or Windows, x86-64). If it cannot find one, it
offers to install the latest release (into `~/.sloppy`, or `%LOCALAPPDATA%\sloppy` on Windows); or
install it from a terminal, which also puts it on your PATH:

```sh
curl -fsSL https://sloppy-lang.org/install | bash
```

On Windows, in PowerShell:

```powershell
irm https://sloppy-lang.org/install.ps1 | iex
```

`sloppy update` (or the command **Sloppy: Install or Update the Sloppy Compiler**) installs newer
releases.

The extension uses the setting `sloppy.path` if it is set, else `bin/sloppy` when the Sloppy
repository is the open folder, else `sloppy` from the PATH, else `~/.sloppy/bin/sloppy`.

## Links

- [sloppy-lang.org](https://sloppy-lang.org): the language, its standard library, and a playground
- [Source and issues](https://github.com/david-andrew/sloppy-lang)
