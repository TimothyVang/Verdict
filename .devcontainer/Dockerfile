# VERDICT dev container — toolchain only.
#
# What's inside: uv + Python 3.11, Node 20 + pnpm, Rust 1.88, common dev utils.
# What's NOT inside: Microsandbox (needs /dev/kvm) and SGLang (needs NVIDIA GPU).
# Those run on the host (or on a SIFT VM with KVM + GPU passthrough); the
# container reaches them via host.docker.internal. Langfuse runs as its own
# docker-compose stack alongside this container — see infra/langfuse/.
#
# License compliance: every component below is MIT, Apache-2.0, or BSD
# (CLAUDE.md §3.8). Verified pin-by-pin in .devcontainer/README.md §"Licenses".

FROM mcr.microsoft.com/devcontainers/base:ubuntu-22.04
# ↑ Microsoft Devcontainers base — MIT (github.com/devcontainers/images).
#   Provides 'vscode' user (UID 1000), passwordless sudo, git, openssh,
#   and the common shell utilities a dev session expects.

ARG NODE_MAJOR=20
ARG PYTHON_VERSION=3.11
ARG RUST_VERSION=1.88.0
ARG PNPM_VERSION=latest

# ─── Root-level installs ──────────────────────────────────────────────────
# Node 20 via NodeSource (mirrors scripts/bootstrap-dev.sh §3) plus a couple
# of forensic-adjacent CLI tools that .mcp.json's npx-based MCPs occasionally
# shell out to. Single layer to keep the image small; clean apt lists at end.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg2 build-essential pkg-config \
        jq ripgrep fd-find sqlite3; \
    curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -; \
    apt-get install -y --no-install-recommends nodejs; \
    npm install -g "pnpm@${PNPM_VERSION}"; \
    rm -rf /var/lib/apt/lists/*

# ─── Switch to vscode user for user-scoped tools ─────────────────────────
USER vscode
ENV HOME=/home/vscode \
    PATH="/home/vscode/.local/bin:/home/vscode/.cargo/bin:${PATH}"
WORKDIR ${HOME}

# ─── uv (Astral, Apache-2.0 / MIT dual) + Python 3.11 ────────────────────
# Mirrors scripts/bootstrap-dev.sh §1 so the host and container converge on
# identical pkg-manager + interpreter versions.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
 && uv python install "${PYTHON_VERSION}"

# ─── Rust 1.88 via rustup (Apache-2.0 / MIT dual) ────────────────────────
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
      | sh -s -- -y \
            --default-toolchain "${RUST_VERSION}" \
            --profile minimal \
            --no-modify-path \
 && /home/vscode/.cargo/bin/rustup default "${RUST_VERSION}"

# ─── Bake PATH into login + non-login shells ─────────────────────────────
RUN printf '\n# Verdict toolchain PATH\nexport PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"\n' \
      >> "${HOME}/.bashrc" \
 && printf '\n# Verdict toolchain PATH\nexport PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"\n' \
      >> "${HOME}/.profile"

# ─── Smoke test: image build fails fast if any tool is missing ───────────
RUN bash -lc ' \
    set -euo pipefail; \
    uv --version; \
    rustc --version; \
    cargo --version; \
    node --version; \
    npm --version; \
    pnpm --version; \
    echo "toolchain OK"'

# Workspace mount happens at /workspaces/Verdict via devcontainer.json.
WORKDIR /workspaces/Verdict
