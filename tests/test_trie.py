from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.trie import PrefixTrie


def _trie():
    t = PrefixTrie()
    for p in ("orders-", "orders-eu-", "metrics-"):
        t.insert(p)
    return t


class TestMatch:
    def test_a_name_matches_a_registered_prefix(self):
        t = _trie()
        assert t.matches("orders-123")
        assert t.matches("metrics-cpu")

    def test_a_name_with_no_registered_prefix_does_not_match(self):
        t = _trie()
        assert not t.matches("logs-app")

    def test_the_longest_matching_prefix_wins(self):
        t = _trie()
        assert t.longest_prefix_of("orders-eu-42") == "orders-eu-"
        assert t.longest_prefix_of("orders-us-42") == "orders-"

    def test_no_match_returns_none(self):
        t = _trie()
        assert t.longest_prefix_of("other") is None


class TestConfig:
    def test_an_empty_prefix_is_refused(self):
        with pytest.raises(Invalid):
            PrefixTrie().insert("")


class TestReport:
    def test_report_counts_prefixes_and_nodes(self):
        t = _trie()
        assert "3 prefix(es)" in t.report()

    def test_shared_heads_use_fewer_nodes(self):
        t = _trie()
        # "orders-" (7) + "orders-eu-" shares the first 7 -> not 17 nodes
        note = t.report()
        assert "node(s)" in note
