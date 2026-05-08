#!/usr/bin/env bash
# Install VERDICT's local Python/dev hooks and report host credential readiness.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v uv >/dev/null 2>&1; then
    echo "error: uv is required. Run scripts/bootstrap-dev.sh first." >&2
    exit 1
fi

export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

echo "==> Detecting host-side cloud credential path"
credential_status="$(python -m verdict.cli.credentials --json)"
echo "$credential_status"
if printf '%s' "$credential_status" | grep -q '"cloud_available": true'; then
    echo "    cloud credential path detected"
else
    echo "    no cloud credential path detected; AIRGAP may still work if SGLang is reachable"
fi

echo "==> Syncing Python dependencies"
uv sync --all-extras

echo "==> Installing pre-commit hooks"
uv run pre-commit install --install-hooks

if [ -f Cargo.toml ]; then
    echo "==> Building Rust workspace"
    cargo build --workspace
fi

if [ -f pnpm-lock.yaml ]; then
    echo "==> Installing Node dependencies"
    pnpm install --frozen-lockfile
fi

echo "==> Running VERDICT pre-flight"
if uv run verdict doctor; then
    echo "    verdict doctor passed"
else
    echo "    verdict doctor reported blockers; configure .env values and real services, then rerun"
fi
