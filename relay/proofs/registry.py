"""Every proof, one import, one page."""

from __future__ import annotations

import importlib

from relay.proofs.finding import Finding

PROOFS = (
    "relay.proofs.watermarkholds",
    "relay.proofs.exactlyonce",
    "relay.proofs.nostall",
    "relay.proofs.retentionfloor",
)


def all_findings() -> list[Finding]:
    findings = []
    for dotted in PROOFS:
        module = importlib.import_module(dotted)
        findings.append(module.run())
    return findings


def broken() -> list[str]:
    return [
        finding.proof
        for finding in all_findings()
        if not finding.holds
    ]


def report() -> str:
    findings = all_findings()
    lines = [finding.line() for finding in findings]
    failing = sum(1 for finding in findings if not finding.holds)
    lines.append("")
    lines.append(f"{len(findings)} proofs, {failing} broken")
    return "\n".join(lines)
