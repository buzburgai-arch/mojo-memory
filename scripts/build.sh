#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
: "${MOJO_BIN:=mojo}"
mkdir -p build
"$MOJO_BIN" build worker.mojo -o build/mojo-memory
"$MOJO_BIN" run test_core.mojo
