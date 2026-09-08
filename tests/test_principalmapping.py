from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.principalmapping import MappingRule, PrincipalMapper


def _mapper():
    return PrincipalMapper(
        rules=[
            MappingRule(prefix="CN=alice,", principal="alice"),
            MappingRule(prefix="CN=", principal="generic-cert-user"),
        ]
    )


class TestMap:
    def test_the_first_matching_rule_wins(self):
        m = _mapper()
        assert m.map("CN=alice,OU=eng") == "alice"

    def test_a_later_rule_catches_the_rest(self):
        m = _mapper()
        assert m.map("CN=bob,OU=eng") == "generic-cert-user"

    def test_an_unmatched_identity_is_refused(self):
        m = PrincipalMapper(rules=[MappingRule("CN=alice,", "alice")])
        with pytest.raises(Invalid) as caught:
            m.map("O=other")
        assert "mapping to a fallback" in str(caught.value)

    def test_no_rules_is_refused(self):
        with pytest.raises(Invalid):
            PrincipalMapper(rules=[])


class TestExplain:
    def test_explain_names_the_matching_rule(self):
        note = _mapper().explain("CN=alice,OU=eng")
        assert "mapped to 'alice' by rule 0" in note

    def test_explain_reports_an_unmapped_identity(self):
        m = PrincipalMapper(rules=[MappingRule("CN=alice,", "alice")])
        assert "access refused" in m.explain("O=other")

    def test_order_shadowing_is_visible(self):
        # a broad rule first shadows a specific one after it
        m = PrincipalMapper(
            rules=[
                MappingRule(prefix="CN=", principal="broad"),
                MappingRule(prefix="CN=alice,", principal="alice"),
            ]
        )
        assert m.map("CN=alice,OU=eng") == "broad"
