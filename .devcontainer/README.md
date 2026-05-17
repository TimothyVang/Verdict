# `.devcontainer/` — VERDICT dev container

Reproducible toolchain for any contributor with Docker. Open the repo in
VS Code with the Dev Containers extension and pick **"Reopen in Container"**;
or build directly with `docker build -f .devcontainer/Dockerfile .`.

## What's inside

| Tool | Pin | License | Source |
|---|---|---|---|
| `uv` (Python pkg manager) | latest from astral.sh | MIT / Apache-2.0 dual | `https://astral.sh/uv/install.sh` |
| Python | 3.11 (uv-managed) | PSF | via `uv python install` |
| Node | 20.x LTS | MIT | NodeSource apt repo |
| `pnpm` | latest | MIT | `npm install -g pnpm` |
| Rust | 1.88.0 | MIT / Apache-2.0 dual | `rustup` |
| Common CLI | `jq`, `ripgrep`, `fd-find`, `sqlite3`, `git`, `gnupg` | various permissive | apt |
| Base image | `mcr.microsoft.com/devcontainers/base:ubuntu-22.04` | MIT | Microsoft Devcontainers |

Every component is MIT, Apache-2.0, or BSD — passes CLAUDE.md §3.8.

The 18 skills under `.claude/skills/` and the MCPs across `.mcp*.json`
(1 in the safe-default `.mcp.json`, 6 in `.mcp.cloud.json` / `.mcp.dual.json`)
come along for free (they're just files in the repo + `npx`/`uvx` commands the
container can run).

## What's NOT inside (by design)

| Component | Why it's host-side | Where it actually runs |
|---|---|---|
| **Microsandbox** (libkrun microVMs) | Needs `/dev/kvm` and KVM kernel module — Docker can't provide this if the host doesn't have nested virt enabled. | Host (or SIFT VM with KVM passthrough). Container reaches it via `host.docker.internal`. |
| **SGLang** (Qwen3 + GLM-4.5-Air inference) | Needs NVIDIA GPU + `nvidia-container-toolkit`. A devcontainer can mount the GPU only if the host has one to mount. | Host (or SIFT VM with GPU passthrough). Container reaches it on `host.docker.internal:30000` and `:30001`. |
| **Langfuse v2** | Already its own docker-compose stack; nesting it inside the devcontainer would just create circular wrapping. | Independent compose stack at `infra/langfuse/`. Container reaches it on `host.docker.internal:3000`. |
| **HMAC ledger key** | Lives at `~/.verdict/key.gpg` on the host — gpg-encrypted with a passphrase you type into a TTY at boot. Must never enter a microVM (CLAUDE.md §3.9), and a portable image must never carry it. | Host. Mount the gpg agent socket if you need the container to sign without exiting. |
| **Evidence files** | `.E01` / `.mem` / `.pcap` etc. are forensic artifacts under chain-of-custody. Read-only mount, host-`chattr +i`, never in the image. | Host `/evidence/` (read-only, `noexec`). |

This split is deliberate. A devcontainer makes the **toolchain** portable — that's the part that drifts across machines and burns hours debugging. The **hardware-bound services** are pinned to whatever box has KVM + GPU, and the container just talks to them over `host.docker.internal`.

## Credential isolation (CLAUDE.md §3.9)

The image carries **no secrets**. `devcontainer.json` uses `${localEnv:VAR}` refs that pull from the host shell at container start:

| Var | Source | Where it ends up |
|---|---|---|
| `ANTHROPIC_API_KEY` | host shell or `.env` | preferred cloud credential; container env only — never written to disk inside the image |
| `OPENROUTER_API_KEY` | host shell or `.env` | optional host-side AI-agent fallback; never passed into microsandboxes |
| `GITHUB_TOKEN` | host shell | passed to the `github` MCP via `.mcp.json` (already env-var-ref only) |
| `LANGFUSE_*` | host shell or `.env` | pointed at `host.docker.internal:3000` |
| `SGLANG_*` | hard-coded to `host.docker.internal:{30000,30001}` | overrides the `.env` defaults of `localhost:*` so the container reaches the host |

