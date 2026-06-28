"""SCOPE Packet rendering for reviewer display."""

from __future__ import annotations

from html import escape
from typing import Any

from scope.policy import PolicyStore
from scope.scopes import (
    allowed_tools_for_scope,
    blocked_tools_for_scope,
    resolve_requested_scope_from_tool,
)

NON_CERTIFICATION = (
    "This display is for review coordination only. It does not constitute "
    "certification, legal authorization, or institutional approval."
)


def _section(title: str, lines: list[str]) -> str:
    body = "\n".join(f"- {line}" for line in lines)
    return f"## {title}\n\n{body}\n"


def _scope_explanation(scope: str, policy: PolicyStore | None) -> str:
    if not policy:
        return scope
    semantics = policy.scope_semantics.get(scope, {})
    desc = semantics.get("description")
    return f"{scope}: {desc}" if desc else scope


def _blocked_tool_severity(tool: str, policy: PolicyStore | None) -> str:
    severity_cfg = policy.blocked_tool_severity if policy else {}
    high = set(severity_cfg.get("high_severity", []))
    policy_label = severity_cfg.get("policy_blocked_label", "policy blocked")
    all_label = severity_cfg.get("all_tools_label", "all tools blocked")
    if tool in high:
        return f"{tool} (high severity — operational or escalation risk)"
    if tool == "*":
        return f"* ({all_label})"
    return f"{tool} ({policy_label})"


def _evidence_warning(ctx: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    evidence = ctx.get("evidence_state", "")
    validation = ctx.get("validation_status", "")
    if evidence in ("E0_unknown", "E1_hypothesis", ""):
        warnings.append(f"Evidence state is weak or unknown: {evidence or 'missing'}")
    if validation in ("V0_unknown", ""):
        warnings.append(f"Validation status is weak or unknown: {validation or 'missing'}")
    return warnings


def _reviewer_checklist(req: dict[str, Any], packet: dict[str, Any]) -> list[str]:
    roles = req.get("required_review_roles", [])
    return [
        f"Confirm your role is one of: {', '.join(roles) or 'see policy'}",
        "Verify requested action and tool match the scientific context",
        "Select the weakest approval scope supported by evidence",
        "Document rationale for approve, reject, or request-more-evidence",
        "Declare conflicts of interest before submitting a decision",
        f"Allowed decision types: {', '.join(packet.get('decision_options', []))}",
    ]


def render_markdown(packet: dict[str, Any], policy: PolicyStore | None = None) -> str:
    """Render packet as markdown for reviewer display."""
    req = packet.get("review_request", {})
    ctx = packet.get("scientific_context", {})
    source = packet.get("source", {})
    constraints = packet.get("akta_constraints", {})

    requested_scope = req.get("requested_scope")
    review_route = req.get("review_route")
    scope_source = req.get("scope_inference_source", "unknown")

    allowed_steps = ", ".join(constraints.get("allowed_next_steps", [])) or "none"
    blocked_tools = constraints.get("blocked_tools", [])

    sections: list[str] = [
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
                f"Requested scope: {requested_scope or 'unknown (see inference)'}",
                f"Review route: {review_route or 'none'}",
                f"Scope inference source: {scope_source}",
                f"Admissibility: {req.get('akta_admissibility', 'unknown')}",
            ],
        ),
    ]

    if req.get("akta_decision_reason"):
        sections.append(
            _section("AKTA Decision Reason", [str(req["akta_decision_reason"])])
        )

    sections.extend(
        [
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
        ]
    )

    evidence_warnings = _evidence_warning(ctx)
    if evidence_warnings:
        sections.append(_section("Evidence and Validation Warnings", evidence_warnings))

    if blocked_tools:
        sections.append(
            _section(
                "Blocked Tools (severity)",
                [_blocked_tool_severity(tool, policy) for tool in blocked_tools],
            )
        )

    sections.append(
        _section(
            "AKTA Constraints",
            [
                f"Blocked tools: {', '.join(blocked_tools) or 'none'}",
                f"Allowed next steps: {allowed_steps}",
            ],
        )
    )

    if policy and requested_scope:
        scope_errors: list[str] = []
        try:
            allowed = allowed_tools_for_scope(requested_scope, policy)
            scope_blocked = blocked_tools_for_scope(requested_scope, policy)
            sections.append(
                _section(
                    "Approval Scope Context",
                    [_scope_explanation(requested_scope, policy)],
                )
            )
            sections.append(
                _section(
                    "Approval Permits",
                    allowed or ["No tools permitted at this scope"],
                )
            )
            not_permitted: list[str] = list(scope_blocked)
            inferred = resolve_requested_scope_from_tool(req.get("requested_tool", ""), policy)
            if inferred and inferred != requested_scope:
                stronger_allowed = allowed_tools_for_scope(inferred, policy)
                for tool in stronger_allowed:
                    if tool not in allowed and tool not in not_permitted:
                        not_permitted.append(tool)
            sections.append(
                _section(
                    "Approval Does NOT Permit",
                    not_permitted or ["No additional restrictions beyond scope policy"],
                )
            )
        except Exception as exc:
            scope_errors.append(f"Could not resolve scope policy context: {exc}")
        if scope_errors:
            sections.append(_section("Render Errors", scope_errors))

    sections.extend(
        [
            _section(
                "Decision Options",
                [f"Allowed: {', '.join(packet.get('decision_options', []))}"],
            ),
            _section("Reviewer Checklist", _reviewer_checklist(req, packet)),
            f"\n---\n\n{NON_CERTIFICATION}\n",
        ]
    )
    return "\n".join(sections)


def render_html(packet: dict[str, Any], policy: PolicyStore | None = None) -> str:
    md = render_markdown(packet, policy)
    lines: list[str] = []
    in_list = False
    for line in md.splitlines():
        if line.startswith("# "):
            if in_list:
                lines.append("</ul>")
                in_list = False
            lines.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_list:
                lines.append("</ul>")
                in_list = False
            lines.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("- "):
            if not in_list:
                lines.append("<ul>")
                in_list = True
            lines.append(f"<li>{escape(line[2:])}</li>")
        elif line.startswith("*") and line.endswith("*"):
            if in_list:
                lines.append("</ul>")
                in_list = False
            lines.append(f"<p><em>{escape(line.strip('*'))}</em></p>")
        elif line.strip() == "---":
            if in_list:
                lines.append("</ul>")
                in_list = False
            lines.append("<hr>")
        elif line.strip():
            if in_list:
                lines.append("</ul>")
                in_list = False
            lines.append(f"<p>{escape(line)}</p>")
    if in_list:
        lines.append("</ul>")
    body = "\n".join(lines)
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<title>SCOPE Review Packet</title></head><body>"
        f"{body}</body></html>"
    )
