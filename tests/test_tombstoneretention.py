from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.tombstoneretention import TombstoneRetention


class TestDeadline:
    def test_the_deadline_is_eligible_plus_retention(self):
        t = TombstoneRetention(retention_ms=1000)
        assert t.removal_deadline(eligible_at_ms=5000) == 6000

    def test_a_tombstone_in_grace_may_not_be_removed(self):
        t = TombstoneRetention(retention_ms=1000)
        assert not t.may_remove(eligible_at_ms=5000, now_ms=5500)

    def test_a_tombstone_past_grace_may_be_removed(self):
        t = TombstoneRetention(retention_ms=1000)
        assert t.may_remove(eligible_at_ms=5000, now_ms=6001)

    def test_at_the_exact_deadline_it_may_be_removed(self):
        t = TombstoneRetention(retention_ms=1000)
        assert t.may_remove(eligible_at_ms=5000, now_ms=6000)


class TestCheck:
    def test_removing_early_is_refused(self):
        t = TombstoneRetention(retention_ms=1000)
        with pytest.raises(Invalid) as caught:
            t.check_removal(eligible_at_ms=5000, now_ms=5500)
        assert "never see" in str(caught.value)

    def test_removing_after_grace_is_allowed(self):
        t = TombstoneRetention(retention_ms=1000)
        assert "may be removed" in t.check_removal(eligible_at_ms=5000, now_ms=7000)


class TestConfig:
    def test_a_negative_retention_is_refused(self):
        with pytest.raises(Invalid):
            TombstoneRetention(retention_ms=-1)

    def test_a_zero_retention_removes_immediately(self):
        t = TombstoneRetention(retention_ms=0)
        assert t.may_remove(eligible_at_ms=5000, now_ms=5000)


class TestNote:
    def test_the_note_says_in_grace_before_the_deadline(self):
        t = TombstoneRetention(retention_ms=1000)
        assert "in grace" in t.note(eligible_at_ms=5000, now_ms=5500)

    def test_the_note_says_past_grace_after_the_deadline(self):
        t = TombstoneRetention(retention_ms=1000)
        assert "past grace" in t.note(eligible_at_ms=5000, now_ms=7000)
