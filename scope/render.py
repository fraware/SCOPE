"""SCOPE Packet rendering for reviewer display."""

from __future__ import annotations

from html import escape
from typing import Any

NON_CERTIFICATION = (
    "This display is for review coordination only. It does not constitute "
    "certification, legal authorization, or institutional approval."
)


def _section(title: str, lines: list[str]) -> str:
    body = "\n".join(f"- {line}" for line in lines)
    return f"## {title}\n\n{body}\n"


def render_markdown(packet: dict[str, Any]) -> str:
    """Render packet as markdown for reviewer display."""
    req = packet.get("review_request", {})
    ctx = packet.get("scientific_context", {})
    source = packet.get("source", {})
    constraints = packet.get("akta_constraints", {})

    allowed_steps = ", ".join(constraints.get("allowed_next_steps", [])) or "none"

    sections = [
        "# SCOPE Review Packet\n",
        f"*{NON_CERTIFICATION}*\n",
        _section(
            "Identification",
            [
                f"Packet ID: {packet.get('packet_id', 'unknown')}",
                f"AKTA Record: {source.get('akta_record_id', 'unknown')}",
                f"Created: {packet.get('created_at', 'unknown')}",
            ],
        ),
        _section(
            "Requested Action",
            [
                f"Action: {req.get('requested_action', 'unknown')}",
                f"Tool: {req.get('requested_tool', 'unknown')}",
                f"Action type: {req.get('scientific_action_type', 'unknown')}",
                f"Requested scope: {req.get('requested_scope', 'unknown')}",
                f"Scope source: {req.get('scope_inference_source', 'unknown')}",
                f"Admissibility: {req.get('akta_admissibility', 'unknown')}",
            ],
        ),
        _section(
            "Required Reviewers",
            [f"Roles: {', '.join(req.get('required_review_roles', []))}"],
        ),
        _section(
            "Scientific Context",
            [
                f"Domain: {ctx.get('domain', 'unknown')}",
                f"Evidence state: {ctx.get('evidence_state', 'unknown')}",
                f"Validation status: {ctx.get('validation_status', 'unknown')}",
                f"Verification status: {ctx.get('verification_status', 'unknown')}",
                f"Protocol version: {ctx.get('protocol_version', 'unknown')}",
            ],
        ),
        _section(
            "AKTA Constraints",
            [
                f"Blocked tools: {', '.join(constraints.get('blocked_tools', [])) or 'none'}",
                f"Allowed next steps: {allowed_steps}",
            ],
        ),
        _section(
            "Decision Options",
            [f"Allowed: {', '.join(packet.get('decision_options', []))}"],
        ),
        f"\n---\n\n{NON_CERTIFICATION}\n",
    ]
    return "\n".join(sections)


def render_html(packet: dict[str, Any]) -> str:
    md = render_markdown(packet)
    lines = []
    for line in md.splitlines():
        if line.startswith("# "):
            lines.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("## "):
            lines.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("- "):
            lines.append(f"<li>{escape(line[2:])}</li>")
        elif line.startswith("*") and line.endswith("*"):
            lines.append(f"<p><em>{escape(line.strip('*'))}</em></p>")
        elif line.strip() == "---":
            lines.append("<hr>")
        elif line.strip():
            lines.append(f"<p>{escape(line)}</p>")
    body = "\n".join(lines)
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>SCOPE Review Packet</title></head><body>"
        f"{body}</body></html>"
    )
