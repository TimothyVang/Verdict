# FIND EVIL! Hackathon — Official Rules

> **Wiki:** [Index](../README.md) · [TL;DR](../TLDR.md) · [Architecture](../ARCHITECTURE.md) · [Build Plan](../BUILD_PLAN.md) · [Devpost](../DEVPOST_COMPLIANCE.md) · [Hackathon Overview](OVERVIEW.md) · root [CLAUDE.md](../../CLAUDE.md)

Source: https://findevil.devpost.com/rules
Scraped: 2026-05-02

## Key Dates
- **Submission Period:** Apr 15 – Jun 15, 2026 (deadline 11:45pm EDT)
- **Judging Period:** Jun 19 – Jul 3, 2026
- **Winners Announced:** ~Jul 8, 2026

## Eligibility
Open to individuals (18+), teams (up to 5), and organizations.

**Not open to:**
- Residents of sanctioned countries
- Hackathon staff/judges, their families
- Anyone with conflicts of interest

## Project Requirements
Entrants must build *"a working software application that extends Protocol SIFT's autonomous incident response capability using an agentic framework."*

- Uses **Claude Code** or **OpenClaw** as primary execution engine
- Demonstrates self-correction, accuracy validation, and analytical reasoning
- Runs on Linux / SANS SIFT Workstation environment
- "Substantially new work created during the hackathon period"
- May leverage open-source libraries and existing SIFT codebase

## Submission Materials Required (8 components)
1. **Code repository** — public GitHub repository with MIT or Apache 2.0 license and setup instructions in the README.
2. **Demo video** — under 5 minutes, screencast with narration showing live terminal execution against real evidence and at least one self-correction sequence.
3. **Architecture diagram** — identifies components, security boundaries, and architectural patterns.
4. **Written project description** — Devpost format: what it does, how it was built, challenges, lessons learned, and what's next.
5. **Evidence dataset documentation** — test data sources and findings.
6. **Accuracy report** — false positives, missed artifacts, hallucinations, and evidence integrity approach.
7. **Try-it-out instructions** — live deployment URL or clear local execution steps for the SIFT workstation.
8. **Agent execution logs** — timestamps, tool traces, token usage, and agent-to-agent or iteration traces where applicable.

## Judging Criteria (Stage Two — six equally weighted factors)
1. **Autonomous Execution Quality** *(tiebreaker)* — agent reasoning and self-correction capability
2. **IR Accuracy** — findings correctness; hallucinations flagged; inferences distinguished from confirmed data
3. **Breadth and Depth of Analysis** — case data handling capacity
4. **Constraint Implementation** — guardrail architecture (architectural vs. prompt-based) and bypass testing
5. **Audit Trail Quality** — traceability from findings to tool execution
6. **Usability and Documentation** — deployment and extensibility for others

## Prizes ($22,000 Total)

| Place | Cash | Additional |
|-------|------|------------|
| 1st | $10,000 | SANS Summit pass + hotel + OnDemand course per member + webcast presentation |
| 2nd | $7,500  | SANS Summit pass + hotel + OnDemand course per member + webcast presentation |
| 3rd | $4,500  | OnDemand course per member |

## Intellectual Property
- Entrants retain ownership
- Sponsor receives a **non-exclusive license** for judging and promotional use for three years
- Projects must be original work without third-party IP violations

## Restrictions
- No prior financial support from sponsor/administrator
- Cannot be derived from commercially funded projects
- Must comply with all third-party SDK/API licensing
- Cannot include copyrighted material without permission

## Dispute Resolution
Claims resolved through binding arbitration under American Arbitration Association rules, governed by New York law.

## Supported Architectural Approaches
1. **Direct Agent Extension** (Claude Code/OpenClaw) — extend existing agent loop with better prompting and self-correction
2. **Custom MCP Server** — purpose-built typed functions preventing destructive commands
3. **Multi-Agent Frameworks** (AutoGen, CrewAI, LangGraph) — specialized communicating agents
4. **Alternative Agentic IDEs** (Cursor, Cline, Aider) — AI-native development environments

## Contact
- **Hackathon Manager:** aihackathon@sans.org
- **Slack:** https://join.slack.com/t/sansaihackathon/shared_invite/zt-3srjz86zo-bwHi_v1aKTg2IJAU4_4OwA
- **Judge:** Rob T. Lee (CAIO, SANS Institute)
