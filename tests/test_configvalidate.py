from __future__ import annotations

import pytest

from relay.configvalidate import TopicConfig, validate, warnings
from relay.errors import Invalid


def good() -> TopicConfig:
    return TopicConfig(
        replication_factor=3,
        min_insync_replicas=2,
        retention_ticks=1000,
        segment_roll_ticks=100,
        compacted=False,
        size_retained=False,
    )


class TestCrossFieldErrors:
    def test_a_valid_config_passes(self):
        assert validate(good()) == []

    def test_min_insync_above_factor_is_refused(self):
        config = TopicConfig(
            replication_factor=2,
            min_insync_replicas=3,
            retention_ticks=1000,
            segment_roll_ticks=100,
            compacted=False,
            size_retained=False,
        )
        with pytest.raises(Invalid) as caught:
            validate(config)
        assert "acks-all writes block forever" in str(caught.value)

    def test_retention_not_longer_than_roll_is_refused(self):
        config = TopicConfig(
            replication_factor=3,
            min_insync_replicas=2,
            retention_ticks=100,
            segment_roll_ticks=100,
            compacted=False,
            size_retained=False,
        )
        with pytest.raises(Invalid) as caught:
            validate(config)
        assert "deletes nothing" in str(caught.value)


class TestWarnings:
    def test_compacted_and_size_retained_warns(self):
        config = TopicConfig(
            replication_factor=3,
            min_insync_replicas=2,
            retention_ticks=1000,
            segment_roll_ticks=100,
            compacted=True,
            size_retained=True,
        )
        notes = warnings(config)
        assert any("which deletes what" in n for n in notes)

    def test_min_insync_equal_factor_warns_about_availability(self):
        config = TopicConfig(
            replication_factor=3,
            min_insync_replicas=3,
            retention_ticks=1000,
            segment_roll_ticks=100,
            compacted=False,
            size_retained=False,
        )
        notes = warnings(config)
        assert any("minimally available" in n for n in notes)

    def test_a_clean_config_warns_nothing(self):
        assert warnings(good()) == []
