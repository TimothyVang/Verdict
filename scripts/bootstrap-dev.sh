#!/usr/bin/env bash
# bootstrap-dev.sh — install the Verdict contributor toolchain.
#
# Pinned versions (must match CONTRIBUTING.md Step 2):
#   Python 3.11.x   via uv
#   uv              latest
#   Node 20.x LTS   via NodeSource apt repo
#   pnpm            latest stable
#   Microsandbox    v0.4.x (libkrun-backed microVM runtime)
#
# Idempotent: safe to re-run. Skips any component already at the required version.
# Linux/SIFT VM (Ubuntu 22.04 / 24.04) is canonical. macOS is best-effort
# (Microsandbox + SGLang require Linux/KVM, so full e2e still needs the SIFT VM).
#
# This script does NOT replace scripts/install.sh (W1.A.1 — credential path
# detection) or scripts/verdict-install.sh (Protocol SIFT layer). It only sets
# up the language runtimes a contributor needs to build, test, and lint.

set -euo pipefail

# ---------------------------------------------------------------------------
# Pinned versions
# ---------------------------------------------------------------------------
PYTHON_VERSION="3.11"
NODE_MAJOR="20"

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
    BOLD='\033[1m'; DIM='\033[2m'; GREEN='\033[0;32m'
    CYAN='\033[0;36m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; RESET='\033[0m'
else
    BOLD=''; DIM=''; GREEN=''; CYAN=''; RED=''; YELLOW=''; RESET=''
fi

step()  { printf "\n${BOLD}${CYAN}==>${RESET} ${BOLD}%s${RESET}\n" "$*"; }
info()  { printf "    %s\n" "$*"; }
ok()    { printf "    ${GREEN}ok${RESET}  %s\n" "$*"; }
skip()  { printf "    ${DIM}skip${RESET} %s\n" "$*"; }
warn()  { printf "    ${YELLOW}warn${RESET} %s\n" "$*"; }
die()   { printf "\n${RED}error${RESET} %s\n" "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Platform detect
# ---------------------------------------------------------------------------
OS="$(uname -s)"
case "$OS" in
    Linux)  PLATFORM="linux" ;;
    Darwin) PLATFORM="darwin" ;;
    *)      die "unsupported platform: $OS (Linux/SIFT VM canonical, macOS best-effort)" ;;
esac

# ---------------------------------------------------------------------------
# Sudo: cache once up front so the rest runs unattended
# ---------------------------------------------------------------------------
NEEDS_SUDO=0
if [ "$PLATFORM" = "linux" ]; then
    NEEDS_SUDO=1
    if [ "$(id -u)" -ne 0 ]; then
        if ! command -v sudo >/dev/null 2>&1; then
            die "sudo is required on Linux for Node + system packages"
        fi
        info "caching sudo credentials (Node 20 + apt installs require root)"
        sudo -v
    fi
fi

run_sudo() {
    if [ "$NEEDS_SUDO" -eq 1 ] && [ "$(id -u)" -ne 0 ]; then
        sudo "$@"
    else
        "$@"
    fi
}

# ---------------------------------------------------------------------------
# 1. uv  (https://astral.sh/uv) — Python 3.11 + project package manager
# ---------------------------------------------------------------------------
step "uv  +  Python ${PYTHON_VERSION}"

if command -v uv >/dev/null 2>&1; then
    ok "uv already installed: $(uv --version)"
else
    info "installing uv via astral.sh installer"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # The installer drops uv into ~/.local/bin.
    export PATH="$HOME/.local/bin:$PATH"
    command -v uv >/dev/null 2>&1 || die "uv install completed but uv not on PATH; open a new shell and re-run"
    ok "installed: $(uv --version)"
fi

if uv python list --only-installed 2>/dev/null | grep -q "cpython-${PYTHON_VERSION}"; then
    ok "Python ${PYTHON_VERSION} already managed by uv"
else
    info "installing Python ${PYTHON_VERSION} via uv"
    uv python install "${PYTHON_VERSION}"
    ok "Python ${PYTHON_VERSION} installed"
fi

# ---------------------------------------------------------------------------
# 2. Node 20 + pnpm
# ---------------------------------------------------------------------------
step "Node ${NODE_MAJOR}  +  pnpm"

