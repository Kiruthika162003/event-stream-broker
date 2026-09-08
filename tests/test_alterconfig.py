from __future__ import annotations

import pytest

from relay.alterconfig import classify_change, is_safe_live
from relay.errors import Invalid


class TestInstant:
    def test_retention_is_instant(self):
        verdict = classify_change("retention_ticks")
        assert "instant" in verdict
        assert "only future records" in verdict

    def test_max_message_bytes_is_safe_live(self):
        assert is_safe_live("max_message_bytes")


class TestReshaping:
    def test_compaction_needs_acknowledgement(self):
        with pytest.raises(Invalid) as caught:
            classify_change("compacted")
        assert "transforms existing data" in str(caught.value)
        assert "not a casual tweak" in str(caught.value)

    def test_acknowledged_compaction_is_permitted(self):
        verdict = classify_change("compacted", acknowledged=True)
        assert "reshaping acknowledged" in verdict

    def test_compaction_is_not_safe_live(self):
        assert not is_safe_live("compacted")


class TestForbidden:
    def test_partition_count_change_is_forbidden(self):
        with pytest.raises(Invalid) as caught:
            classify_change("partition_count")
        assert "breaks keying" in str(caught.value)

    def test_an_unknown_setting_is_refused(self):
        with pytest.raises(Invalid):
            classify_change("mystery")
