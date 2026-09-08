from __future__ import annotations

import pytest

from relay.aclpatterns import (
    LITERAL,
    PREFIX,
    WILDCARD,
    AclRule,
    evaluate,
)
from relay.errors import Invalid


class TestSpecificity:
    def test_a_literal_allow_overrides_a_wildcard_deny(self):
        rules = [
            AclRule(WILDCARD, "*", allow=False),
            AclRule(LITERAL, "orders", allow=True),
        ]
        verdict = evaluate(rules, "orders")
        assert verdict.startswith("ALLOW orders")
        assert "most specific match" in verdict

    def test_a_prefix_beats_a_wildcard(self):
        rules = [
            AclRule(WILDCARD, "*", allow=True),
            AclRule(PREFIX, "secret-", allow=False),
        ]
        verdict = evaluate(rules, "secret-keys")
        assert verdict.startswith("DENY secret-keys")

    def test_the_wildcard_applies_when_alone(self):
        rules = [AclRule(WILDCARD, "*", allow=True)]
        assert evaluate(rules, "anything").startswith("ALLOW")


class TestFailClosed:
    def test_no_matching_rule_denies(self):
        rules = [AclRule(LITERAL, "orders", allow=True)]
        verdict = evaluate(rules, "payments")
        assert "no rule matches" in verdict
        assert "fails closed" in verdict

    def test_deny_beats_allow_at_equal_specificity(self):
        rules = [
            AclRule(LITERAL, "orders", allow=True),
            AclRule(LITERAL, "orders", allow=False),
        ]
        verdict = evaluate(rules, "orders")
        assert verdict.startswith("DENY")
        assert "security fails closed" in verdict


class TestRefusals:
    def test_an_unknown_pattern_type_is_refused(self):
        with pytest.raises(Invalid):
            AclRule("regex", ".*", allow=True)
