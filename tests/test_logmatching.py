from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.logmatching import FollowerLog


class TestAppend:
    def test_a_matching_preceding_entry_appends(self):
        f = FollowerLog(entries={1: 1, 2: 1})
        note = f.append(prev_index=2, prev_term=1, new={3: 2, 4: 2})
        assert "appended after index 2" in note
        assert f.entries == {1: 1, 2: 1, 3: 2, 4: 2}

    def test_a_mismatch_is_rejected(self):
        f = FollowerLog(entries={1: 1, 2: 3})  # term 3 at index 2
        with pytest.raises(Invalid) as caught:
            f.append(prev_index=2, prev_term=1, new={3: 2})
        assert "log mismatch at index 2" in str(caught.value)

    def test_appending_truncates_a_divergent_tail(self):
        f = FollowerLog(entries={1: 1, 2: 1, 3: 9, 4: 9})  # divergent tail
        f.append(prev_index=2, prev_term=1, new={3: 2})
        assert f.entries == {1: 1, 2: 1, 3: 2}

    def test_appending_at_the_start_needs_no_check(self):
        f = FollowerLog()
        f.append(prev_index=0, prev_term=0, new={1: 1})
        assert f.entries == {1: 1}


class TestAgreement:
    def test_the_agreement_point_is_the_last_matching_index(self):
        f = FollowerLog(entries={1: 1, 2: 1, 3: 9})
        leader = {1: 1, 2: 1, 3: 2, 4: 2}
        assert f.agreement_point(leader) == 2

    def test_report_states_the_reconcile_distance(self):
        f = FollowerLog(entries={1: 1, 2: 9})
        leader = {1: 1, 2: 1, 3: 1}
        note = f.report(leader)
        assert "agree through index 1" in note
