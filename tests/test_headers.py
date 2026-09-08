from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.headers import Headers


class TestOrderingAndRepeats:
    def test_headers_keep_order_and_repeats(self):
        headers = Headers()
        headers.add("trace", b"span-1")
        headers.add("trace", b"span-2")
        headers.add("source", b"billing")
        assert headers.get_all("trace") == [b"span-1", b"span-2"]
        assert headers.ordered_names() == [
            "trace",
            "trace",
            "source",
        ]

    def test_a_nameless_header_is_refused(self):
        with pytest.raises(Invalid):
            Headers().add(" ", b"x")


class TestReservedNamespace:
    def test_a_producer_cannot_set_reserved_headers(self):
        with pytest.raises(Invalid) as caught:
            Headers().add("__relay.sequence", b"5")
        assert "impersonate a transaction" in str(caught.value)

    def test_the_broker_may_set_reserved_headers(self):
        headers = Headers()
        headers.add_reserved("__relay.txn", b"open")
        assert headers.get_all("__relay.txn") == [b"open"]

    def test_broker_headers_must_use_the_prefix(self):
        with pytest.raises(Invalid):
            Headers().add_reserved("plain", b"x")


class TestSizeLimit:
    def test_headers_are_bounded(self):
        headers = Headers()
        with pytest.raises(Invalid) as caught:
            headers.add("big", b"x" * 5000)
        assert "smuggled past the value limit" in str(caught.value)

    def test_total_bytes_counts_names_and_values(self):
        headers = Headers()
        headers.add("ab", b"cde")
        assert headers.total_bytes() == 5
