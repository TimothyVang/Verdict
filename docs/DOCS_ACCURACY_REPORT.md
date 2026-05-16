# VERDICT — Docs Accuracy Audit

> **Wiki:** [Index](README.md) · [TL;DR](TLDR.md) · [Architecture](ARCHITECTURE.md) · [Build Plan](BUILD_PLAN.md) · [Devpost](DEVPOST_COMPLIANCE.md) · [Workflow Review](AGENTIC_WORKFLOW_REVIEW.md) · root [CLAUDE.md](../CLAUDE.md)

**Audited:** 2026-05-02
**Resolved:** 2026-05-02 (all 11 punchlist items closed; see *Resolution log* at bottom).
**Scope:** README.md, ARCHITECTURE.md, BUILD_PLAN.md, DEVPOST_COMPLIANCE.md (project root). Archive treated as historical reference, not authority — but cross-checked when it disagrees with the current docs.
**Methodology:** (1) cross-reference claims across the four authority docs; (2) verify external technical claims against MITRE ATT&CK, arXiv, GitHub, NIST, vendor pages, and the Devpost rules page; (3) re-count tables and lists where the docs assert totals.

---

## Severity legend

- **CRITICAL** — factually wrong; will cause a runtime/judging failure or claim something false.
- **HIGH** — internal inconsistency between authority docs, will confuse a reader and trip "judges read carefully" review.
- **MEDIUM** — code-level or surface-level error; not load-bearing for judging but will fail QA.
- **LOW** — wording / future-proofing nits.

---

## CRITICAL — factual errors

### C1. MITRE technique `T1014.001` does not exist

