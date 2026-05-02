#!/usr/bin/env bash
# install.sh — Verdict bootstrap with three-credential-path detection (W1.A.1).
#
# Credential precedence (highest to lowest):
#   1. ANTHROPIC_API_KEY env var          → mode=api_key
#   2. CLAUDE_CODE_OAUTH_TOKEN env var    → mode=oauth
#   3. ~/.claude/credentials.json         → mode=oauth_interactive
#   4. ANTHROPIC_API env var (legacy)     → mode=api_key
#
# On credential detection the script:
#   - Prints  "credential_mode=<mode>" to stdout (machine-readable).
#   - Proceeds with Python env setup via uv and pre-commit hooks.
#
# Security (CLAUDE.md §3.9):
#   - Credential VALUES are never echoed, stored in logs, or baked into images.
#   - Only the MODE string (api_key / oauth / oauth_interactive) is printed.
#   - OAuth tokens are NOT redistributable per Anthropic commercial terms.
#
# Usage:
#   bash scripts/install.sh           # auto-detect credentials
#   ANTHROPIC_API_KEY=sk-… bash scripts/install.sh
#
# Idempotent: safe to re-run.

set -euo pipefail

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
    BOLD='\033[1m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'
    RED='\033[0;31m'; YELLOW='\033[0;33m'; DIM='\033[2m'; RESET='\033[0m'
else
    BOLD=''; GREEN=''; CYAN=''; RED=''; YELLOW=''; DIM=''; RESET=''
fi

step() { printf "\n${BOLD}${CYAN}==>${RESET} ${BOLD}%s${RESET}\n" "$*"; }
info() { printf "    %s\n" "$*"; }
ok()   { printf "    ${GREEN}ok${RESET}  %s\n" "$*"; }
warn() { printf "    ${YELLOW}warn${RESET} %s\n" "$*"; }
die()  { printf "\n${RED}error${RESET} %s\n" "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Three-credential-path detection (W1.A.1.b)
# Returns the detected mode as a string, or empty string if none found.
# ---------------------------------------------------------------------------
detect_credential_mode() {
    # Path 1: ANTHROPIC_API_KEY (canonical, highest priority)
    if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
        printf "api_key"
        return 0
    fi

    # Path 2: CLAUDE_CODE_OAUTH_TOKEN (OAuth bearer token in env)
    if [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
        printf "oauth"
        return 0
    fi

    # Path 3: ~/.claude/credentials.json (interactive OAuth stored on disk)
    local creds_file="${HOME}/.claude/credentials.json"
    if [ -f "${creds_file}" ]; then
        # Check that the file contains a non-empty oauth_token field.
        # python3 avoids an extra jq dependency.
        local has_token
        has_token=$(python3 -c "
import json, sys
try:
    data = json.loads(open(sys.argv[1]).read())
    print('yes' if data.get('oauth_token', '') else 'no')
except Exception:
    print('no')
" "${creds_file}" 2>/dev/null || printf "no")
        if [ "${has_token}" = "yes" ]; then
            printf "oauth_interactive"
            return 0
        fi
    fi

    # Path 4: ANTHROPIC_API legacy alias (lowest precedence)
    if [ -n "${ANTHROPIC_API:-}" ]; then
        printf "api_key"
        return 0
    fi

    # No credential found
    printf ""
    return 0
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
step "Verdict credential detection"

CRED_MODE="$(detect_credential_mode)"

if [ -z "${CRED_MODE}" ]; then
    warn "No credentials detected."
    info "Set one of the following (see .env.example):"
    info "  ANTHROPIC_API_KEY=sk-...         (highest priority)"
    info "  CLAUDE_CODE_OAUTH_TOKEN=...      (OAuth bearer)"
    info "  Run 'claude' to create ~/.claude/credentials.json"
    info "  ANTHROPIC_API=sk-...             (legacy alias)"
    info ""
    info "Continuing install without cloud credentials."
    info "Air-gap mode (SGLang only) will still work."
    CRED_MODE="none"
fi

# Machine-readable output — consumed by verdict doctor and CI.
printf "credential_mode=%s\n" "${CRED_MODE}"
ok "credential mode: ${CRED_MODE}"

# ---------------------------------------------------------------------------
# Python environment (uv)
# ---------------------------------------------------------------------------
step "Python environment (uv)"

if ! command -v uv >/dev/null 2>&1; then
    die "uv not found. Run scripts/bootstrap-dev.sh first."
fi

ok "uv found: $(uv --version)"
info "syncing Python dependencies"
uv sync --quiet
ok "Python env ready"

# ---------------------------------------------------------------------------
# Pre-commit hooks
# ---------------------------------------------------------------------------
step "Pre-commit hooks"

if command -v pre-commit >/dev/null 2>&1 || uv run pre-commit --version >/dev/null 2>&1; then
    if [ -f ".pre-commit-config.yaml" ]; then
        uv run pre-commit install --install-hooks --quiet
        ok "pre-commit hooks installed"
    else
        warn ".pre-commit-config.yaml not yet present (W1.A.9); skipping hook install"
    fi
else
    warn "pre-commit not available; run 'uv sync' then retry"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
printf "\n${BOLD}${GREEN}Verdict install complete.${RESET}\n"
printf "  credential_mode=%s\n" "${CRED_MODE}"
printf "  Next: verdict doctor\n\n"
