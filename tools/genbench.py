#!/usr/bin/env python3
"""Generate a large synthetic program (Jot + equivalent C) for compile-speed benchmarks.
usage: genbench.py N_FUNCS out_prefix"""
import sys, random
n = int(sys.argv[1]); out = sys.argv[2]
random.seed(1)
jot, c = [], []
c.append("#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <math.h>")
c.append("typedef struct { double x, y; long id; } Item;")
jot.append("struct Item:\n    x: float\n    y: float\n    id: int\n")
for i in range(n):
    k = random.randint(2, 9)
    jot.append(f"""fn work{i}(a: int, b: float, items: [Item]) -> float:
    total := 0.0
    count := 0
    for j in 0..a:
        v := float(j * {k}) + b
        if v > {k * 10}.0:
            total += v * 0.5
        else if j % {k} == 0:
            total -= v / {k}.0
        else:
            count += 1
    for it in items:
        if it.id % {k} == 1:
            total += it.x * it.y
        else:
            total += sqrt(abs(it.x - it.y))
    s := "item {i}"
    if len(s) > {k}:
        total += float(len(s))
    while count > {k}:
        count -= {k + 1}
        total *= 1.0001
    total + float(count)
""")
    c.append(f"""double work{i}(long a, double b, Item *items, long n) {{
    double total = 0.0;
    long count = 0;
    for (long j = 0; j < a; j++) {{
        double v = (double)(j * {k}) + b;
        if (v > {k * 10}.0) {{
            total += v * 0.5;
        }} else if (j % {k} == 0) {{
            total -= v / {k}.0;
        }} else {{
            count += 1;
        }}
    }}
    for (long q = 0; q < n; q++) {{
        Item it = items[q];
        if (it.id % {k} == 1) {{
            total += it.x * it.y;
        }} else {{
            total += sqrt(fabs(it.x - it.y));
        }}
    }}
    char s[64];
    snprintf(s, sizeof s, "item {i}");
    if ((long)strlen(s) > {k}) {{
        total += (double)strlen(s);
    }}
    while (count > {k}) {{
        count -= {k + 1};
        total *= 1.0001;
    }}
    return total + (double)count;
}}""")
jot.append("items: [Item]\nfor i in 0..100: items.push(Item(float(i), float(i) * 0.5, i))\nacc := 0.0")
c.append("int main(void) {\n    Item items[100];\n    for (long i = 0; i < 100; i++) { items[i].x = i; items[i].y = i * 0.5; items[i].id = i; }\n    double acc = 0.0;")
for i in range(n):
    jot.append(f"acc += work{i}({i % 50}, {i}.0, items)")
    c.append(f"    acc += work{i}({i % 50}, {i}.0, items, 100);")
jot.append('print("{acc:.3}")')
c.append('    printf("%.3f\\n", acc);\n    return 0;\n}')
open(out + ".jot", "w").write("\n".join(jot) + "\n")
open(out + ".c", "w").write("\n".join(c) + "\n")
