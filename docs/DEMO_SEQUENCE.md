# DEMO_SEQUENCE.md — 5-minute recording guide

> **Status:** W3.B.2 seed (TSI tcpdump section) + stub for W6.A.1.
> The full beat list (cold open, cloud, airgap hero, dual, recap) is authored
> in W6.A.1 per BUILD_PLAN.md §W6.A.1.

---

## A. Overview — 5-minute structure

| Beat | Time | Content |
|------|------|---------|
| Cold open | 0:00 – 0:30 | Problem statement + architecture diagram flash |
| Cloud mode | 0:30 – 1:30 | n=3 self-consistency, Langfuse sibling spans |
| Air-gap hero | 1:30 – 3:00 | DKOM divergence, Hunt Evil masquerade, Amcache caveat, pivot, TSI proof, kill-9 resume |
| Dual mode | 3:00 – 4:00 | Three-way verification, mode-locked case |
| Recap | 4:00 – 5:00 | Architecture table + accuracy numbers |

Full beat script: see BUILD_PLAN.md W6.A.1 + `docs/spec/03-audit-v4.5.md` lines 855–865.

---

## B. TSI Credential Isolation — tcpdump Proof (W3.B.2)

This section provides reproducible filters and instructions for recording the
tcpdump TSI proof visible at **1:30 – 3:00** of the air-gap hero shot.

### B.1 What the proof shows

The SANS judge rubric (CLAUDE.md §3.9, BUILD_PLAN.md acceptance gate §W3.B)
requires demonstrable evidence that:

1. The `Authorization: Bearer <token>` header appears on **host egress** to
   `opencti.local:8080` (or the configured TSI origin).
2. The same header is **absent** on every frame captured **inside the microVM**
   (vsock loopback).

This is the software + network enforcement of CLAUDE.md §3.9:
> API keys, OAuth tokens, and bearer tokens never enter a microVM. They are
> injected via TSI on host egress only; tcpdump-verifiable.

### B.2 Pre-requisites

```bash
# Microsandbox installed
msb --version   # ≥ 0.4.x

# tcpdump available on the host (SIFT ships it)
which tcpdump

# OPENCTI_KEY set in host environment (never hardcoded)
echo "OPENCTI_KEY is set: ${OPENCTI_KEY:+yes}"

# OpenCTI running (either local Docker or opencti.local DNS alias)
curl -sf http://opencti.local:8080/graphql -H "Authorization: Bearer $OPENCTI_KEY" \
     -d '{"query":"{about{version}}"}' | jq .data.about.version
```

### B.3 Host egress capture

```bash
# Identify the host interface used for egress to opencti.local
# (typically eth0 or the bridge interface for Docker-based OpenCTI)
export HOST_IFACE=$(ip route get $(dig +short opencti.local) | awk 'NR==1{print $5}')

# Start capture — write to file so the frame is preserved after the demo
sudo tcpdump -i "$HOST_IFACE" \
    -w /tmp/tsi-host-egress.pcap \
    "host opencti.local and port 8080 and tcp"

# In a second terminal, trigger the TSI-proxied enrichment call
# (this spawns the microVM + TSI proxy + issues the GET /graphql):
verdict init /evidence/ransomware.E01 --mode airgap
# … wait for the first pivot that fires OpenCTI enrichment …

# Stop the capture (Ctrl-C)
```

Verify the bearer token is present:

```bash
tshark -r /tmp/tsi-host-egress.pcap \
    -Y 'http.request.full_uri contains "opencti.local"' \
    -T fields -e http.authorization
# Expected: Bearer <token>   ← at least one frame
```

### B.4 VM-internal capture

The microVM's vsock interface is not directly accessible from the host.
The proof uses one of two methods:

**Method A — capture at the vsock bridge on the host (recommended)**

```bash
# libkrun exposes a tap/vsock bridge device on the host side
# Find it: normally tap0 or veth<hash> created at microsandbox.spawn time
export VM_IFACE=$(ip link show | awk '/tap/{print $2; exit}' | tr -d ':')

sudo tcpdump -i "$VM_IFACE" \
    -w /tmp/tsi-vm-internal.pcap \
    "tcp port 8080"
```

**Method B — run tcpdump inside the VM (requires debug image)**

```bash
msb exec <container_id> -- tcpdump -i eth0 -w /work/vm-capture.pcap \
    "tcp port 8080" &
```

Verify the bearer token is **absent**:

```bash
# Count Authorization headers in VM-internal capture
COUNT=$(tshark -r /tmp/tsi-vm-internal.pcap \
    -Y 'http.authorization' \
    -T fields -e http.authorization | wc -l)
echo "VM-internal bearer frame count: $COUNT"
# Expected: 0
```

### B.5 Side-by-side recording script

The demo recording captures both terminals simultaneously.  Recommended layout:

```
┌─────────────────────────────────────────────────────────────────┐
│  Left pane: verdict terminal (investigation in progress)        │
├───────────────────────┬─────────────────────────────────────────┤
│  Bottom-left: tshark  │  Bottom-right: tshark VM-internal       │
│  (host egress)        │  (vm-internal: "0 frames with auth")    │
└───────────────────────┴─────────────────────────────────────────┘
```

Using `tmux` (recommended for the demo recording):

```bash
tmux new-session -s verdict-demo \; \
    split-window -v \; \
    split-window -h \; \
    select-pane -t 0 \; \
    send-keys "verdict init /evidence/ransomware.E01 --mode airgap" Enter \; \
    select-pane -t 1 \; \
    send-keys "sudo tcpdump -i $HOST_IFACE -nn -A 'host opencti.local and port 8080'" Enter \; \
    select-pane -t 2 \; \
    send-keys "sudo tcpdump -i $VM_IFACE  -nn -A 'tcp port 8080' 2>&1 | grep -c Authorization || echo 'Authorization count: 0'" Enter
```

At the moment the TSI proxy fires:
- Bottom-left: shows `Authorization: Bearer <token>` in the HTTP request.
- Bottom-right: shows nothing (or `Authorization count: 0`).

This is the tcpdump TSI proof visible at the demo.

### B.6 Automated assertion (CI Microsandbox runner)

The automated test `tests/sandboxes/test_tsi_provider.py::test_credentials_never_enter_microvm`
runs the same proof programmatically.  It calls `run_tsi_microvm_tcpdump_proof()` which:
- Asserts `host_egress_bearer_count >= 1`
- Asserts `vm_internal_bearer_count == 0`

This test is `pytest.mark.skipif`-gated on Microsandbox presence; the CI
Microsandbox runner (`.github/workflows/ci-microsandbox.yml`, Phase W4.B.3)
runs it against a real microVM on every push to `feat/W3.*` and `main`.

---

## C. Full beat script (W6.A.1 — to be authored)

> Stub.  See BUILD_PLAN.md W6.A.1 for the complete 5-minute beat list with
> exact timing, hero beats, and production notes.  This section will be
> expanded in W6.A.1.

Hero beats for the air-gap shot (1:30 – 3:00):

1. pslist + psscan DKOM divergence → T1014 hypothesis (CLAUDE.md §7).
2. Hunt Evil masquerade catch: `scvhost.exe` parent=`cmd.exe` → T1036.005.
3. Amcache caveat acknowledged in Finding rationale (CLAUDE.md §3.3).
4. Pivot fires in response to prior tool output (not part of initial plan).
5. Qwen3-vs-GLM disagreement → CONTESTED → replan → VETTED_AIRGAP.
6. **TSI tcpdump proof** — this section (§B above).
7. kill -9 between super-steps + `verdict resume` (zero step loss).
