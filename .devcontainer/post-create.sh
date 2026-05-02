#!/usr/bin/env bash
# VERDICT devcontainer post-create — runs once per container creation.
# Idempotent (uv/git submodule are no-ops if already done). Mirrors the
# repo-bootstrap section of scripts/bootstrap-dev.sh §5.
set -euo pipefail

cd /workspaces/Verdict

echo "==> initializing protocol-sift submodule"
git submodule update --init --recursive

echo "==> uv sync --all-extras"
uv sync --all-extras

echo "==> verifying MCP runtimes"
# .mcp.json uses npx (5 servers) + uvx (mitre-attack). Both must be on PATH.
command -v npx  >/dev/null || { echo "FAIL: npx missing"; exit 1; }
command -v uvx  >/dev/null || { echo "FAIL: uvx missing"; exit 1; }

echo "==> license + secret guard on .mcp.json (CLAUDE.md §3.8 + §3.9)"
# Match the secret keywords, then exclude (a) env-var refs ${FOO}, (b) the
# underscore-prefixed JSON comment fields (_comment, _origin, _purpose) we
# use for inline documentation per docs/MCP_FRAMEWORK.md §4.
if grep -E -i '(api[_-]?key|secret|token|password|BEGIN.*PRIVATE)' .mcp.json \
     | grep -vE '"_(comment|origin|purpose)"|\$\{[A-Z_]+\}' >/dev/null; then
    echo "FAIL: literal credential in .mcp.json — must use \${VAR} refs only"
    exit 1
fi

echo "==> toolchain summary"
printf "  uv     %s\n" "$(uv --version)"
printf "  python %s\n" "$(uv run python --version 2>&1 | awk '{print $2}')"
printf "  node   %s\n" "$(node --version)"
printf "  pnpm   %s\n" "$(pnpm --version)"
printf "  rustc  %s\n" "$(rustc --version | awk '{print $2}')"

echo ""
echo "Container ready. Next:"
echo "  - Bring up Langfuse on the HOST: cd infra/langfuse && docker compose up -d"
echo "  - Microsandbox + SGLang are HOST-side (need /dev/kvm + GPU); see .devcontainer/README.md"
echo "  - claude mcp list   # all 6 MCPs should resolve via npx/uvx"
