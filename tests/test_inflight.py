from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.inflight import (
    ProducerPipeline,
    check_ordering,
    ordering_safe,
    throughput_class,
)


class TestSafety:
    def test_one_in_flight_is_safe(self):
        pipe = ProducerPipeline(max_in_flight=1, idempotent=False)
        assert ordering_safe(pipe)
        assert "no second batch can leapfrog" in check_ordering(pipe)

    def test_many_in_flight_with_idempotence_is_safe(self):
        pipe = ProducerPipeline(max_in_flight=5, idempotent=True)
        assert ordering_safe(pipe)
        assert "reject an out-of-order retry" in check_ordering(pipe)

    def test_the_unsafe_middle_is_refused_with_both_fixes(self):
        pipe = ProducerPipeline(max_in_flight=5, idempotent=False)
        assert not ordering_safe(pipe)
        with pytest.raises(Invalid) as caught:
            check_ordering(pipe)
        message = str(caught.value)
        assert "reorders on the first retry" in message
        assert "cap in-flight to 1 or enable idempotence" in message

    def test_a_zero_pipeline_is_refused(self):
        with pytest.raises(Invalid):
            ProducerPipeline(max_in_flight=0, idempotent=True)


class TestThroughputClass:
    def test_one_in_flight_is_throttled_but_safe(self):
        pipe = ProducerPipeline(max_in_flight=1, idempotent=False)
        assert "safe but throttled" in throughput_class(pipe)

    def test_idempotent_pipelining_is_fast_and_safe(self):
        pipe = ProducerPipeline(max_in_flight=5, idempotent=True)
        assert "safe and pipelined" in throughput_class(pipe)

    def test_an_unsafe_pipeline_has_no_rating(self):
        pipe = ProducerPipeline(max_in_flight=5, idempotent=False)
        with pytest.raises(Invalid):
            throughput_class(pipe)