Mount `.env` is **not** a separate step — the repo workspace mount (`/workspaces/Verdict`) already exposes `.env` to the container. It stays gitignored, mode 0600, and never appears in `git status`.

## Quickstart

### Path A — VS Code Dev Containers (recommended)

```bash
# Once: install the Dev Containers extension in VS Code.
# Then, in the repo root:
code .
# Cmd/Ctrl+Shift+P → "Dev Containers: Reopen in Container"
```

VS Code builds the image, runs `post-create.sh` (which inits `protocol-sift/`, runs `uv sync`, and runs the MCP license/secret guard), and drops you in a shell with everything on `PATH`.

### Path B — straight `docker build` / `docker run`

```bash
# Build
docker build -f .devcontainer/Dockerfile -t verdict-dev .devcontainer

# Run (mount the repo, forward the host network gateway)
docker run -it --rm \
  --add-host=host.docker.internal:host-gateway \
  -v "$PWD":/workspaces/Verdict \
  -w /workspaces/Verdict \
  -e ANTHROPIC_API_KEY \
  -e OPENROUTER_API_KEY \
  -e GITHUB_TOKEN \
  -e LANGFUSE_PUBLIC_KEY \
  -e LANGFUSE_SECRET_KEY \
  verdict-dev \
  bash
```

Inside, run the same `post-create.sh` once: `bash .devcontainer/post-create.sh`.

### Path C — pure host install (no Docker)

The original path: `bash scripts/bootstrap-dev.sh`. Gets you the same toolchain on the host without containerization. Useful if you're already on the SIFT VM and don't want a layer between you and the hardware.

## Bringing up the host-side services

These don't change between contributors — once per host:

```bash
# 1. Langfuse v2 (~1.5 GB RAM)
cd infra/langfuse && docker compose up -d
curl -fsS http://localhost:3000/api/public/health   # expect 200
# Open http://localhost:3000, create org+project, copy keys → .env

# 2. Microsandbox (Linux + KVM only)
curl -fsSL https://install.microsandbox.dev | sh
~/.microsandbox/bin/msb --version

# 3. SGLang (Linux + NVIDIA GPU only)
sglang_server_v1 --model-path /path/to/qwen3 --port 30000 \
  --tool-call-parser qwen &
sglang_server_v1 --model-path /path/to/glm-4.5-air --port 30001 \
  --tool-call-parser glm &

# 4. HMAC ledger key (no TPM → gpg fallback)
mkdir -p ~/.verdict ~/cases
openssl rand -base64 32 | gpg --symmetric --output ~/.verdict/key.gpg
chmod 600 ~/.verdict/key.gpg
```

After this, `verdict doctor` (when the CLI lands per `BUILD_PLAN.md` W6) will report green on whatever the host can actually provide.

## Rebuilding

The image is layered for fast incremental rebuilds:

- Bumping `NODE_MAJOR`, `PYTHON_VERSION`, or `RUST_VERSION` in the Dockerfile invalidates only the affected layer.
- `uv sync` runs in `post-create.sh` (not in the image) so a `pyproject.toml` change re-syncs the venv without rebuilding the image.
- `git submodule update` runs in `post-create.sh` for the same reason.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `claude mcp list` shows `github` but auth fails | `GITHUB_TOKEN` unset on the host shell that launched the container | `export GITHUB_TOKEN=ghp_…` then rebuild/reopen |
| `host.docker.internal` doesn't resolve inside the container | Host runs Docker without `--add-host=…:host-gateway` (e.g., older Docker) | Upgrade Docker to 20.10+, or set `--network=host` in `runArgs` |
| `uv sync` fails on first start | `pyproject.toml` references a dep that isn't on PyPI yet | Rare; see `pyproject.toml` history. Not a container bug. |
| `git submodule update` asks for credentials | Mounted `.gitconfig` doesn't include the host's GitHub auth | Use SSH-based remote (`git remote set-url origin git@github.com:…`) and forward `SSH_AUTH_SOCK` via an extra mount |
