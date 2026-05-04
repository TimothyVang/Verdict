#!/usr/bin/env bash
# Generate Langfuse v2 self-host secrets and append them to .env.
#
# Per CLAUDE.md §3.9 — no committed secrets. The compose at
# infra/langfuse/docker-compose.yml uses ${VAR:?...} refs that fail-fast
# if these are unset; this script populates them on first install.
#
# Idempotent: refuses to overwrite values already in .env. Re-run only
# after manually deleting the relevant lines if you want to rotate.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

# .env must exist (it's a copy of .env.example with credentials filled in).
if [ ! -f "${ENV_FILE}" ]; then
    echo "error: ${ENV_FILE} not found — copy .env.example to .env first" >&2
    exit 1
fi

append_if_missing() {
    local var="$1"
    local val="$2"
    if grep -qE "^${var}=" "${ENV_FILE}"; then
        echo "skip ${var}: already set in .env"
    else
        printf '%s=%s\n' "${var}" "${val}" >> "${ENV_FILE}"
        echo "added ${var}"
    fi
}

# 32-byte hex secrets (Langfuse expects exactly this for ENCRYPTION_KEY;
# NEXTAUTH_SECRET + SALT accept any high-entropy string of the same length).
NEXTAUTH_SECRET="$(openssl rand -hex 32)"
SALT="$(openssl rand -hex 32)"
ENCRYPTION_KEY="$(openssl rand -hex 32)"
DB_PASSWORD="$(openssl rand -base64 24 | tr -d '\n=+/')"

append_if_missing LANGFUSE_NEXTAUTH_SECRET "${NEXTAUTH_SECRET}"
append_if_missing LANGFUSE_SALT            "${SALT}"
append_if_missing LANGFUSE_ENCRYPTION_KEY  "${ENCRYPTION_KEY}"
append_if_missing LANGFUSE_DB_PASSWORD     "${DB_PASSWORD}"

chmod 600 "${ENV_FILE}"

cat <<'EOF'

Langfuse secrets generated. Next:
  cd infra/langfuse && docker compose up -d
  curl -fsS http://localhost:3000/api/public/health   # expect 200

Then open http://localhost:3000 → create org+project → copy the
LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY into .env (existing template
slots already there).
EOF
