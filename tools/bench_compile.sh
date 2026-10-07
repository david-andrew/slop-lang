#!/bin/sh
# usage: tools/bench_compile.sh [compiler] [file] -- best of 9 compiles, CPU time (user+sys)
JOT=${1:-bin/jot}
F=${2:-bench/big.jot}
[ -f bench/big.jot ] || python3 tools/genbench.py
export JOT_LIB=${JOT_LIB:-$PWD/lib}
best=999
for i in 1 2 3 4 5 6 7 8 9; do
  rm -f /tmp/jot_bench_out
  t=$( { /usr/bin/time -f "%U %S" $JOT build $F -o /tmp/jot_bench_out >/dev/null || echo FAIL; } 2>&1 | tail -1)
  if [ "$t" = FAIL ] || ! [ -x /tmp/jot_bench_out ]; then echo "compile failed"; exit 1; fi
  best=$(echo "$t $best" | awk '{s = $1 + $2; print (s < $3) ? s : $3}')
done
lines=$(wc -l < $F)
echo "$F: $lines lines, best $best s CPU, $(echo "$lines $best" | awk '{printf "%d", $1/$2}') lines/s"
