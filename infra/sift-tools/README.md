# SIFT Tools Microsandbox Image

This image carries the minimum SIFT tool surface that VERDICT currently calls through Microsandbox:

- Volatility 3 `vol3` for `windows.info`, `windows.pslist`, and `windows.psscan`.
- Sleuth Kit `mmls`, `fsstat`, and `fls` for disk-image triage.

Build and tag locally:

```bash
docker build -f infra/sift-tools/Containerfile -t verdict-sift-tools:2.28.0 .
```

Verify the required binaries before using the image in a case:

```bash
docker run --rm verdict-sift-tools:2.28.0 vol3 -h
docker run --rm verdict-sift-tools:2.28.0 mmls -V
docker run --rm verdict-sift-tools:2.28.0 fsstat -V
docker run --rm verdict-sift-tools:2.28.0 fls -V
```

Set `VERDICT_MICROSANDBOX_IMAGE` to a digest-pinned reference. For a registry-pushed image, use the registry digest:

```bash
docker buildx build --platform linux/amd64 \
  -f infra/sift-tools/Containerfile \
  -t ghcr.io/OWNER/verdict-sift-tools:2.28.0 \
  --push .

docker buildx imagetools inspect ghcr.io/OWNER/verdict-sift-tools:2.28.0
export VERDICT_MICROSANDBOX_IMAGE='ghcr.io/OWNER/verdict-sift-tools@sha256:<digest-from-inspect>'
```

The CLI intentionally rejects unpinned image tags. The value must match `IMAGE@sha256:<64 hex characters>` so each ledger row can record the exact root filesystem digest used for examination.

Licensing note: Volatility 3 is distributed under the Volatility Software License, and Sleuth Kit is distributed under its upstream forensic-tool licenses. These are executed as external tools inside the forensic image; they are not added to VERDICT's Python package dependencies.