NODE_OK=0
if command -v node >/dev/null 2>&1; then
    NODE_MAJOR_INSTALLED="$(node -p 'process.versions.node.split(".")[0]')"
    if [ "${NODE_MAJOR_INSTALLED}" = "${NODE_MAJOR}" ]; then
        ok "Node $(node --version) already installed"
        NODE_OK=1
    else
        warn "Node $(node --version) installed but we need ${NODE_MAJOR}.x — replacing"
    fi
fi

if [ "$NODE_OK" -ne 1 ]; then
    if [ "$PLATFORM" = "linux" ]; then
        info "configuring NodeSource apt repo for Node ${NODE_MAJOR}"
        curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | run_sudo -E bash - >/dev/null
        info "apt install nodejs"
        run_sudo apt-get install -y nodejs >/dev/null
    elif [ "$PLATFORM" = "darwin" ]; then
        if ! command -v brew >/dev/null 2>&1; then
            die "Homebrew not found — install brew first or use nvm to install Node ${NODE_MAJOR}"
        fi
        brew install "node@${NODE_MAJOR}"
        brew link --overwrite --force "node@${NODE_MAJOR}"
    fi
    ok "Node $(node --version)"
fi
ok "npm  $(npm --version)"

if command -v pnpm >/dev/null 2>&1; then
    ok "pnpm already installed: $(pnpm --version)"
else
    info "installing pnpm globally"
    run_sudo npm install -g pnpm >/dev/null
    ok "pnpm $(pnpm --version)"
fi

# ---------------------------------------------------------------------------
# 3. Microsandbox  (Linux only — libkrun requires KVM)
# ---------------------------------------------------------------------------
step "Microsandbox"

if [ "$PLATFORM" != "linux" ]; then
    skip "Microsandbox is Linux-only (libkrun + KVM); install inside the SIFT VM"
elif [ -x "$HOME/.microsandbox/bin/msb" ] || command -v msb >/dev/null 2>&1; then
    MSB_BIN="$(command -v msb || echo "$HOME/.microsandbox/bin/msb")"
    ok "Microsandbox already installed: $("$MSB_BIN" --version)"
else
    info "installing Microsandbox via install.microsandbox.dev"
    curl -fsSL https://install.microsandbox.dev | sh
    ok "Microsandbox $("$HOME/.microsandbox/bin/msb" --version)"
fi

# ---------------------------------------------------------------------------
# 4. Repo bootstrap (only if the lockfiles already exist — early in W1 they don't)
# ---------------------------------------------------------------------------
step "Repo bootstrap"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f pyproject.toml ]; then
    info "uv sync --all-extras"
    uv sync --all-extras
    ok "Python deps synced"
else
    skip "no pyproject.toml yet (W1.A scaffold not landed) — re-run after first commit"
fi

if [ -f .pre-commit-config.yaml ] && [ -f pyproject.toml ]; then
    info "installing pre-commit hooks"
    uv run pre-commit install --install-hooks >/dev/null
    ok "pre-commit hooks installed"
else
    skip "pre-commit config not present yet"
fi

if [ -f pnpm-lock.yaml ]; then
    info "pnpm install --frozen-lockfile"
    pnpm install --frozen-lockfile
    ok "Node deps installed"
else
    skip "no pnpm-lock.yaml yet"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
step "Toolchain summary"
printf "    uv          %s\n" "$(uv --version 2>/dev/null || echo MISSING)"
printf "    python      %s\n" "$(uv python find "${PYTHON_VERSION}" 2>/dev/null || echo MISSING)"
printf "    node        %s\n" "$(node --version 2>/dev/null || echo MISSING)"
printf "    pnpm        %s\n" "$(pnpm --version 2>/dev/null || echo MISSING)"
if [ "$PLATFORM" = "linux" ]; then
    printf "    msb         %s\n" "$("$HOME/.microsandbox/bin/msb" --version 2>/dev/null || command -v msb >/dev/null && msb --version || echo MISSING)"
fi

cat <<EOF

${GREEN}done${RESET} contributor toolchain ready.

Next steps (CONTRIBUTING.md):
  Step 1  GitHub PAT or SSH key
  Step 3  GPG / SSH commit signing  (CLAUDE.md §3.7 forbids --no-gpg-sign)
  Step 6  Run a smoke investigation inside the SIFT VM

Open a new shell — or run:  source ~/.bashrc
to pick up updated PATH (uv, msb).
EOF
