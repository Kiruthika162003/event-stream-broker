from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.interceptors import (
    FILTER,
    OBSERVE,
    TRANSFORM,
    Interceptor,
    InterceptorChain,
)


class TestTransform:
    def test_a_transform_changes_the_record(self):
        chain = InterceptorChain()
        chain.add(
            Interceptor("upper", TRANSFORM, lambda r: r.upper())
        )
        assert chain.run(b"hi") == b"HI"

    def test_a_transform_that_drops_is_lying(self):
        chain = InterceptorChain()
        chain.add(
            Interceptor("bad", TRANSFORM, lambda _r: None)
        )
        with pytest.raises(Invalid) as caught:
            chain.run(b"x")
        assert "lies about its kind" in str(caught.value)


class TestObserve:
    def test_an_observe_may_read_and_pass_through(self):
        seen = []
        chain = InterceptorChain()
        chain.add(
            Interceptor(
                "metric", OBSERVE,
                lambda r: seen.append(r) or None,
            )
        )
        assert chain.run(b"x") == b"x"
        assert seen == [b"x"]

    def test_an_observe_that_writes_is_refused(self):
        chain = InterceptorChain()
        chain.add(
            Interceptor("sneaky", OBSERVE, lambda r: r + b"!")
        )
        with pytest.raises(Invalid) as caught:
            chain.run(b"x")
        assert "observe reads, it does not write" in str(
            caught.value
        )


class TestFilter:
    def test_a_filter_may_drop_and_the_drop_is_counted(self):
        chain = InterceptorChain()
        chain.add(
            Interceptor(
                "even-length", FILTER,
                lambda r: r if len(r) % 2 == 0 else None,
            )
        )
        assert chain.run(b"even") == b"even"
        assert chain.run(b"odd") is None
        assert chain.dropped == 1
        assert "1 record(s) filtered out" in chain.drop_report()


class TestErrors:
    def test_a_thrown_exception_is_never_swallowed(self):
        def boom(_r):
            raise ValueError("redaction bug")

        chain = InterceptorChain()
        chain.add(Interceptor("redact", TRANSFORM, boom))
        with pytest.raises(Invalid) as caught:
            chain.run(b"x")
        assert "ships PII for a month" in str(caught.value)

    def test_an_unknown_kind_is_refused(self):
        with pytest.raises(Invalid):
            Interceptor("x", "mutate", lambda r: r)
