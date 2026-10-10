#!/usr/bin/env python3
"""Release notes for a tag: how to install, then that version's section of CHANGELOG.md.
usage: release_notes.py vX.Y.Z > notes.md"""
import os, re, sys

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
version = sys.argv[1].lstrip("v")
text = open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8").read()
m = re.search(r"^## " + re.escape(version) + r"\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
print("Install or upgrade (or run `sloppy update`): on Linux `curl -fsSL https://sloppy-lang.org/install | bash`; "
      "on Windows, in PowerShell, `irm https://sloppy-lang.org/install.ps1 | iex`")
if m:
    # (GitHub shows each line break in release notes: join the lines of a paragraph or list item)
    out = []
    for line in m.group(1).strip().split("\n"):
        if out and line.strip() and out[-1].strip() and not line.startswith(("- ", "#")):
            out[-1] += " " + line.strip()
        else:
            out.append(line)
    print()
    print("\n".join(out))
