"""Token-level view of Jot source, for mechanical source migrations.

tokenize(src) returns tokens covering the whole file (whitespace and comments included), so
that join(tokens) == src. Each token is [kind, text]; kinds: ws, nl, comment, ident, num,
str, char, op.
"""

OPS3 = ["..=", "<<=", ">>=", "**="]
OPS2 = ["..", "->", ":=", "==", "!=", "<=", ">=", "<<", ">>", "+=", "-=", "*=", "/=", "%=",
        "&=", "|=", "^=", "??", "**", "=>"]


def tokenize(src):
    toks = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c == "\n":
            toks.append(["nl", c])
            i += 1
        elif c in " \t\r":
            j = i
            while j < n and src[j] in " \t\r": j += 1
            toks.append(["ws", src[i:j]])
            i = j
        elif c == "#":
            j = src.find("\n", i)
            if j < 0: j = n
            toks.append(["comment", src[i:j]])
            i = j
        elif c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"): j += 1
            # raw string prefix r"..."
            if src[i:j] == "r" and j < n and src[j] == '"':
                k = _string_end(src, j, raw=True)
                toks.append(["str", src[i:k]])
                i = k
                continue
            toks.append(["ident", src[i:j]])
            i = j
        elif c.isdigit():
            j = i
            if src.startswith(("0x", "0X", "0b", "0B"), i):
                j = i + 2
                while j < n and (src[j].isalnum() or src[j] == "_"): j += 1
            else:
                while j < n and (src[j].isdigit() or src[j] == "_"): j += 1
                if j + 1 < n and src[j] == "." and src[j + 1].isdigit():
                    j += 1
                    while j < n and (src[j].isdigit() or src[j] == "_"): j += 1
                if j < n and src[j] in "eE" and (src[j + 1:j + 2].isdigit() or src[j + 1:j + 3] in ("e-", "e+") or src[j + 1:j + 2] in "+-"):
                    k = j + 1
                    if k < n and src[k] in "+-": k += 1
                    if k < n and src[k].isdigit():
                        j = k
                        while j < n and src[j].isdigit(): j += 1
            toks.append(["num", src[i:j]])
            i = j
        elif c == '"':
            k = _string_end(src, i)
            toks.append(["str", src[i:k]])
            i = k
        elif c == "'":
            j = i + 1
            if j < n and src[j] == "\\":
                j += 2
                while j < n and src[j] != "'": j += 1
            else:
                j += 1
            toks.append(["char", src[i:j + 1]])
            i = j + 1
        else:
            for op in OPS3 + OPS2:
                if src.startswith(op, i):
                    toks.append(["op", op])
                    i += len(op)
                    break
            else:
                toks.append(["op", c])
                i += 1
    return toks


def _string_end(src, i, raw=False):
    """index just past the string literal starting at src[i] == '"' (handles triple quotes)"""
    n = len(src)
    if src.startswith('"""', i):
        k = src.find('"""', i + 3)
        return n if k < 0 else k + 3
    j = i + 1
    depth = 0
    while j < n:
        c = src[j]
        if c == "\\" and not raw:
            j += 2
            continue
        if c == "{" and not raw:
            if src.startswith("{{", j):
                j += 2
                continue
            depth += 1
        elif c == "}" and not raw and depth > 0:
            depth -= 1
        elif c == '"' and depth == 0:
            return j + 1
        elif c == '"' and depth > 0:
            # a string inside an interpolation
            j = _string_end(src, j) - 1
        j += 1
    return n


def join(toks):
    return "".join(t[1] for t in toks)


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:]:
        src = open(path).read()
        assert join(tokenize(src)) == src, path
    print("round trip ok")
