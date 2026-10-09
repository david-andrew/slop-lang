#!/bin/sh
# Build the Sloppy compiler from scratch: C bootstrap -> sloppy1 -> sloppy2 -> sloppy3 (must equal sloppy2).
set -e
cd "$(dirname "$0")/.."
make -s -C stage0
mkdir -p bin
export SLOPPY_LIB="$PWD/lib"
./stage0/sloppy0 compiler/main.jo -o /tmp/sloppy1
/tmp/sloppy1 build compiler/main.jo -o /tmp/sloppy2
/tmp/sloppy2 build compiler/main.jo -o /tmp/sloppy3
if cmp -s /tmp/sloppy2 /tmp/sloppy3; then
    rm -f bin/sloppy && cp /tmp/sloppy2 bin/sloppy      # (rm: an editor may be running the old one)
    echo "bootstrap ok: bin/sloppy ($(stat -c %s bin/sloppy) bytes), self-compile is a fixed point"
else
    echo "bootstrap FAILED: sloppy2 and sloppy3 differ"
    exit 1
fi
