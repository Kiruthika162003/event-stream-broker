from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.sinkconnector import SinkConnector


class TestCommit:
    def test_it_commits_the_confirmed_prefix(self):
        s = SinkConnector()
        s.consume(1)
        s.consume(2)
        s.consume(3)
        s.confirm_write(1)
        s.confirm_write(2)
        assert s.commit() == 2

    def test_it_does_not_commit_past_an_unconfirmed_write(self):
        s = SinkConnector()
        s.consume(1)
        s.consume(2)
        s.confirm_write(2)  # 1 not confirmed
        assert s.commit() == -1


class TestRefusals:
    def test_a_backwards_consume_is_refused(self):
        s = SinkConnector()
        s.consume(5)
        with pytest.raises(Invalid):
            s.consume(3)

    def test_confirming_an_unconsumed_offset_is_refused(self):
        s = SinkConnector()
        with pytest.raises(Invalid) as caught:
            s.confirm_write(9)
        assert "never consumed" in str(caught.value)


class TestReport:
    def test_report_shows_the_uncommitted_gap(self):
        s = SinkConnector()
        s.consume(1)
        s.consume(2)
        s.confirm_write(1)
        s.commit()
        assert "committed offset 1, consumed 2" in s.report()
