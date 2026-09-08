from __future__ import annotations

import pytest

from relay.dedupstore import DedupStore
from relay.errors import Invalid


class TestProcess:
    def test_a_first_sighting_is_processed(self):
        d = DedupStore(window=100)
        assert "for the first time" in d.process("k1", now=0)

    def test_a_repeat_within_the_window_is_dropped(self):
        d = DedupStore(window=100)
        d.process("k1", now=0)
        assert "duplicate 'k1' dropped" in d.process("k1", now=50)

    def test_a_repeat_after_the_window_is_processed_again(self):
        d = DedupStore(window=100)
        d.process("k1", now=0)
        # key expired by now=200; treated as first sighting again
        assert "for the first time" in d.process("k1", now=200)


class TestConfig:
    def test_a_non_positive_window_is_refused(self):
        with pytest.raises(Invalid):
            DedupStore(window=0)


class TestReport:
    def test_report_counts_keys_and_missed_duplicates(self):
        d = DedupStore(window=100)
        d.process("k1", now=0)
        d.process("k2", now=0)
        d.note_missed_duplicate()
        note = d.report(now=10)
        assert "2 key(s) remembered" in note
        assert "1 duplicate(s) arrived" in note

    def test_expired_keys_drop_out_of_the_count(self):
        d = DedupStore(window=100)
        d.process("k1", now=0)
        assert "0 key(s) remembered" in d.report(now=500)
