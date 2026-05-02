# VERDICT Threat Model (v1)

**Document type:** Threat analysis for VERDICT DFIR agent running on SANS SIFT Workstation.
**Authority:** Per ARCHITECTURE.md §9 and BUILD_PLAN.md Phase W1.G.1.
**Scope:** Digital forensic incident response within air-gap, cloud, or dual inference modes.

---

## Executive summary

VERDICT faces four distinct adversary surfaces in v1:

1. **Insider analyst** — with HMAC ledger-key access
2. **Prompt injection from evidence** — malicious strings in memory/disk images
3. **Malicious tool output** — forensic tools exploited by crafted evidence
4. **External attacker on SIFT box** — assumption: SIFT box is trusted-host

Each surface has documented mitigations and known residual risks.

---

## 1. Insider analyst with ledger-key access

### Threat

A cleared analyst with physical access to the SIFT box **and knowledge of the HMAC ledger key** could forge ledger entries.

### Mitigation

- **TPM-backed HMAC key** (primary): If `/dev/tpmrm0` is present, the ledger key is stored in TPM. Extraction requires physical access to the TPM chip itself.
  - Implementation: `verdict/ledger/hmac_key.py` detects TPM presence and uses `tpm2-tools` CLI.

- **GPG-encrypted fallback**: On systems without TPM (laptops, lab VMs), the key is encrypted with a passphrase and stored at `~/.verdict/key.gpg`. Gateway init prompts for the passphrase once per session.

- **Ledger entry chain**: Every entry includes `prev_entry_hash` (SHA-256 of prior entry), forming a hash chain. Tampering invalidates all downstream entries.

- **HMAC-signed findings**: Each `Finding` is signed over `(Finding + approver_id + timestamp)`. Approver identity is audited.

### Residual risk

A cleared analyst with both physical access to the TPM and knowledge of the passphrase can forge ledger entries.

**Acceptance for v1:** This is a human accountability problem. Insider threats are addressed by organizational policy (key rotation, log monitoring, multi-analyst review).

---

## 2. Prompt injection from evidence

### Threat

A malicious memory or disk image could contain attacker-controlled strings that become inputs to the LLM planner. An attacker could craft command-line arguments with jailbreak suffixes, file paths with `</tool_call>` markers, or registry values with prompt-manipulation payloads.

### Mitigation

- **Sanitization scanner** (`verdict/tools/sanitization.py`): Every tool output is scanned for jailbreak markers. Detection patterns include:
  - `IGNORE PREVIOUS INSTRUCTIONS`
  - `SYSTEM:` / `ASSISTANT:` / `USER:` / `INSTRUCTIONS:`
  - `</tool_call>` / `<tool_use>` (XML-like markers)
  - `[INST]` / `[/INST]` (Llama format)

- **ToolOutput.sanitization_flags**: Detected patterns are recorded. The planner must justify any use of flagged content.

- **Structured-output parsing as primary defense**: Tool output is parsed into Pydantic models at the schema layer. Malicious raw strings are rejected before reaching the planner.

### Residual risk

Novel jailbreak patterns not yet in the deny-list may evade sanitization. Update the deny-list quarterly with new patterns from HF / OpenAI / Anthropic threat reports.

**Acceptance for v1:** This is a defense-in-depth layer. Structured parsing is the primary defense.

---

## 3. Malicious tool output from crafted evidence

### Threat

A forensic tool (`vol3`, `plaso`, `hayabusa`, `MFTECmd`, etc.) is invoked on a crafted memory or disk image and is exploited to execute arbitrary code, read evidence files outside the current case, or exfiltrate data.

### Mitigation

- **Microsandbox isolation** (primary): Every tool call runs in an **ephemeral libkrun microVM**, destroyed after the call completes.
  - **Network isolation**: `network=False`; no external communication
  - **Read-only evidence mount**: Evidence files mounted read-only (`noexec`); writes fail
  - **Shallow filesystem**: Minimal rootfs with only tool and runtime dependencies
  - **Host evidence protection**: Host runs `chattr +i` (immutable bit) on evidence files
  - **Cold start**: Each call = fresh microVM; no state carries over

- **Restricted privileges on host**: Tools run as unprivileged `verdict` user, not `root`.

### Residual risk

**Microsandbox escape** — if `libkrun` hypervisor is exploited, attacker could break into host. Accepted v1 risk. Evaluation of `kata-containers` deferred to v2.

**Acceptance for v1:** Microsandbox is actively maintained and used in production. Its attack surface is smaller than the full Linux kernel.

---

## 4. External attacker on SIFT box

### Threat

An unauthorized person gains shell access via unpatched SSH, weak credentials, or physical access. The attacker could read case data, modify ledger, steal the HMAC key, or exfiltrate findings.

### Mitigation

**Out of scope for v1.** Host hardening is the responsibility of the operator:
- SSH key-only auth, no passwords
- Firewall rules
- Encrypted filesystem (`/evidence` on LUKS)
- Physical security
- Regular OS patching
- Audit logging

VERDICT assumes the SIFT box is a **trusted execution environment** (TEE).

### Residual risk

If the SIFT box is compromised, the attacker has full access to VERDICT's state and evidence.

**Acceptance for v1:** Standard in forensic practice. Chain-of-custody relies on physical security, not on the tool.

---

## 5. Known gap: Model as adversary

**Not addressed in v1.** The planner's chain-of-thought reasoning is captured in the ledger (first 8KB) and Langfuse traces. If Langfuse is cloud-hosted, the CoT leaks to a third party.

### Mitigation strategy (v2 roadmap)

- **Air-gap Langfuse**: In `AIRGAP` mode, Langfuse runs on the same SIFT box as the agent.
- **CoT redaction pipeline**: Filter out evidence-derived strings from CoT before recording.
- **Fine-tuning policy**: Never export case CoT for training without explicit approval.

### Acceptance for v1

Documented as accepted v1 risk; v2 will add redaction.

---

## 6. Attack surface summary

| Adversary | Mitigation | Residual risk | Accepted |
|-----------|-----------|----------------|----------|
| Insider analyst (HMAC key) | TPM-backed key + GPG + hash-chain | Cleared insider with TPM access can forge | Yes |
| Malicious evidence (prompt injection) | Sanitization + structured parsing | Novel jailbreaks evade deny-list | Yes |
| Malicious forensic tool | Microsandbox + read-only mounts | Microsandbox escape = host compromise | Yes (v2: kata) |
| External attacker (SIFT box) | Operator hardening | No defense by agent | Yes (operator responsibility) |
| LLM model (CoT exfiltration) | v2: air-gap Langfuse, CoT redaction | Langfuse cloud compromise leaks reasoning | Documented; v2 roadmap |

---

## References

- **NIST SP 800-86** — Guide to Integrating Forensic Techniques into Incident Response. Section 5 ("Preservation") emphasizes chain-of-custody and integrity verification.
- **OWASP Prompt Injection** — https://owasp.org/www-community/attacks/Prompt_Injection
- **Unikraft Microsandbox** — https://unikraft.io/
- **Kata Containers** — https://katacontainers.io/ (v2 evaluation candidate)

---

## Document history

| Version | Date | Notes |
|---------|------|-------|
| 1.0 | 2026-05-02 | Initial draft per BUILD_PLAN.md W1.G.1. Four surfaces, mitigations, residual risks. |
