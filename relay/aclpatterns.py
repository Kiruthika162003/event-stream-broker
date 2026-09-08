"""ACL patterns: literal beats prefix beats wildcard, so specific rules win.

Access rules name resources by pattern, a literal topic name, a
prefix covering a family, or a wildcard covering all, and the
question that decides correctness is which rule applies when
several match. A wildcard deny and a literal allow both match one
topic, and if the wildcard wins the literal allow is dead, while
if the literal wins the wildcard is a default the specific rule
overrides. The evaluator resolves by specificity: a literal match
is more specific than a prefix, a prefix more specific than a
wildcard, and the most specific matching rule decides, so an
operator can write a broad default and carve exceptions from it
the obvious way, deny-all-then-allow-these, without the default
swallowing the exceptions. Among rules of equal specificity a
deny beats an allow, because a security default that resolves
ties toward access is a security default that fails open, and
failing open is the one direction an access system must never
fail. The evaluator names the winning rule and why it won,
because an access decision an operator cannot explain is an
access decision they cannot audit, and the difference between
denied-by-the-wildcard and denied-by-a-specific-rule tells them
whether their allow is missing or overridden, two different
fixes.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid

LITERAL = "literal"
PREFIX = "prefix"
WILDCARD = "wildcard"
SPECIFICITY = {LITERAL: 2, PREFIX: 1, WILDCARD: 0}


@dataclass(frozen=True)
class AclRule:
    pattern_type: str
    pattern: str
    allow: bool

    def __post_init__(self) -> None:
        if self.pattern_type not in SPECIFICITY:
            raise Invalid(
                f"unknown pattern type {self.pattern_type}"
            )

    def matches(self, resource: str) -> bool:
        if self.pattern_type == WILDCARD:
            return True
        if self.pattern_type == LITERAL:
            return resource == self.pattern
        return resource.startswith(self.pattern)


def evaluate(rules: list[AclRule], resource: str) -> str:
    matching = [r for r in rules if r.matches(resource)]
    if not matching:
        return (
            f"DENY {resource}: no rule matches, and an access "
            "system with no matching rule fails closed"
        )
    best_spec = max(SPECIFICITY[r.pattern_type] for r in matching)
    contenders = [
        r
        for r in matching
        if SPECIFICITY[r.pattern_type] == best_spec
    ]
    # deny beats allow at equal specificity
    decision = min(contenders, key=lambda r: r.allow)
    verb = "ALLOW" if decision.allow else "DENY"
    kind = decision.pattern_type
    return (
        f"{verb} {resource}: by the {kind} rule "
        f"'{decision.pattern}', the most specific match"
        + (
            "; a deny broke the tie because security fails closed"
            if not decision.allow
            and any(c.allow for c in contenders)
            else ""
        )
    )
