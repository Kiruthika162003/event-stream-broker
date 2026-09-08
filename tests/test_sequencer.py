from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.sequencer import Sequencer


class TestIssue:
    def test_numbers_strictly_increase(self):
        s = Sequencer()
        assert s.issue() == 0
        assert s.issue() == 1
        assert s.issue() == 2

    def test_a_batch_reserves_a_range(self):
        s = Sequencer()
        s.issue()  # 0
        start, end = s.issue_batch(5)
        assert (start, end) == (1, 5)
        assert s.issue() == 6

    def test_a_zero_batch_is_refused(self):
        with pytest.raises(Invalid):
            Sequencer().issue_batch(0)


class TestFailover:
    def test_resume_above_the_highest_issued(self):
        s = Sequencer()
        for _ in range(10):
            s.issue()  # highest issued 9
        assert "resumes at 100" in s.failover_resume(floor=100)
        assert s.issue() == 100

    def test_resume_below_the_highest_is_refused(self):
        s = Sequencer()
        for _ in range(10):
            s.issue()  # highest 9
        with pytest.raises(Invalid) as caught:
            s.failover_resume(floor=5)
        assert "break the total order" in str(caught.value)


class TestThroughput:
    def test_it_names_the_bottleneck(self):
        note = Sequencer().throughput_note(per_second=100000)
        assert "bottleneck" in note
