from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.startup import BrokerStartup, LogDir


def healthy(partition: int) -> LogDir:
    return LogDir(
        partition=partition,
        segment_bases=(0, 100),
        segment_ends=(100, 200),
        recorded_end=200,
        actual_end=200,
    )


def gapped() -> LogDir:
    return LogDir(
        partition=1,
        segment_bases=(0, 150),
        segment_ends=(100, 250),
        recorded_end=250,
        actual_end=250,
    )


def torn() -> LogDir:
    return LogDir(
        partition=2,
        segment_bases=(0, 100),
        segment_ends=(100, 200),
        recorded_end=200,
        actual_end=180,
    )


class TestLoading:
    def test_a_clean_directory_comes_online(self):
        startup = BrokerStartup()
        assert "online" in startup.load(healthy(0))
        assert startup.online == [0]

    def test_a_gapped_directory_is_quarantined(self):
        startup = BrokerStartup()
        verdict = startup.load(gapped())
        assert "offline" in verdict
        assert "torn data is never served as whole" in verdict
        assert 1 in startup.offline

    def test_a_torn_directory_needs_truncation(self):
        startup = BrokerStartup()
        verdict = startup.load(torn())
        assert "interrupted write" in verdict
        assert "truncate to the last intact record" in verdict


class TestAllOrParts:
    def test_one_bad_directory_does_not_stop_the_rest(self):
        startup = BrokerStartup()
        report = startup.load_all([healthy(0), gapped(), healthy(3)])
        assert "2 partition(s) online, 1 quarantined" in report
        assert "take the healthy partitions down with it" in report

    def test_no_directories_is_refused(self):
        with pytest.raises(Invalid):
            BrokerStartup().load_all([])
