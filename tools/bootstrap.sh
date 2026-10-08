#!/bin/sh
# Build the Jot compiler from scratch: C bootstrap -> jot1 -> jot2 -> jot3 (must equal jot2).
set -e
cd "$(dirname "$0")/.."
make -s -C stage0
mkdir -p bin
export JOT_LIB="$PWD/lib"
./stage0/jot0 compiler/main.jot -o /tmp/jot1
/tmp/jot1 build compiler/main.jot -o /tmp/jot2
/tmp/jot2 build compiler/main.jot -o /tmp/jot3
if cmp -s /tmp/jot2 /tmp/jot3; then
    rm -f bin/jot && cp /tmp/jot2 bin/jot      # (rm: an editor may be running the old one)
    echo "bootstrap ok: bin/jot ($(stat -c %s bin/jot) bytes), self-compile is a fixed point"
else
    echo "bootstrap FAILED: jot2 and jot3 differ"
    exit 1
fi
