from __future__ import annotations

import html
import json
import re
import textwrap
from collections.abc import Iterable
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any


def build_analyst_report_html(case_id: str, entries: list[dict[str, Any]]) -> str:
    entries = _entries_with_citation_ordinals(entries)
    citations = _citations(entries)
    conclusion = _latest_payload(entries, "case_conclusion")
    findings = [entry for entry in entries if entry.get("event_type") == "finding"]
    evidence_items = _evidence_items(entries)
    timeline_rows = "\n".join(_timeline_row(entry) for entry in entries)
    evidence_rows = "\n".join(_evidence_row(item) for item in evidence_items)
    finding_cards = "\n".join(_finding_card(entry, citations) for entry in findings)
    figure_cards = "\n".join(_evidence_figure(citation) for citation in citations)
    appendix_rows = "\n".join(_chain_row(entry) for entry in entries)
    status = conclusion.get("status", "NO_CASE_CONCLUSION")
    rationale = conclusion.get("rationale", "No terminal case conclusion is present yet.")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>VERDICT Analyst Report - {html.escape(case_id)}</title>
<style>
body {{ font-family: Arial, sans-serif; line-height: 1.45; margin: 2rem; color: #172033; }}
h1, h2, h3 {{ color: #0f2742; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ border: 1px solid #bac4d1; padding: 0.45rem; vertical-align: top; }}
th {{ background: #eef3f8; text-align: left; }}
.finding, figure {{ border: 1px solid #9fb1c5; padding: 1rem; margin: 1rem 0; }}
.citation {{ font-family: Consolas, monospace; color: #143d66; }}
.review li {{ margin: 0.35rem 0; }}
svg {{ width: 100%; max-width: 980px; height: auto; border: 1px solid #cbd5df; }}
</style>
</head>
<body>
<h1>VERDICT Analyst Report</h1>
<p><strong>Case:</strong> {html.escape(case_id)}</p>
<section>
<h2>Executive Summary</h2>
<p><strong>Case conclusion:</strong> {html.escape(str(status))}</p>
<p>{html.escape(str(rationale))}</p>
</section>
<section class="review">
<h2>Human Review Checklist</h2>
<ul>
<li>Confirm every narrative claim cites a <span class="citation">CIT-####</span> item.</li>
<li>Verify evidence hashes against the case manifest before relying on findings.</li>
<li>Review rendered evidence figures and linked tool-output hashes for each finding.</li>
<li>Confirm caveats are acknowledged before approving execution claims.</li>
<li>Approve or reject findings only after the cited artifacts prove the claim.</li>
</ul>
</section>
<section>
<h2>Evidence Inventory</h2>
<table><thead><tr><th>Type</th><th>Path</th><th>SHA-256</th><th>Size</th></tr></thead>
<tbody>{evidence_rows}</tbody></table>
</section>
<section>
<h2>Investigation Timeline</h2>
<table><thead><tr><th>UTC</th><th>Event</th><th>Checkpoint</th><th>Citation</th></tr></thead>
<tbody>{timeline_rows}</tbody></table>
</section>
<section>
<h2>Findings And Citations</h2>
{finding_cards or '<p>No finding entries are present in the ledger.</p>'}
</section>
<section>
<h2>Evidence Figures</h2>
{figure_cards}
</section>
<section>
<h2>Chain Of Custody Appendix</h2>
<table><thead><tr><th>UTC</th><th>Event</th><th>Entry Hash</th><th>HMAC</th></tr></thead>
<tbody>{appendix_rows}</tbody></table>
</section>
</body>
</html>
"""


def build_analyst_report_pdf(case_id: str, entries: list[dict[str, Any]]) -> bytes:
    entries = _entries_with_citation_ordinals(entries)
    return _pdf_from_lines(_plain_report_lines(case_id, entries))


def _entries_with_citation_ordinals(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**entry, "_citation_ordinal": index} for index, entry in enumerate(entries, start=1)]


def _latest_payload(entries: list[dict[str, Any]], event_type: str) -> dict[str, Any]:
    for entry in reversed(entries):
        if entry.get("event_type") == event_type:
            payload = entry.get("payload", {})
            return payload if isinstance(payload, dict) else {}
    return {}


def _evidence_items(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for entry in entries:
        if entry.get("event_type") != "case_init":
            continue
        payload = entry.get("payload", {})
        items = payload.get("evidence_items", []) if isinstance(payload, dict) else []
        return [item for item in items if isinstance(item, dict)]
    return []


def _citations(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        citation_id = f"CIT-{index:04d}"
        citations.append({"citation_id": citation_id, "entry": entry})
    return citations


def _citation_for(entry: dict[str, Any], citations: list[dict[str, Any]]) -> str:
    for citation in citations:
        if citation["entry"] is entry:
            return str(citation["citation_id"])
    return "UNCITED"


def _timeline_row(entry: dict[str, Any]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(str(entry.get('timestamp_utc', '')))}</td>"
        f"<td>{html.escape(str(entry.get('event_type', '')))}</td>"
        f"<td>{html.escape(str(entry.get('langgraph_checkpoint_id', '')))}</td>"
        f"<td><a class=\"citation\" href=\"#fig-{html.escape(str(entry.get('entry_hash', '')))}\">"
        f"{html.escape(str(_entry_citation_id(entry)))}</a></td>"
        "</tr>"
    )


def _entry_citation_id(entry: dict[str, Any]) -> str:
    ordinal = entry.get("_citation_ordinal")
    if isinstance(ordinal, int):
        return f"CIT-{ordinal:04d}"
    return "CIT-????"


def _evidence_row(item: dict[str, Any]) -> str:
    display_path = _public_path(str(item.get("path", "")))
    return (
        "<tr>"
        f"<td>{html.escape(str(item.get('evidence_type', '')))}</td>"
        f"<td>{html.escape(display_path)}</td>"
        f"<td class=\"citation\">{html.escape(str(item.get('sha256_at_init', '')))}</td>"
        f"<td>{html.escape(str(item.get('size_bytes', '')))}</td>"
        "</tr>"
    )


def _finding_card(entry: dict[str, Any], citations: list[dict[str, Any]]) -> str:
    payload = entry.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    citation_id = _citation_for(entry, citations)
    artifact_paths = _html_list(
        _public_path(str(path)) for path in payload.get("artifact_paths", [])
    )
    caveats = _html_list(payload.get("caveats_acknowledged", []))
    finding_id = html.escape(str(payload.get("finding_id", entry.get("finding_id", "finding"))))
    status = html.escape(str(payload.get("status", "")))
    review_state = html.escape(str(payload.get("review_state", "DRAFT")))
    mitre = html.escape(str(payload.get("mitre_technique", "")))
    rationale = html.escape(str(payload.get("rationale", "")))
    supporting = _html_list(
        output.get("tool_name", "tool_output")
        for output in payload.get("supporting_tool_outputs", [])
        if isinstance(output, dict)
    )
    return f"""<article class="finding">
<h3>{finding_id}</h3>
<p><strong>Citation:</strong> <span class="citation">{html.escape(citation_id)}</span></p>
<p><strong>Status:</strong> {status}; <strong>Review:</strong> {review_state}</p>
<p><strong>MITRE:</strong> {mitre}</p>
<p>{rationale}</p>
<p><strong>Artifact paths:</strong></p>{artifact_paths}
<p><strong>Caveats acknowledged:</strong></p>{caveats}
<p><strong>Supporting tool outputs:</strong></p>{supporting}
</article>"""


def _html_list(values: Iterable[Any]) -> str:
    items = "".join(f"<li>{html.escape(str(value))}</li>" for value in values)
    return f"<ul>{items}</ul>" if items else "<p>None recorded.</p>"


def _evidence_figure(citation: dict[str, Any]) -> str:
    citation_id = str(citation["citation_id"])
    entry = citation["entry"]
    entry_hash = str(entry.get("entry_hash", citation_id))
    title = f"Evidence Figure {citation_id}: {entry.get('event_type', 'event')}"
    lines = _figure_lines(entry)
    svg_lines = "".join(
        f"<text x=\"24\" y=\"{56 + (line_index * 22)}\">{html.escape(line)}</text>"
        for line_index, line in enumerate(lines[:10])
    )
    height = 88 + (min(len(lines), 10) * 22)
    escaped_title = html.escape(title)
    title_text = (
        '<text x="24" y="32" font-family="Consolas, monospace" '
        f'font-size="18" fill="#0f2742">{escaped_title}</text>'
    )
    return f"""<figure id="fig-{html.escape(entry_hash)}">
<figcaption><span class="citation">{html.escape(citation_id)}</span> {escaped_title}</figcaption>
<svg viewBox="0 0 1000 {height}" role="img" aria-label="{escaped_title}">
<rect x="8" y="8" width="984" height="{height - 16}" fill="#f7fafc" stroke="#46617a"/>
{title_text}
<g font-family="Consolas, monospace" font-size="16" fill="#172033">{svg_lines}</g>
</svg>
</figure>"""


def _figure_lines(entry: dict[str, Any]) -> list[str]:
    payload = entry.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}
    lines = [
        f"UTC: {entry.get('timestamp_utc', '')}",
        f"Checkpoint: {entry.get('langgraph_checkpoint_id', '')}",
        f"Entry hash: {entry.get('entry_hash', '')}",
    ]
    if entry.get("event_type") == "tool_call":
        lines.extend(
            [
                f"Tool: {payload.get('tool_name', '')}",
                f"Exit code: {payload.get('exit_code', '')}",
                f"Stdout SHA-256: {payload.get('stdout_hash', '')}",
                f"Output path: {_public_path(str(payload.get('tool_output_path', '')))}",
                f"Artifact IDs: {', '.join(map(str, payload.get('artifact_ids', [])))}",
            ]
        )
    elif entry.get("event_type") == "finding":
        lines.extend(
            [
                f"Finding: {payload.get('finding_id', entry.get('finding_id', ''))}",
                f"Status: {payload.get('status', '')}",
                f"MITRE: {payload.get('mitre_technique', '')}",
                f"Caveats: {', '.join(map(str, payload.get('caveats_acknowledged', [])))}",
                f"Rationale: {payload.get('rationale', '')}",
            ]
        )
    elif entry.get("event_type") == "case_conclusion":
        lines.extend(
            [
                f"Conclusion: {payload.get('status', '')}",
                f"Rationale: {payload.get('rationale', '')}",
            ]
        )
    return [line[:118] for line in lines]


def _chain_row(entry: dict[str, Any]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(str(entry.get('timestamp_utc', '')))}</td>"
        f"<td>{html.escape(str(entry.get('event_type', '')))}</td>"
        f"<td class=\"citation\">{html.escape(str(entry.get('entry_hash', '')))}</td>"
        f"<td class=\"citation\">{html.escape(str(entry.get('hmac_sig', '')))}</td>"
        "</tr>"
    )


def _plain_report_lines(case_id: str, entries: list[dict[str, Any]]) -> list[str]:
    conclusion = _latest_payload(entries, "case_conclusion")
    evidence_items = _evidence_items(entries)
    latest_run_entries = _latest_run_entries(entries)
    latest_findings = [
        entry for entry in latest_run_entries if entry.get("event_type") == "finding"
    ]
    superseded = _superseded_conclusions(entries)
    status = str(conclusion.get("status", "NO_CASE_CONCLUSION"))
    rationale = _professional_rationale(str(conclusion.get("rationale", "")))
    lines = [
        "VERDICT DFIR Analyst Report",
        "VERDICT Analyst Report",
        f"Case ID: {case_id}",
        "Report purpose: professional writeup for final examiner review",
        "Review state: human approval required before external reliance",
        "",
        "Executive Assessment",
        f"Final case status: {status}",
        f"Assessment: {rationale or 'No terminal case conclusion is present yet.'}",
        (
            "Scope note: this writeup summarizes the latest case run. Earlier failed or "
            "unverifiable attempts are preserved in Superseded Run History and chain of custody."
            if superseded
            else "Scope note: this writeup summarizes the case ledger and cited evidence."
        ),
        "",
        "Human Review Checklist",
        "[ ] Every claim has a CIT-#### citation.",
        "[ ] Evidence hashes match the case manifest.",
        "[ ] Key Findings match the cited ledger evidence cards.",
        "[ ] Caveats are acknowledged before approving findings.",
        "",
        "Key Findings",
    ]
    lines.extend(_key_finding_lines(latest_findings, status))
    lines.extend(["", "Evidence And Citation Summary", "Evidence inventory:"])
    for item in evidence_items:
        lines.append(_professional_evidence_line(item))
    if not evidence_items:
        lines.append("- No case_init evidence inventory was found in the ledger.")
    lines.extend(["", "Latest run evidence:"])
    lines.extend(_latest_run_citation_lines(latest_run_entries))
    if superseded:
        lines.extend(["", "Superseded Run History"])
        lines.extend(_superseded_run_lines(superseded))
    lines.extend(
        [
            "",
            "Ledger Evidence Appendix",
            "The cards below are concise ledger-derived evidence figures. Raw tool "
            "output paths and hashes remain available in the case output directory "
            "and JSONL ledger.",
        ]
    )
    for entry in latest_run_entries:
        lines.append(f"Evidence Figure {_entry_citation_id(entry)}: {entry.get('event_type', '')}")
        lines.extend(f"  {line}" for line in _professional_figure_lines(entry))
    lines.extend(["", "Chain Of Custody Appendix"])
    for entry in entries:
        lines.append(
            f"{_entry_citation_id(entry)} {entry.get('timestamp_utc', '')} "
            f"{entry.get('event_type', '')} "
            f"entry_hash={entry.get('entry_hash', '')} hmac={entry.get('hmac_sig', '')}"
        )
    return _wrap_lines(lines)


def _latest_run_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest_conclusion_index = _latest_conclusion_index(entries)
    if latest_conclusion_index is None:
        return entries
    previous_conclusion_index = None
    for index in range(latest_conclusion_index - 1, -1, -1):
        if entries[index].get("event_type") == "case_conclusion":
            previous_conclusion_index = index
            break
    start = 0 if previous_conclusion_index is None else previous_conclusion_index + 1
    return entries[start : latest_conclusion_index + 1]


def _latest_conclusion_index(entries: list[dict[str, Any]]) -> int | None:
    for index in range(len(entries) - 1, -1, -1):
        if entries[index].get("event_type") == "case_conclusion":
            return index
    return None


def _superseded_conclusions(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest_index = _latest_conclusion_index(entries)
    if latest_index is None:
        return []
    return [
        entry
        for index, entry in enumerate(entries)
        if index < latest_index and entry.get("event_type") == "case_conclusion"
    ]


def _professional_rationale(rationale: str) -> str:
    return _abbreviate_pid_list(rationale) if rationale else ""


def _abbreviate_pid_list(value: str, *, keep: int = 12) -> str:
    match = re.search(r"(psscan PID\(s\) absent from pslist:\s*)([0-9,\s]+)(\.)?", value)
    if not match:
        return value
    pids = [pid.strip() for pid in match.group(2).split(",") if pid.strip()]
    if len(pids) <= keep:
        return value
    omitted = len(pids) - keep
    abbreviated = f"{match.group(1)}{', '.join(pids[:keep])} ({omitted} additional PIDs omitted)"
    suffix_start = match.end(3) if match.group(3) else match.end(2)
    return value[: match.start()] + abbreviated + value[suffix_start:]


def _key_finding_lines(findings: list[dict[str, Any]], case_status: str) -> list[str]:
    if not findings:
        return [
            "- No separate finding entries were emitted in the latest run.",
            f"- Case-level conclusion: {case_status}; see Latest run evidence citations below.",
        ]
    lines: list[str] = []
    for entry in findings:
        payload = entry.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        finding_status = str(payload.get("status", ""))
        finding_id = payload.get("finding_id", entry.get("finding_id", "finding"))
        artifact_classes = ", ".join(map(str, payload.get("artifact_classes", [])))
        caveats = ", ".join(map(str, payload.get("caveats_acknowledged", [])))
        lines.extend(
            [
                f"- {_entry_citation_id(entry)} {finding_id}",
                f"  Status: {finding_status}; case status: {case_status}",
                f"  MITRE: {payload.get('mitre_technique', 'not recorded')}",
                f"  Artifact classes: {artifact_classes or 'not recorded'}",
                f"  Caveats: {caveats or 'none recorded'}",
                f"  Rationale: {_professional_rationale(str(payload.get('rationale', '')))}",
            ]
        )
        if finding_status and finding_status != case_status:
            lines.append(
                "  Note: finding-level verifier state differs from the case-level conclusion; "
                "human review must resolve this before approval."
            )
    return lines


def _professional_evidence_line(item: dict[str, Any]) -> str:
    return (
        f"- {item.get('evidence_type', '')}: {_public_path(str(item.get('path', '')))}; "
        f"sha256={item.get('sha256_at_init', '')}; size={item.get('size_bytes', '')}"
    )


def _latest_run_citation_lines(entries: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for entry in entries:
        event_type = str(entry.get("event_type", ""))
        if event_type not in {"tool_call", "finding", "case_conclusion"}:
            continue
        payload = entry.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        if event_type == "tool_call":
            detail = f"{payload.get('tool_name', 'tool')} exit={payload.get('exit_code', '')}"
        elif event_type == "finding":
            detail = str(payload.get("finding_id", entry.get("finding_id", "finding")))
        else:
            detail = f"case conclusion {payload.get('status', '')}"
        lines.append(
            f"- {_entry_citation_id(entry)} {entry.get('timestamp_utc', '')} {event_type}: {detail}"
        )
    return lines or ["- No latest-run tool, finding, or conclusion entries were available."]


def _superseded_run_lines(entries: list[dict[str, Any]]) -> list[str]:
    lines = ["Latest run evidence is authoritative for the executive assessment above."]
    for entry in entries:
        payload = entry.get("payload", {})
        if not isinstance(payload, dict):
            payload = {}
        rationale = _professional_rationale(str(payload.get("rationale", "")))
        lines.append(
            f"- {_entry_citation_id(entry)} {entry.get('timestamp_utc', '')} "
            f"status={payload.get('status', '')}; {rationale}"
        )
    return lines


def _professional_figure_lines(entry: dict[str, Any]) -> list[str]:
    return [_professional_rationale(line) for line in _figure_lines(entry)[:8]]


def _wrap_lines(lines: list[str], width: int = 96) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        if not line:
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(line, width=width, replace_whitespace=False) or [line])
    return wrapped


def _public_path(value: str) -> str:
    if not value:
        return ""
    normalized = value.replace("\\", "/")
    base, separator, fragment = normalized.partition("#")
    for marker in ("/outputs/", "outputs/"):
        if marker in base:
            base = "outputs/" + base.split(marker, 1)[1]
            break
    else:
        if re_match := _windows_drive_path(base):
            base = PureWindowsPath(re_match).name
        else:
            base = PurePosixPath(base).name
    return f"{base}{separator}{fragment}" if separator else base


def _windows_drive_path(value: str) -> str | None:
    return value if len(value) >= 3 and value[1:3] == ":/" else None


def _pdf_from_lines(lines: list[str]) -> bytes:
    pages = [lines[index : index + 48] for index in range(0, len(lines), 48)] or [[]]
    objects: list[bytes | None] = [
        None,
        None,
        None,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
    ]
    page_refs: list[str] = []
    for page_number, page_lines in enumerate(pages, start=1):
        content = _pdf_page_content(page_lines, page_number=page_number, page_count=len(pages))
        content_number = len(objects)
        objects.append(
            b"<< /Length "
            + str(len(content)).encode("ascii")
            + b" >>\nstream\n"
            + content
            + b"\nendstream"
        )
        page_number = len(objects)
        page_refs.append(f"{page_number} 0 R")
        objects.append(
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                "/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
                f"/Contents {content_number} 0 R >>"
            ).encode("ascii")
        )
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = f"<< /Type /Pages /Kids [{' '.join(page_refs)}] /Count {len(pages)} >>".encode(
        "ascii"
    )
    return _assemble_pdf(objects)


def _pdf_page_content(lines: list[str], *, page_number: int, page_count: int) -> bytes:
    commands: list[str] = []
    y_position = 752
    for line in lines:
        if not line:
            y_position -= 8
            continue
        font = "/F1"
        size = 9
        x_position = 50
        if line == "VERDICT DFIR Analyst Report":
            font = "/F2"
            size = 18
            commands.append("q 0.06 0.16 0.28 rg 0 772 612 20 re f Q")
        elif line in _PDF_SECTION_HEADINGS:
            font = "/F2"
            size = 12
            commands.append(f"q 0.90 0.94 0.98 rg 42 {y_position - 4} 528 18 re f Q")
        if line.startswith("Evidence Figure"):
            font = "/F2"
            size = 9
            commands.append(f"q 0.93 0.95 0.98 rg 45 {y_position - 3} 522 14 re f Q")
        elif line.startswith("  "):
            x_position = 62
            size = 8
        elif "entry_hash=" in line or "sha256=" in line:
            font = "/F3"
            size = 7
        commands.extend(
            [
                "BT",
                f"{font} {size} Tf",
                f"{x_position} {y_position} Td",
                f"({_pdf_escape(line)}) Tj",
                "ET",
            ]
        )
        y_position -= 12
    commands.extend(
        [
            "BT",
            "/F1 8 Tf",
            "50 34 Td",
            f"({_pdf_escape(f'Page {page_number} of {page_count}')}) Tj",
            "ET",
        ]
    )
    return "\n".join(commands).encode("latin-1", errors="replace")


_PDF_SECTION_HEADINGS = {
    "Executive Assessment",
    "Human Review Checklist",
    "Key Findings",
    "Evidence And Citation Summary",
    "Superseded Run History",
    "Ledger Evidence Appendix",
    "Chain Of Custody Appendix",
}


def _pdf_escape(value: str) -> str:
    normalized = value.encode("latin-1", errors="replace").decode("latin-1")
    return normalized.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _assemble_pdf(objects: list[bytes | None]) -> bytes:
    pdf = b"%PDF-1.4\n"
    offsets = [0]
    for object_number, body in enumerate(objects[1:], start=1):
        if body is None:
            raise ValueError("pdf object body was not initialized")
        offsets.append(len(pdf))
        pdf += f"{object_number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects)}\n".encode("ascii")
    pdf += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += (
        f"trailer\n<< /Root 1 0 R /Size {len(objects)} >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")
    return pdf


def report_summary_json(case_id: str, entries: list[dict[str, Any]]) -> str:
    conclusion = _latest_payload(entries, "case_conclusion")
    return json.dumps(
        {
            "case_id": case_id,
            "entry_count": len(entries),
            "finding_count": sum(1 for entry in entries if entry.get("event_type") == "finding"),
            "status": conclusion.get("status", "NO_CASE_CONCLUSION"),
        },
        sort_keys=True,
    )
