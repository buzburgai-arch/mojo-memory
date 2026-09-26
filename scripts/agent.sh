#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ ! -x build/mojo-memory ]]; then
    printf '%s\n' 'Build first: MOJO_BIN=/path/to/mojo bash scripts/build.sh' >&2
    exit 1
fi
exec ./build/mojo-memory "$@"
