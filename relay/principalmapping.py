"""Principal mapping: the authenticated name is not yet the name ACLs use.

Authentication proves an identity in the form the mechanism speaks:
an SSL client certificate carries a distinguished name like a full
X.500 subject, a Kerberos login carries a principal with a realm,
and these long mechanism-specific strings are not what an operator
wants to write ACLs against. Principal mapping is the translation
step in between: a set of ordered rules, each a pattern and a
replacement, that turns the authenticated name into a short Kafka
principal, so an ACL can name alice rather than the whole
certificate subject. The rules are tried in order and the first
that matches wins, which makes rule order part of the policy the
same way branch order was: a broad rule placed before a specific
one captures identities the specific rule meant to handle, so
specific rules go first. The mapping is where a dangerous default
must be refused: an authenticated identity that matches no rule is
not mapped to a fallback principal, because a fallback would grant
every unmatched identity whatever access that principal has,
collapsing distinct identities into one and quietly widening who
can do what. So an unmatched identity is rejected, forcing the
operator to add a rule that names it rather than have it silently
inherit access. The mapper applies the first matching rule's
replacement, refuses an identity no rule matches, and refuses a
rule set with no rules at all, which would map nothing. It reports
which rule mapped an identity, because an identity mapped to a
surprising principal is usually one caught by an earlier broad rule
than the operator intended, the ordering shadow a per-identity
report reveals.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class MappingRule:
    prefix: str
    principal: str

    def matches(self, identity: str) -> bool:
        return identity.startswith(self.prefix)


@dataclass
class PrincipalMapper:
    rules: list[MappingRule] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.rules:
            raise Invalid("a mapper with no rules maps nothing")

    def _first_match(self, identity: str) -> MappingRule | None:
        for rule in self.rules:
            if rule.matches(identity):
                return rule
        return None

    def map(self, identity: str) -> str:
        rule = self._first_match(identity)
        if rule is None:
            raise Invalid(
                f"identity '{identity}' matches no rule; refusing rather "
                "than mapping to a fallback that would grant it whatever "
                "access the fallback has"
            )
        return rule.principal

    def explain(self, identity: str) -> str:
        rule = self._first_match(identity)
        if rule is None:
            return f"'{identity}' unmapped; no rule matches, access refused"
        idx = self.rules.index(rule)
        return (
            f"'{identity}' mapped to '{rule.principal}' by rule {idx} "
            f"(prefix '{rule.prefix}'); a surprising result is an earlier "
            "broad rule shadowing a later specific one"
        )
