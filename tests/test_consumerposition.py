from __future__ import annotations

import pytest

from relay.consumerposition import ConsumerPosition
from relay.errors import Invalid


class TestInvariants:
    def test_a_starting_position_past_the_watermark_is_refused(self):
        with pytest.raises(Invalid):
            ConsumerPosition(high_watermark=100, position=200)

    def test_a_starting_commit_past_the_position_is_refused(self):
        with pytest.raises(Invalid):
            ConsumerPosition(high_watermark=100, position=50, committed=60)


class TestAdvance:
    def test_the_position_advances_up_to_the_watermark(self):
        p = ConsumerPosition(high_watermark=100)
        p.advance_position(80)
        assert p.position == 80

    def test_advancing_past_the_watermark_is_refused(self):
        p = ConsumerPosition(high_watermark=100)
        with pytest.raises(Invalid) as caught:
            p.advance_position(200)
        assert "reading the future" in str(caught.value)


class TestCommit:
    def test_committing_up_to_the_position_is_allowed(self):
        p = ConsumerPosition(high_watermark=100)
        p.advance_position(80)
        p.commit(80)
        assert p.committed == 80

    def test_committing_past_the_position_is_refused(self):
        p = ConsumerPosition(high_watermark=100)
        p.advance_position(50)
        with pytest.raises(Invalid) as caught:
            p.commit(60)
        assert "promises work not done" in str(caught.value)


class TestGaps:
    def test_replay_window_and_lag(self):
        p = ConsumerPosition(high_watermark=100)
        p.advance_position(70)
        p.commit(50)
        assert p.replay_window() == 20
        assert p.lag() == 30

    def test_report_names_all_three(self):
        p = ConsumerPosition(high_watermark=100)
        p.advance_position(70)
        p.commit(50)
        note = p.report()
        assert "position 70, committed 50, watermark 100" in note