**Where:** `README.md` line 284, `ARCHITECTURE.md` lines 211, 214, 422, `DEVPOST_COMPLIANCE.md` lines 82, 92.
**Claim:** The DKOM auto-detection emits `Hypothesis(T1014.001, …)` and the demo's hero beat ⓵ shows "DKOM divergence (pslist+psscan) → T1014.001 auto."
**Reality:** MITRE ATT&CK `T1014` (Rootkit) has **zero sub-techniques**. There is no `T1014.001`. Confirmed against `attack.mitre.org/techniques/T1014/` and noted in your own archive: `docs/spec/02-audit-v4.4.md` line 562 emits `Hypothesis(mitre_technique="T1014", confidence=high)` — no sub-technique — and your `BUILD_PLAN.md` line 38 also says "DKOM/T1014" without `.001`.
**Impact:** The schema validator that requires MITRE IDs to match `^T\d{4}(\.\d{3})?$` will accept `T1014.001` as syntactically valid but it is semantically fabricated; a SANS judge familiar with MITRE will catch this in seconds. Your IR Accuracy criterion (rubric #2) is the worst place to hand them a wrong MITRE ID.
**Fix:** Replace every `T1014.001` with `T1014` in `README.md`, `ARCHITECTURE.md`, and `DEVPOST_COMPLIANCE.md`. (Optional: add a `mitre_technique_subtype: "DKOM"` free-text field if you want sub-technique-style granularity.) `docs/spec/04-spec-plan-v4.6.md` mixes both forms; leave that archive untouched and cite the current architecture instead.

### C2. "RFC-2119 standard MIT" mislabels the MIT license

**Where:** `DEVPOST_COMPLIANCE.md` line 220 (W6.D.0.b): "Verify LICENSE file at repo root contains MIT text (RFC-2119 standard MIT, not custom)."
**Reality:** RFC 2119 defines requirement-level keywords (MUST / SHALL / SHOULD). It has nothing to do with the MIT license. The MIT license is not specified by an RFC; the canonical reference is the OSI page or `spdx.org/licenses/MIT.html`.
**Fix:** Replace with "OSI-canonical MIT text (SPDX identifier `MIT`), not custom."

### C3. Vol3 example version `2.10.0` is far behind current

**Where:** `ARCHITECTURE.md` line 313 (`tool_version="vol3 2.10.0"`), `docs/spec/02-audit-v4.4.md` line 342 (`vol3-2.10.0`).
**Reality:** Volatility 3 is at **2.28.0** in the official docs (`volatility3.readthedocs.io/en/latest/`). 2.10.0 dates from early 2024. Pinning a microsandbox image at 2.10.0 means losing ~18 minor releases of plugin fixes — including improvements to `windows.netscan` and `windows.svcscan` that you rely on for hero beats.
**Fix:** Either change the example to a current version (`2.28.0`) or label the literal as "<<pin-at-build-time>>" so it doesn't read as a recommendation. Also pin the actual microsandbox image to a current vol3 build before W2.A.

---

## HIGH — internal inconsistencies between authority docs

### H1. Vol3 plugin count: "10 plugins" claimed, 11 listed

**Where:** `ARCHITECTURE.md` line 288.
**Claim:** `windows.{info,pslist,psscan,pstree,cmdline,dlllist,malfind,netscan,svcscan,handles,callbacks}` (10 plugins).
**Reality:** That list contains 11 names: info, pslist, psscan, pstree, cmdline, dlllist, malfind, netscan, svcscan, handles, callbacks.
**Cross-check with BUILD_PLAN:** `BUILD_PLAN.md` W1.E.1 wraps `psscan` and W2.A.1–W2.A.9 wraps the other nine — but `windows.info` has **no wrapper task at all**. So either the architecture is over-listing by including `info`, or the build plan is missing a wrapper task.
**Fix:** Pick one. Either drop `info` from the architecture list (count stays 10, both docs match), or add a W2.A.1.5 task to wrap `windows.info` (count goes to 11, update both docs and the totals in §H2).

### H2. "19 wrappers" total — math doesn't add up

**Where:** `ARCHITECTURE.md` §6 header ("12 SIFT tools, 19 wrappers"), `DEVPOST_COMPLIANCE.md` line 89 ("19 tool wrappers"), implicitly in `README.md` roadmap (Tim "9 vol3 wrappers" + KP "9 non-vol3 wrappers" = 18).
**Reality, counting wrappers as defined in `BUILD_PLAN.md`:**
- vol3: 10 (W1.E.1 psscan + W2.A.1–9)
- hayabusa: 2 (W2.F.1 + W2.F.2)
- plaso: 2 (W2.F.3 + W2.F.4)
- sleuth kit: 3 (mmls/fls/fsstat — W2.A.10–12)
- EZ tools: 3 (MFTECmd/RECmd/PECmd — W2.A.13–15)
- other: 3 (bulk_extractor/exiftool/capa — W2.A.16–18)
- **Total: 23 wrappers** (24 if you also wrap `windows.info` per H1).

The "19" figure appears to drop the W2.F plaso+hayabusa splits (4 wrappers); the README's "18" appears to additionally drop the same 4 and also miscount one. The counting basis is inconsistent across the three docs.
**Fix:** Update all three docs to "23 wrappers" (or 24 after H1 resolution). And in `DEVPOST_COMPLIANCE.md` line 89, the parenthetical "9 Sleuth Kit/EZ Tools/bulk_extractor/exiftool/capa" sums to 9 (3+3+1+1+1) — that part is correct — but its outer "10 vol3 + … + 9 …" formula still misses the +2+2 for hayabusa and plaso splits.

### H3. "9 nodes" in the LangGraph topology — actually 10

**Where:** `BUILD_PLAN.md` line 565 ("LangGraph compiles with 9 nodes"), `DEVPOST_COMPLIANCE.md` line 63 ("Plan-then-Execute LangGraph with 9 nodes").
**Reality, counting named nodes in `ARCHITECTURE.md` §2 topology:**
1. `planner_node`
2. `planner_critique`
3. `comprehension_gate`
4. `executor_fanout`
5. `pivot_node`
6. `quorum_node`
7. `finalize_node`
8. `replan_node`
9. `unverifiable_finalize_node`
10. `clarify_node` (referenced as the route on comprehension mismatch)

Plus the four executor branches inside fanout if you count those separately. So either 9 (drop `clarify_node` or drop `executor_fanout` as "not a node, a meta-node") or 10. The doc set should pick a definition and align.
**Fix:** Either define `clarify_node` as not-a-node (reclassify as a sub-state of `comprehension_gate`) and leave the 9 figure, or update both docs to 10. `BUILD_PLAN.md` W2.B.1 only enumerates "Five core nodes" — recommend re-stating the full graph node count in one place and citing it from the others.

### H4. "12 documentation files: <16 listed>"

**Where:** `DEVPOST_COMPLIANCE.md` line 146 (Criterion 6 scoring).
**Claim:** "12 documentation files: README, ARCHITECTURE, BUILD, THREAT_MODEL, FAILURE_MODES, CLI, CHECKPOINTING, CASE_ISOLATION, SCOPE, SCHEMA_MIGRATION, SANS_JUDGE_CHECKLIST, ACCURACY_REPORT, EVIDENCE_DATASET, NOVEL_CONTRIBUTION, DEMO_SEQUENCE, PRODUCTION_AUDIT".
**Reality:** That list has **16 names**, not 12. (`README.md` line 341 also claims "16 doc files" — README is right, this doc is wrong.)
**Fix:** "16 documentation files: …"

### H5. Part 6 checklist count drift

**Where:** `DEVPOST_COMPLIANCE.md` line 248 (W6.D.4.a).
**Reality:** Part 6 (lines ~190–208) lists 19 internal release checks, not 18. These are finer-grained than Devpost's eight required components: repo/license/README state, build reproducibility, required docs, execution-log files, video constraints, secrets check, tag push, and form receipt.
**Fix:** Replace the old numeric fraction language with "every checklist item" or "all 19 internal checks", and keep a separate sentence that Devpost itself requires eight submission components.

### H6. README roadmap header "9 vol3 wrappers" disagrees with BUILD_PLAN's 10

**Where:** `README.md` line 228 ("Tim │████████████████│ 9 vol3 wrappers + ledger") in the Week 2 roadmap.
**Reality:** `BUILD_PLAN.md` assigns Tim 9 vol3 wrappers in W2.A (W2.A.1–W2.A.9) **plus** psscan in W1.E.1. The README's "9" only counts W2's vol3 work; it conflicts with the architectural "10 plugins" figure. Cosmetic but the roadmap is what teammates parse weekly.
**Fix:** "10 vol3 wrappers" or "9 vol3 wrappers W2 + 1 W1" — match BUILD_PLAN counting.

---

## MEDIUM — code-level / API issues you'll hit at build time

### M1. `blake3` Python API misuse in `derive_seeds`

**Where:** `ARCHITECTURE.md` lines 23–30, `docs/spec/04-spec-plan-v4.6.md` line 145, `docs/spec/02-audit-v4.4.md` line 43.
**Code as written:**
```python
h = blake3(case_id.encode())
... h.derive_key("seed_a").digest()[:4] ...
```
**Reality:** The `blake3` Python package (PyPI `blake3`) uses **constructor-time** key derivation: `blake3(data, derive_key_context="seed_a").digest()`. There is no `instance.derive_key(...)` method on a hasher object. Calling it as written will raise `AttributeError`. The MITRE-correct API is:
```python
def derive_seeds(case_id: str) -> tuple[int, int, int]:
    enc = case_id.encode()
    return tuple(
        int.from_bytes(blake3(enc, derive_key_context=f"verdict seed {tag}").digest()[:4], "big")
        for tag in ("a", "b", "c")
    )
```
(Note also: `derive_key_context` per the BLAKE3 spec wants a static, application-unique string; embedding the `case_id` as the *input* and rotating the *context* is the right shape.)
**Impact:** W1.C.1 task (`derive_seeds(case_id)` helper) will fail its first test as written. This is the seed of the whole CloudSelfConsistency story.
**Fix:** Update the snippet in `ARCHITECTURE.md` and the v4.6 spec; update the W1.C.1 implementation accordingly.

### M2. "Microsandbox is beta" — partial fact

**Where:** `ARCHITECTURE.md` line 362, `README.md` "Risk #1".
**Reality:** Microsandbox is published as Apache-2.0 (`zerocore-ai/microsandbox`) and is on PyPI as `microsandbox` 0.1.x. There is no formal "beta" label on the GitHub releases — but the 0.1.x version is consistent with pre-1.0 / "early adopter" status. Calling it "beta" is reasonable risk-language; just acknowledge that's a judgment call rather than a vendor designation.
**Fix:** Reword Risk #1 from "it's beta" to "it's pre-1.0 (latest 0.1.x)" — more defensible if a judge probes.

### M3. Microsandbox `network=False` plus TSI Pattern 2 — contradictory by default

**Where:** `ARCHITECTURE.md` §6 Pattern 1 sets `network=False`; Pattern 2 wants outbound HTTPS to `opencti.local:8080`.
**Reality:** TSI works by intercepting the VM's network egress at the vsock/proxy layer; you'll need `network=True` (or a TSI-managed network namespace) for Pattern 2 — `network=False` would block the outbound call entirely. The doc doesn't explicitly resolve this.
**Fix:** Make explicit that Pattern 2 spawns with `network=TSI(...)` (which implies network access via the proxy) and contrast with Pattern 1's hard `network=False`. Add a one-line note: "Pattern 2 intentionally allows TSI-mediated egress; nothing else."

### M4. `verdict reverify` flag mismatch

**Where:** `ARCHITECTURE.md` line 11 says `verdict reverify <case_id> --mode <new>`. `DEVPOST_COMPLIANCE.md` line 134 says `verdict reverify <case_id> --mode dual`. Both consistent with each other, but `BUILD_PLAN.md` W3.C.2 gives no flag spec — fine, and `README.md` "Quick reference" doesn't list it.
**Fix:** Add `verdict reverify` to the README CLI list and the W3.C.2 task description so this command's surface is documented in one canonical place.

---

## LOW — verified accurate (no action)

These were checked and hold up.

- **arXiv 2203.11171** Wang et al. 2022 self-consistency — ✓ correct title, authors, date.
- **arXiv 2309.11495** Dhuliawala 2023 Chain-of-Verification — ✓ correct title, authors, date.
- **anthropics/claude-code #33106** PreToolUse deny not enforced for MCP tools — ✓ exists, status "closed: not planned" as of recent.
- **anthropics/claude-code #37210** PreToolUse deny ignored for Edit tool — ✓ exists.
- **NIST SP 800-86** "Guide to Integrating Forensic Techniques into Incident Response" — ✓ real publication, §5.1.x covers data preservation/acquisition (referenced section numbers are plausible; you can defend them by quoting page numbers).
- **MITRE T1036.005** Match Legitimate Name or Location — ✓ valid sub-technique.
- **MITRE T1055.012** Process Hollowing — ✓ valid sub-technique.
- **MITRE T1059, T1106, T1204, T1218, T1543, T1547** (execution-claim trigger list) — all ✓ valid technique IDs.
- **Qwen3-30B-A3B-Thinking-2507** released July 2025 under Apache-2.0 — ✓ confirmed on Hugging Face.
- **GLM-4.5-Air** under MIT (zai-org) — ✓ confirmed on Hugging Face / GitHub.
- **Microsandbox** Apache-2.0, libkrun-based — ✓ confirmed.
- **SANS Find Evil** deadline Jun 15 2026 11:45 PM EDT — ✓ matches `findevil.devpost.com/rules`.
- **Judging window** Jun 19 – Jul 3 2026, winners ~Jul 8 — ✓ matches.
- **SANS Institute** as sponsor — ✓ matches.
- **6 equally weighted judging criteria** — ✓ matches Devpost rules; the prior "5 of 6" framing is correctly called out as wrong (DEVPOST_COMPLIANCE Part 3 intro).
- **License attributions** for the stack table (`ARCHITECTURE.md` §7) — spot-checked SGLang Apache-2.0, LangGraph MIT, Pydantic MIT, FastMCP Apache-2.0, NeMo Guardrails Apache-2.0, Inspect AI MIT — all match upstream.
- **License "hard nos"** — Daytona AGPL-3.0, REMnux GPL-3.0 — match upstream.
- **6-week window math** — May 2 → Jun 14 EOD against a Jun 15 23:45 EDT deadline = ~28h buffer. ✓ correct.

---

## Summary punchlist (priority order)

1. **C1**: Replace `T1014.001` with `T1014` everywhere in `README.md`, `ARCHITECTURE.md`, `DEVPOST_COMPLIANCE.md`. (3 files, ~6 occurrences.)
2. **M1**: Fix the `derive_seeds` blake3 snippet — `blake3(data, derive_key_context=...)` constructor pattern, not `instance.derive_key(...)`. Otherwise W1.C.1's first test will fail.
3. **C2**: `DEVPOST_COMPLIANCE.md` line 220 — replace "RFC-2119 standard MIT" with "OSI-canonical MIT (SPDX `MIT`)".
4. **H1+H2**: Decide whether `windows.info` gets a wrapper, then update vol3 plugin count (10 vs 11) and total wrapper count (19 → 23 or 24) consistently across `README.md`, `ARCHITECTURE.md`, `DEVPOST_COMPLIANCE.md`, `BUILD_PLAN.md`.
5. **H3**: Pick a single canonical node count (9 or 10) and align `BUILD_PLAN.md` line 565, `DEVPOST_COMPLIANCE.md` line 63, and `ARCHITECTURE.md` §2.
6. **H4**: `DEVPOST_COMPLIANCE.md` line 146 — "12" → "16".
7. **H5**: `DEVPOST_COMPLIANCE.md` line 248 — replace "18" with "every checklist item" or "19 internal checks" while preserving the Devpost eight-component requirement.
8. **C3**: Bump `vol3 2.10.0` example to a current version (or template it).
9. **H6**: README W2 roadmap "9 vol3 wrappers" → align with BUILD_PLAN's 10.
10. **M3**: One-line clarification on Pattern 2 TSI vs Pattern 1 `network=False`.
11. **M4**: Add `verdict reverify` to the README's Quick Reference CLI block.

**Estimated fix effort:** under 90 minutes total. None require re-architecting; all are find-and-replace or single-paragraph rewrites. Do them before the W1.B schema freeze (May 8) so the docs match the schemas you're locking.

---

## Resolution log (2026-05-02)

All 11 punchlist items closed in two passes:

| # | Item | Status | Where |
|---|---|---|---|
| C1 | `T1014.001` → `T1014` | ✅ closed | `README.md`, `docs/ARCHITECTURE.md`, `docs/DEVPOST_COMPLIANCE.md` |
| C2 | "RFC-2119 standard MIT" → "OSI-canonical MIT" | ✅ closed | `docs/DEVPOST_COMPLIANCE.md` W6.D.0.b |
| C3 | vol3 example version `2.10.0` → `2.28.0` (with build-time pin note) | ✅ closed | `docs/ARCHITECTURE.md` Pattern 1 |
| H1 | vol3 plugin count: dropped `windows.info` from typed list (10 plugins, matches BUILD_PLAN). Note: `windows.info` is still invokable through the dynamic vol3 allow-list (`§6 Tool-call argument validation`). | ✅ closed | `docs/ARCHITECTURE.md` §6 |
| H2 | "19 wrappers" → "23 wrappers" (10 vol3 + 2 hayabusa + 2 plaso + 9 other) | ✅ closed | `docs/ARCHITECTURE.md` §6 header, `docs/DEVPOST_COMPLIANCE.md` line 89 |
| H3 | 9-node count: aligned by removing "executor_work" as a separate node in CLAUDE.md and BUILD_PLAN.md (it's the in-fanout composition); clarified `clarify_node` is a sub-state of `comprehension_gate` in ARCHITECTURE.md §2 | ✅ closed | `CLAUDE.md` §4, `docs/BUILD_PLAN.md` Week 2 critical-path, `docs/ARCHITECTURE.md` §2 |
| H4 | "12 documentation files" → "16 documentation files" | ✅ closed | `docs/DEVPOST_COMPLIANCE.md` line 146 |
| H5 | Old checklist-count wording → "every checklist item ticked" | ✅ closed | `docs/DEVPOST_COMPLIANCE.md` W6.D.4.a + `docs/BUILD_PLAN.md` W6.D.3 |
| H6 | README W2 roadmap "9 vol3 wrappers" reference removed during 2026-05-02 doc refactor | ✅ closed | `README.md` (no current occurrence) |
| M1 | `blake3` API: keyed-hash mode `blake3(data, key=_SEED_DERIVATION_KEY)` (not `instance.derive_key()`); 32-byte key held in module constant | ✅ closed | `docs/ARCHITECTURE.md` §1 `derive_seeds` snippet; `src/verdict/verification/derive_seeds.py` |
| M3 | Pattern 2 TSI vs Pattern 1 `network=False`: explicit one-paragraph clarification added | ✅ closed | `docs/ARCHITECTURE.md` Pattern 2 |
| M4 | `verdict reverify` surfaced in README CLI block with parallel-chain note | ✅ closed | `README.md` Quick reference |

**Re-audit cadence:** re-run this audit before the W1.B schema freeze and before each major doc commit; track new findings as `C/H/M/L` items appended to the relevant section above.
