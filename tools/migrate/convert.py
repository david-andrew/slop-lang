#!/usr/bin/env python3
"""Convert Jot source from syntax revision 1 to revision 2 (docs/SYNTAX2.md).

usage: convert.py --info migrate_info.txt --globals lib_dir file.jot...   (rewrites in place)

Token based: comments, strings and layout are kept. Type facts that syntax alone cannot
give (which two-variable loops run over arrays) come from the old compiler (JOT_MIGRATE=1).
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jtok import tokenize, join

KW_STMT = {"return", "if", "else", "while", "for", "match", "break", "continue", "pass", "defer"}
LOW_STOP = {",", ";", ":", "=", ":=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=",
            "==", "!=", "<", "<=", ">", ">=", "??", "->", "and", "or", "not", "in", "return", "if",
            "else", "for", "while", "match", "as", "is"}

# ---------------------------------------------------------------------------
class Toks:
    def __init__(self, src):
        self.t = tokenize(src)

    def sig(self, i, d=1):
        """index of the next significant token from i (exclusive) in direction d"""
        j = i + d
        while 0 <= j < len(self.t) and self.t[j][0] in ("ws", "comment"): j += d
        return j

    def txt(self, i):
        return self.t[i][1] if 0 <= i < len(self.t) else ""

    def kind(self, i):
        return self.t[i][0] if 0 <= i < len(self.t) else "eof"

    def match_close(self, i):
        """index of the bracket closing the one at i"""
        o = self.txt(i)
        depth = 0
        for j in range(i, len(self.t)):
            x = self.t[j]
            if x[0] == "op" and x[1] in "([{": depth += 1
            elif x[0] == "op" and x[1] in ")]}":
                depth -= 1
                if depth == 0: return j
        return len(self.t) - 1

    def match_open(self, i):
        depth = 0
        for j in range(i, -1, -1):
            x = self.t[j]
            if x[0] == "op" and x[1] in ")]}": depth += 1
            elif x[0] == "op" and x[1] in "([{":
                depth -= 1
                if depth == 0: return j
        return 0


# ---------------------------------------------------------------------------
# types
def conv_type(tk, i):
    """convert the type starting at significant token i; returns (text, end index exclusive)"""
    t = tk.txt(i)
    if t == "[":
        c = tk.match_close(i)
        inner, j = conv_type(tk, tk.sig(i - 1) if tk.kind(i) == "ws" else i + 1 if tk.kind(i + 1) != "ws" else tk.sig(i))
        j2 = tk.sig(j - 1)
        if tk.txt(j2) == ";":
            # fixed-size: keep as is (rare)
            return join(tk.t[i:c + 1]), c + 1
        if "->" in inner or "|" in inner: inner = "(" + inner + ")"
        out = inner + "[]"
        return post_type(tk, out, c + 1)
    if t == "{":
        c = tk.match_close(i)
        k, j = conv_type(tk, tk.sig(i))
        colon = tk.sig(j - 1)
        v, j2 = conv_type(tk, tk.sig(colon))
        return post_type(tk, "{" + k + ": " + v + "}", c + 1)
    if t == "(":
        c = tk.match_close(i)
        parts = []
        j = tk.sig(i)
        while j < c:
            p, j = conv_type(tk, j)
            parts.append(p)
            j = tk.sig(j - 1)
            if tk.txt(j) == ",": j = tk.sig(j)
        return post_type(tk, "(" + ", ".join(parts) + ")", c + 1)
    if t in ("*", "**"):
        inner, j = conv_type(tk, tk.sig(i))
        return t + inner, j
    if t == "mut":
        inner, j = conv_type(tk, tk.sig(i))
        return "mut " + inner, j
    if t in ("fn", "cfn"):
        op = tk.sig(i)
        c = tk.match_close(op)
        parts = []
        j = tk.sig(op)
        while j < c:
            p, j = conv_type(tk, j)
            parts.append(p)
            j = tk.sig(j - 1)
            if tk.txt(j) == ",": j = tk.sig(j)
        nxt = tk.sig(c)
        ret = None
        end = c + 1
        if tk.txt(nxt) == "->":
            ret, end = conv_type(tk, tk.sig(nxt))
        if t == "cfn":
            s = "cfn(" + ", ".join(parts) + ")" + (" -> " + ret if ret else "")
        else:
            s = "(" + ", ".join(parts) + ") -> " + (ret if ret else "void")
        return post_type(tk, s, end)
    if tk.kind(i) == "ident":
        name = "f64" if t == "float" else t
        j = i + 1
        if tk.txt(j) == "." and tk.kind(j + 1) == "ident":
            name += "." + tk.txt(j + 1)
            j += 2
        if tk.txt(j) == "[":
            c = tk.match_close(j)
            parts = []
            k = tk.sig(j)
            while k < c:
                p, k = conv_type(tk, k)
                parts.append(p)
                k = tk.sig(k - 1)
                if tk.txt(k) == ",": k = tk.sig(k)
            name += "[" + ", ".join(parts) + "]"
            j = c + 1
        return post_type(tk, name, j)
    raise ValueError(f"cannot convert type at token {t!r}")


def post_type(tk, s, j):
    while tk.txt(j) == "?":
        s += "?"
        j += 1
    return s, j


# ---------------------------------------------------------------------------
def operand_left(tk, i, stop):
    """start index of the operand ending just before token i, stopping at `stop` tokens"""
    j = i - 1
    start = i
    while j >= 0:
        k, x = tk.t[j]
        if k in ("ws", "comment"):
            j -= 1
            continue
        if k == "nl": break
        if k == "op" and x in ")]}":
            j = tk.match_open(j)
            start = j
            j -= 1
            continue
        if k == "op" and x in "([{": break
        if (k in ("op", "ident") and x in stop): break
        start = j
        j -= 1
    return start


def operand_right(tk, i, stop):
    """end index (exclusive) of the operand starting after token i"""
    j = i + 1
    end = i + 1
    while j < len(tk.t):
        k, x = tk.t[j]
        if k in ("ws", "comment"):
            j += 1
            continue
        if k == "nl": break
        if k == "op" and x in "([{":
            j = tk.match_close(j)
            end = j + 1
            j += 1
            continue
        if k == "op" and x in ")]}": break
        if (k in ("op", "ident") and x in stop): break
        end = j + 1
        j += 1
    return end


RANGE_STOP = LOW_STOP | {"..", "..="}
XOR_STOP = LOW_STOP | {"|", "^", ".."}


# ---------------------------------------------------------------------------
class Converter:
    def __init__(self, path, enumerates, globals_):
        self.path = path
        self.enum = enumerates
        self.globals = globals_
        self.edits = []          # (start, end, text) on token indexes

    def run(self, src):
        src = self.pass_fn(src)
        src = self.pass_misc(src)
        while True:
            s2 = self.pass_fill(src)
            if s2 == src: break
            src = s2
        src = self.pass_ranges(src)
        while True:
            s2 = self.pass_loops(src)
            if s2 == src: break
            src = s2
        src = self.pass_decl(src)
        return src

    def pass_fill(self, src):
        tk = Toks(src)
        edits = []
        for i in range(len(tk.t)):
            k, x = tk.t[i]
            if k == "op" and x == "[":
                c = tk.match_close(i)
                depth = 0
                semi = -1
                for j in range(i + 1, c):
                    xx = tk.txt(j)
                    if xx in "([{": depth += 1
                    elif xx in ")]}": depth -= 1
                    elif xx == ";" and depth == 0: semi = j
                if semi > 0 and not self.is_type_bracket(tk, i):
                    edits.append((i, c + 1, "fill(" + join(tk.t[i + 1:semi]).strip() + ", " + join(tk.t[semi + 1:c]).strip() + ")"))
        return self.apply(tk, edits)

    # ---- helpers ----
    @staticmethod
    def apply(tk, edits):
        edits.sort(key=lambda e: e[0])
        out = []
        pos = 0
        for s, e, txt in edits:
            if s < pos: continue        # overlapping edit: skip (the first one wins)
            out.append(join(tk.t[pos:s]))
            out.append(txt)
            pos = e
        out.append(join(tk.t[pos:]))
        return "".join(out)

    # ---- functions: fn headers, lambdas, fn types, type annotations ----
    def pass_fn(self, src):
        tk = Toks(src)
        edits = []
        n = len(tk.t)
        i = 0
        while i < n:
            k, x = tk.t[i]
            if k == "ident" and x == "fn":
                e = self.conv_fn(tk, i)
                if e:
                    edits.append(e)
                    i = e[1]
                    continue
            elif k == "op" and x == ":" and self.is_decl_colon(tk, i):
                j = tk.sig(i)
                if tk.kind(j) not in ("nl", "eof") and tk.txt(j) not in ("=",):
                    try:
                        ty, end = conv_type(tk, j)
                        if self.typeish(tk, j, end):
                            edits.append((j, end, ty))
                            i = end
                            continue
                    except (ValueError, IndexError):
                        pass
            elif k == "ident" and x == "as":
                j = tk.sig(i)
                try:
                    ty, end = conv_type(tk, j)
                    edits.append((j, end, ty))
                    i = end
                    continue
                except ValueError:
                    pass
            elif k == "ident" and x == "float":
                edits.append((i, i + 1, "f64"))
            elif k == "str" and "float" in x and "{" in x:
                # inside interpolations: {float(n)}
                edits.append((i, i + 1, re.sub(r"(\{[^{}]*?)\bfloat\b", r"\1f64", x)))
            i += 1
        return self.apply(tk, edits)

    def typeish(self, tk, s, e):
        """could tokens s..e be a type (rather than an expression after a match arm's ':')?"""
        prev = None
        for j in range(s, e):
            k, x = tk.t[j]
            if k in ("ws", "comment"): continue
            if k in ("num", "str", "char", "nl"): return False
            if k == "ident" and x in ("true", "false", "none", "null", "and", "or", "not", "if", "return"): return False
            if k == "op" and x not in ("[", "]", "(", ")", "{", "}", ",", "?", ".", "->", "*", "**", ":"): return False
            if k == "op" and x in ("*", "**") and prev is not None and prev[0] == "ident" and prev[1] not in ("mut",): return False
            if k == "ident" and prev is not None and prev[0] == "ident" and prev[1] != "mut": return False
            prev = (k, x)
        return True

    def is_decl_colon(self, tk, i):
        """`name: Type` (declaration, field, parameter) rather than a block, dict or slice colon"""
        p = tk.sig(i, -1)
        if tk.kind(p) != "ident": return False
        if tk.txt(p) in ("else", "loop") or tk.txt(p) in KW_STMT: return False
        pp = tk.sig(p, -1)
        ppx = tk.txt(pp)
        if tk.kind(pp) == "nl" or pp < 0 or ppx in ("(", ",", "mut", "let", "const", "struct") or tk.kind(pp) == "ws":
            pass
        else:
            return False
        if ppx == ",":
            # a parameter only inside (...), not a dict {a: 1, b: 2}
            o = tk.match_open(self.enclosing(tk, p))
            return tk.txt(self.enclosing(tk, p)) == "("
        if ppx == "(":
            return True
        # statement start: next must look like a type, not an expression/block
        j = tk.sig(i)
        if tk.kind(j) in ("nl", "eof", "comment"): return False
        # a struct field / typed declaration has the type then '=' or end of line
        return True

    def enclosing(self, tk, i):
        depth = 0
        for j in range(i, -1, -1):
            x = tk.t[j]
            if x[0] == "op" and x[1] in ")]}": depth += 1
            elif x[0] == "op" and x[1] in "([{":
                if depth == 0: return j
                depth -= 1
        return -1

    def conv_params(self, tk, op, c):
        """(params) -> converted text of the parameter list (with parens)"""
        parts = []
        j = tk.sig(op)
        while j < c:
            # [mut] name [: [mut] Type] [= default]
            start = j
            words = []
            if tk.txt(j) == "mut":
                words.append("mut ")
                j = tk.sig(j)
            name = tk.txt(j)
            words.append(name)
            j = tk.sig(j)
            if tk.txt(j) == ":":
                ty, e = conv_type(tk, tk.sig(j))
                words.append(": " + ty)
                j = tk.sig(e - 1)
            if tk.txt(j) == "=":
                # default value: copy tokens to the next top-level comma
                ds = tk.sig(j)
                de = ds
                depth = 0
                while de < c:
                    xx = tk.txt(de)
                    if xx in "([{": depth += 1
                    elif xx in ")]}": depth -= 1
                    elif xx == "," and depth == 0: break
                    de += 1
                words.append(" = " + join(tk.t[ds:de]).strip())
                j = de
            parts.append("".join(words))
            if tk.txt(j) == ",": j = tk.sig(j)
            elif j < c and j == start: break
        return "(" + ", ".join(parts) + ")"

    def conv_fn(self, tk, i):
        j = tk.sig(i)
        t = tk.txt(j)
        # lambda or function type: fn(...)
        if t == "(":
            c = tk.match_close(j)
            nxt = tk.sig(c)
            ret = ""
            end = c + 1
            k = nxt
            if tk.txt(nxt) == "->":
                ty, end = conv_type(tk, tk.sig(nxt))
                ret = " -> " + ty
                k = tk.sig(end - 1)
            if tk.txt(k) == ":":
                # lambda
                return (i, end, self.conv_params(tk, j, c) + ret)
            ty, end = conv_type(tk, i)
            return (i, end, ty)
        # declaration: fn name[T](params) -> R:
        prefix = ""
        p = tk.sig(i, -1)
        name_end = j + 1
        if tk.kind(j) == "ident":
            name = t
        elif t == "[":
            # fn [](...) or fn []=(...)
            c = tk.match_close(j)
            name = "[]"
            name_end = c + 1
            if tk.txt(name_end) == "=":
                name = "[]="
                name_end += 1
            name = "(" + name + ")"
        else:
            # operator: fn +(...), fn ==(...)
            name = "(" + t + ")"
        tps = ""
        k = name_end
        if tk.txt(k) == "[":
            c = tk.match_close(k)
            tps = join(tk.t[k:c + 1])
            k = c + 1
        if tk.txt(k) != "(": raise ValueError(f"{self.path}: unexpected fn form near {join(tk.t[i:k+3])!r}")
        c = tk.match_close(k)
        params = self.conv_params(tk, k, c)
        end = c + 1
        ret = ""
        nxt = tk.sig(c)
        if tk.txt(nxt) == "->":
            ty, end = conv_type(tk, tk.sig(nxt))
            ret = " -> " + ty
        return (i, end, f"{name}{tps} = {params}{ret}")

    # ---- small things: if :=, **, ^, [x; n], use, while-let ----
    def pass_misc(self, src):
        tk = Toks(src)
        edits = []
        n = len(tk.t)
        for i in range(n):
            k, x = tk.t[i]
            if k == "ident" and x in ("if", "while"):
                j = tk.sig(i)
                if tk.kind(j) == "ident" and tk.txt(tk.sig(j)) == ":=":
                    d = tk.sig(j)
                    if x == "if": edits.append((i, d + 1, f"if let {tk.txt(j)} ="))
                    else: edits.append((i, d + 1, f"loop let {tk.txt(j)} ="))
            elif k == "char" and x in ("'{'", "'}'"):
                edits.append((i, i + 1, "'" + x[1] * 2 + "'"))
            elif k == "op" and x == "**":
                # power (binary) only; `**T` is a pointer type
                p = tk.sig(i, -1)
                if tk.kind(p) in ("ident", "num") and tk.txt(p) not in ("as", "return", "in", "and", "or", "not") or tk.txt(p) in (")", "]"):
                    edits.append((i, i + 1, "^"))
            elif k == "op" and x in ("^", "^="):
                if x == "^=":
                    edits.append((i, i + 1, "xor="))
                else:
                    s = operand_left(tk, i, XOR_STOP)
                    e = operand_right(tk, i, XOR_STOP)
                    edits.append((s, e, "(" + join(tk.t[s:i]).strip() + " xor " + join(tk.t[i + 1:e]).strip() + ")"))
            elif k == "ident" and x == "use":
                j = tk.sig(i)
                if tk.kind(j) == "ident" and tk.kind(tk.sig(i, -1)) in ("nl",) or i == 0:
                    if tk.kind(j) == "ident" and os.path.exists(os.path.join(os.path.dirname(self.path), tk.txt(j) + ".jot")):
                        edits.append((j, j + 1, f"'{tk.txt(j)}.jot'"))
        return self.apply(tk, edits)

    def is_type_bracket(self, tk, i):
        p = tk.sig(i, -1)
        return tk.txt(p) in (":", "->")

    # ---- ranges: old a..b excludes b ----
    def pass_ranges(self, src):
        tk = Toks(src)
        edits = []
        n = len(tk.t)
        for i in range(n):
            k, x = tk.t[i]
            if k != "op" or x not in ("..", "..="): continue
            incl = x == "..="
            o = self.enclosing(tk, i)
            # slices: xs[a..b] / xs[..b] / xs[a..]
            if o >= 0 and tk.txt(o) == "[" and tk.kind(o - 1) in ("ident", "op") and tk.txt(o - 1) not in ("(", ",", "[", "=", ":", "return", "in") and tk.kind(o - 1) != "ws":
                c = tk.match_close(o)
                s = operand_left(tk, i, RANGE_STOP)
                e = operand_right(tk, i, RANGE_STOP)
                if s == o + 1 and e >= c - 0 or e == c:
                    if incl: edits.append((i, i + 1, ".."))
                    elif tk.sig(i) != c:
                        edits.append((i, i + 1, ".."))
                        edits.append((c, c + 1, ")"))
                    continue
            # match pattern: a..b: (integer literals) -> inclusive a..b-1
            s = operand_left(tk, i, RANGE_STOP)
            e = operand_right(tk, i, RANGE_STOP)
            after = tk.sig(e - 1)
            before = tk.sig(s, -1)
            lo = join(tk.t[s:i]).strip()
            hi = join(tk.t[i + 1:e]).strip()
            if tk.txt(after) == ":" and tk.kind(before) in ("nl", "ws") and re.fullmatch(r"-?\d+", hi or "x") and tk.txt(tk.sig(after)) != "":
                line_start = before
                if incl: edits.append((s, e, f"{lo}..{hi}"))
                else: edits.append((s, e, f"{lo}..{int(hi) - 1}"))
                continue
            if not hi:
                continue            # open range a..
            if incl: edits.append((s, e, f"{lo}..{hi}"))
            else: edits.append((s, e, f"[{lo}..{hi})"))
        return self.apply(tk, edits)

    # ---- loops and comprehensions ----
    def pass_loops(self, src):
        tk = Toks(src)
        edits = []
        n = len(tk.t)
        i = 0
        # comprehensions first: [ELEM for ... ]
        for i in range(n):
            k, x = tk.t[i]
            if k == "op" and x == "[":
                c = tk.match_close(i)
                depth = 0
                fpos = -1
                for j in range(i + 1, c):
                    xx = tk.t[j]
                    if xx[0] == "op" and xx[1] in "([{": depth += 1
                    elif xx[0] == "op" and xx[1] in ")]}": depth -= 1
                    elif xx[0] == "ident" and xx[1] == "for" and depth == 0:
                        fpos = j
                        break
                if fpos > 0:
                    edits.append((i, c + 1, self.conv_comprehension(tk, i, fpos, c)))
        for i in range(n):
            k, x = tk.t[i]
            if k == "ident" and x == "for":
                if any(s <= i < e for s, e, _ in edits): continue
                p = tk.sig(i, -1)
                if tk.kind(p) != "nl" and p >= 0 and tk.txt(p) not in (":",):
                    continue
                e = self.conv_for_header(tk, i)
                if e: edits.append(e)
            elif k == "ident" and x == "while":
                if any(s <= i < e for s, e, _ in edits): continue
                edits.append((i, i + 1, "loop"))
        return self.apply(tk, edits)

    def line_col(self, tk, i):
        line = 1 + sum(t[1].count("\n") for t in tk.t[:i])
        return line

    def conv_for_header(self, tk, i):
        """for VARS in EXPR:  ->  loop ..."""
        j = tk.sig(i)
        mut = ""
        if tk.txt(j) == "mut":
            mut = "mut "
            j = tk.sig(j)
        vars_ = [tk.txt(j)]
        j = tk.sig(j)
        if tk.txt(j) == ",":
            j = tk.sig(j)
            vars_.append(tk.txt(j))
            j = tk.sig(j)
        if tk.txt(j) != "in": return None
        line = self.line_col(tk, i)
        if len(vars_) == 2 and (os.path.basename(self.path), line) in self.enum:
            return (i, j + 1, f"loop {vars_[0]} in 0.. and {mut}{vars_[1]} in")
        return (i, j + 1, f"loop {mut}{', '.join(vars_)} in")

    def conv_comprehension(self, tk, o, fpos, c):
        elem = join(tk.t[o + 1:fpos]).strip()
        clauses = []
        j = fpos
        cur = None
        while j < c:
            x = tk.txt(j)
            if tk.kind(j) == "ident" and x in ("for", "if") and self.top_level(tk, j, o):
                if cur: clauses.append(cur)
                cur = [x, j, None]
            j += 1
        if cur: clauses.append(cur)
        out = []
        for idx, cl in enumerate(clauses):
            end = clauses[idx + 1][1] if idx + 1 < len(clauses) else c
            body = join(tk.t[cl[1] + 1:end]).strip()
            if cl[0] == "for":
                m = re.match(r"(\w+)(?:\s*,\s*(\w+))?\s+in\s+(.*)$", body, re.S)
                if not m: raise ValueError(f"{self.path}: comprehension clause {body!r}")
                a, b, it = m.group(1), m.group(2), m.group(3)
                line = self.line_col(tk, cl[1])
                if b and (os.path.basename(self.path), line) in self.enum:
                    out.append(f"loop {a} in 0.. and {b} in {it}: ")
                elif b:
                    out.append(f"loop {a}, {b} in {it}: ")
                else:
                    out.append(f"loop {a} in {it}: ")
            else:
                out.append(f"if {body}: ")
        return "[" + "".join(out) + elem + "]"

    def top_level(self, tk, j, o):
        return self.enclosing(tk, j) == o

    # ---- declarations: x := v ----
    def pass_decl(self, src):
        tk = Toks(src)
        edits = []
        n = len(tk.t)
        # scopes by indentation: list of (indent, set)
        scopes = [(-1, set(self.globals))]
        line_indent = 0
        at_line_start = True
        cur_fn_indent = None
        top_declared = set()
        i = 0
        while i < n:
            k, x = tk.t[i]
            if k == "nl":
                at_line_start = True
                i += 1
                continue
            if at_line_start:
                if k in ("ws", "comment"):
                    if k == "ws" and tk.kind(i + 1) not in ("nl", "comment"):
                        line_indent = len(x.replace("\t", "    "))
                    i += 1
                    continue
                if k != "ws":
                    if tk.kind(i - 1) != "ws": line_indent = 0
                    # pop scopes deeper than this line
                    while len(scopes) > 1 and scopes[-1][0] >= line_indent: scopes.pop()
                    at_line_start = False
                    self.note_line(tk, i, scopes, line_indent)
            if k == "op" and x == ":=":
                # NAME := or A, B :=
                names = []
                j = tk.sig(i, -1)
                names.append(tk.txt(j))
                first = j
                p = tk.sig(j, -1)
                while tk.txt(p) == ",":
                    q = tk.sig(p, -1)
                    names.insert(0, tk.txt(q))
                    first = q
                    p = tk.sig(q, -1)
                if line_indent == 0:
                    # top level: only an earlier top-level declaration in this file counts
                    visible = any(nm in top_declared for nm in names if nm != "_")
                    top_declared.update(names)
                else:
                    visible = any(nm in sc[1] for sc in scopes for nm in names if nm != "_")
                in_struct = self.in_struct(tk, first)
                if visible and not in_struct:
                    edits.append((first, first, "let "))
                edits.append((i, i + 1, "="))
                for nm in names: scopes[-1][1].add(nm)
            i += 1
        return self.apply(tk, edits)

    def note_line(self, tk, i, scopes, indent):
        """a line starts at token i: open scopes for function bodies / loops (params, loop vars)"""
        n0 = len(scopes)
        self.note_line2(tk, i, scopes, indent)
        if len(scopes) == n0:
            # any other block opener (if/else/match/...) gets its own scope too
            j = i
            last = None
            while j < len(tk.t) and tk.kind(j) != "nl":
                if tk.kind(j) not in ("ws", "comment"): last = tk.txt(j)
                j += 1
            if last == ":": scopes.append((indent, set()))

    def note_line2(self, tk, i, scopes, indent):
        x = tk.txt(i)
        if x == "loop":
            # loop vars are visible in the body
            names = set()
            j = tk.sig(i)
            while j < len(tk.t) and tk.kind(j) != "nl":
                if tk.kind(j) == "ident" and tk.txt(tk.sig(j)) in ("in", ","):
                    names.add(tk.txt(j))
                j += 1
            scopes.append((indent, names))
            return
        # name = (params) ... : function declaration
        if tk.kind(i) == "ident" or tk.txt(i) == "(":
            j = i
            while j < len(tk.t) and tk.kind(j) != "nl" and tk.txt(j) != "=":
                j += 1
            if tk.txt(j) == "=" and tk.txt(tk.sig(j)) == "(":
                c = Toks.match_close(tk, tk.sig(j))
                params = set()
                k = tk.sig(j)
                depth = 0
                prev = "("
                for kk in range(k + 1, c):
                    xx = tk.t[kk]
                    if xx[0] == "op" and xx[1] in "([{": depth += 1
                    elif xx[0] == "op" and xx[1] in ")]}": depth -= 1
                    elif xx[0] == "ident" and depth == 0 and prev in ("(", ",", "mut"): params.add(xx[1])
                    if xx[0] not in ("ws", "comment"): prev = xx[1]
                if self.at_top(scopes, indent) and indent == 0:
                    scopes.append((indent, params))
                else:
                    scopes.append((indent, params))

    def at_top(self, scopes, indent):
        return True

    def in_struct(self, tk, i):
        # is the line inside a struct body? look back for the governing 'struct' line
        j = i
        indent = None
        # find this line's indentation
        k = j
        while k > 0 and tk.kind(k - 1) != "nl": k -= 1
        ind = len(tk.t[k][1]) if tk.kind(k) == "ws" else 0
        while k > 0:
            k -= 1
            while k > 0 and tk.kind(k - 1) != "nl": k -= 1
            lind = len(tk.t[k][1]) if tk.kind(k) == "ws" else 0
            first = k if tk.kind(k) != "ws" else k + 1
            if tk.kind(first) in ("nl", "comment"): continue
            if lind < ind:
                return tk.txt(first) == "struct"
        return False


def load_enum(path):
    out = set()
    if not path or not os.path.exists(path): return out
    for line in open(path):
        m = re.match(r"MIGRATE enumerate (.*):(\d+):\d+", line.strip())
        if m: out.add((os.path.basename(m.group(1)), int(m.group(2))))
    return out


def collect_globals(paths):
    g = set()
    for p in paths:
        for line in open(p):
            m = re.match(r"([A-Za-z_]\w*)\s*(:=|:\s)", line)
            if m: g.add(m.group(1))
    return g


if __name__ == "__main__":
    args = sys.argv[1:]
    info = None
    gl = []
    files = []
    i = 0
    while i < len(args):
        if args[i] == "--info": info = args[i + 1]; i += 2
        elif args[i] == "--globals": gl.append(args[i + 1]); i += 2
        else: files.append(args[i]); i += 1
    enum = load_enum(info)
    lib_files = []
    for d in gl:
        for root, _, fs in os.walk(d):
            lib_files += [os.path.join(root, f) for f in fs if f.endswith(".jot")]
    gset = collect_globals(lib_files)
    for f in files:
        src = open(f).read()
        own = collect_globals([f])
        out = Converter(f, enum, gset | own).run(src)
        open(f, "w").write(out)
        print("converted", f)
