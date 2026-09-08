from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.fetchsession import FetchSession


def established() -> FetchSession:
    session = FetchSession(session_id=7)
    session.full_fetch(dict.fromkeys(range(1000), 0))
    return session


class TestSession:
    def test_the_first_fetch_establishes_the_session(self):
        session = FetchSession(session_id=7)
        verdict = session.full_fetch({0: 0, 1: 0})
        assert "established at epoch 1 with 2 partition(s)" in (
            verdict
        )

    def test_an_incremental_before_full_is_refused(self):
        with pytest.raises(Invalid) as caught:
            FetchSession(session_id=1).incremental_fetch(1, {})
        assert "the first fetch must be full" in str(caught.value)


class TestIncremental:
    def test_only_changed_partitions_are_named(self):
        session = established()
        touched, note = session.incremental_fetch(
            1, {42: 100, 907: 5}
        )
        assert touched == [42, 907]
        assert "2 of 1000 partition(s) named" in note
        assert "the rest the broker remembers" in note

    def test_the_epoch_advances_each_round(self):
        session = established()
        session.incremental_fetch(1, {0: 1})
        assert session.epoch == 2

    def test_an_epoch_mismatch_forces_a_full_fetch(self):
        session = established()
        with pytest.raises(Invalid) as caught:
            session.incremental_fetch(9, {0: 1})
        assert "silently skips partitions" in str(caught.value)


class TestTheRatio:
    def test_the_protocol_ratio_names_the_elision(self):
        session = established()
        report = session.protocol_ratio(
            subscribed=1000, entries_sent=2
        )
        assert "2 entrie(s) for 1000 partition(s), 998 elided" in (
            report
        )
        assert "entire reason the session exists" in report

    def test_no_subscription_is_refused(self):
        with pytest.raises(Invalid):
            established().protocol_ratio(0, 0)
