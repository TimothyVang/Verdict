# FIND EVIL! Hackathon — Overview

> **Wiki:** [Index](../README.md) · [TL;DR](../TLDR.md) · [Architecture](../ARCHITECTURE.md) · [Build Plan](../BUILD_PLAN.md) · [Devpost](../DEVPOST_COMPLIANCE.md) · [Hackathon Rules](RULES.md) · root [CLAUDE.md](../../CLAUDE.md)

Source: https://findevil.devpost.com/
Scraped: 2026-05-02; spot-checked against live Devpost page during docs polish.

## What to Build
Improve Protocol SIFT's autonomous incident response capabilities processing case data (disk images, memory captures, log files, network captures).

> "Make Protocol SIFT a fully autonomous incident response agent."

## Context / Motivation
> "An AI-powered adversary can go from initial access to full domain control in under 8 minutes," while "a human incident responder is still pulling up their toolkit."

Participants build solutions teaching AI agents to "think like a senior analyst" with autonomous triage, correlation, and self-correction capabilities.

## Stats
- **Participants:** 2,484 registered at last live-page spot-check
- **Sponsor:** SANS Institute
- **Judge:** Rob T. Lee (CAIO, SANS Institute)
- **Format:** Online, public hackathon

## Core Deliverables (All 8 Must-Include Components)
1. Code repository — public GitHub repo with MIT or Apache 2.0 license and README setup instructions
2. Demo Video (max 5 minutes) — live terminal execution with narration and at least one self-correction sequence
3. Architecture Diagram — identifying security boundaries and architectural patterns
4. Written Project Description (Devpost format)
5. Dataset Documentation — test data sources and findings
6. Accuracy Report — false positives, missed artifacts, hallucinations, evidence integrity approach
7. Try-It-Out Instructions — local deployment steps or live URL
8. Agent Execution Logs — timestamps, tool traces, token usage, and agent/iteration traces where applicable

## Resource Links

| Resource | URL |
|----------|-----|
| Main Hackathon Page | https://findevil.devpost.com/ |
| Rules (Full) | https://findevil.devpost.com/rules |
| Registration | https://findevil.devpost.com/register |
| Project Gallery | https://findevil.devpost.com/project-gallery |
| Protocol SIFT Slack | https://join.slack.com/t/sansaihackathon/shared_invite/zt-3srjz86zo-bwHi_v1aKTg2IJAU4_4OwA |
| SIFT Workstation Download | https://www.sans.org/tools/sift-workstation |
| Protocol SIFT Install Script | https://raw.githubusercontent.com/teamdfir/protocol-sift/main/install.sh |
| Protocol SIFT GitHub | https://github.com/teamdfir/protocol-sift |
| Hackathon Manager Email | aihackathon@sans.org |

## SIFT Workstation
- **VM Appliance (OVA):** 8.81GB, last updated April 24, 2026 — login to SANS Portal required
- **Default credentials:** sansforensics / forensics
- **Privilege escalation:** `sudo su -`
- **Native Ubuntu install:** `sudo cast install teamdfir/sift` (upstream documents this path for Ubuntu 22.04; VERDICT's preferred reproduction path is the SIFT OVA)
- **WSL install:** `sudo cast install --mode=server teamdfir/sift-saltstack`

## Protocol SIFT Install (one-liner)
```bash
curl -fsSL https://raw.githubusercontent.com/teamdfir/protocol-sift/main/install.sh | bash
```

## Note on Sample Evidence
The Protocol SIFT GitHub repository contains **no forensic images, sample evidence files, or IOC datasets**. It provides configuration and automation templates only. Sample case data (hard drives, memory images) is referenced as available through the Protocol SIFT Slack channel — no direct public download links are published on devpost.
