#!/usr/bin/env bash
# Validate and package the Devpost submission artifact set.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT=""
MODE="check"

usage() {
    cat <<'EOF'
usage: scripts/package-devpost.sh [--root PATH] [--check] [--output FILE.zip] [--list-required]

--check          Validate required files only (default).
--output FILE    Validate, then write a zip with the required files.
--list-required  Print required relative paths and exit.
EOF
}

required_files() {
    cat <<'EOF'
README.md
LICENSE
docs/ARCHITECTURE.md
docs/ARCHITECTURE_DIAGRAM.svg
docs/DEVPOST_COMPLIANCE.md
docs/FAILURE_MODES.md
docs/CASE_ISOLATION.md
docs/RELEASE.md
submission/execution-logs/case_001.jsonl
submission/execution-logs/case_002.jsonl
submission/execution-logs/case_003.jsonl
EOF
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --root)
            ROOT="$2"
            shift 2
            ;;
        --check)
            MODE="check"
            shift
            ;;
        --output)
            MODE="zip"
            OUTPUT="$2"
            shift 2
            ;;
        --list-required)
            required_files
            exit 0
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            usage >&2
            exit 2
            ;;
    esac
done

missing=0
while IFS= read -r rel; do
    [ -z "$rel" ] && continue
    if [ ! -f "$ROOT/$rel" ]; then
        printf 'missing: %s\n' "$rel" >&2
        missing=1
    fi
done < <(required_files)

if [ "$missing" -ne 0 ]; then
    exit 1
fi

if [ "$MODE" = "check" ]; then
    printf 'Devpost artifact check passed for %s\n' "$ROOT"
    exit 0
fi

if [ -z "$OUTPUT" ]; then
    printf 'error: --output requires a zip path\n' >&2
    exit 2
fi

ROOT="$ROOT" OUTPUT="$OUTPUT" python - <<'PY'
from __future__ import annotations

import os
import subprocess
import zipfile
from pathlib import Path

root = Path(os.environ["ROOT"]).resolve()
output = Path(os.environ["OUTPUT"]).resolve()
result = subprocess.run(
    [str(root / "scripts" / "package-devpost.sh"), "--root", str(root), "--list-required"],
    check=True,
    capture_output=True,
    text=True,
)
output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for rel in result.stdout.splitlines():
        if rel:
            zf.write(root / rel, rel)
print(f"wrote {output}")
PY
