from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.segmentdelete import SegmentDeletion


class TestRename:
    def test_rename_records_the_open_readers(self):
        d = SegmentDeletion(delay_ticks=60)
        note = d.rename(now=100, readers_open=2)
        assert "no new read can open it" in note
        assert d.open_readers == 2

    def test_a_double_rename_is_refused(self):
        d = SegmentDeletion(delay_ticks=60)
        d.rename(now=100, readers_open=0)
        with pytest.raises(Invalid) as caught:
            d.rename(now=110, readers_open=0)
        assert "already renamed" in str(caught.value)


class TestUnlink:
    def test_unlink_after_the_delay_with_no_readers(self):
        d = SegmentDeletion(delay_ticks=60)
        d.rename(now=100, readers_open=0)
        assert "disk reclaimed" in d.try_unlink(now=200)

    def test_unlink_is_refused_while_a_pre_rename_read_is_active(self):
        d = SegmentDeletion(delay_ticks=60)
        d.rename(now=100, readers_open=1)
        with pytest.raises(Invalid) as caught:
            d.try_unlink(now=120)
        assert "live reader" in str(caught.value)

    def test_unlink_allowed_once_readers_finish(self):
        d = SegmentDeletion(delay_ticks=60)
        d.rename(now=100, readers_open=1)
        d.reader_finished()
        assert "disk reclaimed" in d.try_unlink(now=120)

    def test_unlink_allowed_once_the_delay_elapses_regardless(self):
        d = SegmentDeletion(delay_ticks=60)
        d.rename(now=100, readers_open=1)
        # delay elapsed; the bound outlasts any reasonable read
        assert "disk reclaimed" in d.try_unlink(now=200)

    def test_unlink_without_a_rename_is_refused(self):
        d = SegmentDeletion(delay_ticks=60)
        with pytest.raises(Invalid):
            d.try_unlink(now=100)


class TestStatus:
    def test_status_reports_the_due_time_and_holders(self):
        d = SegmentDeletion(delay_ticks=60)
        d.rename(now=100, readers_open=2)
        note = d.status(now=130)
        assert "unlink due at 160" in note
        assert "2 pre-rename read(s)" in note
