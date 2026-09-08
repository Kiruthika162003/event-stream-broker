from __future__ import annotations

import pytest

from relay.describelogdirs import LogDir, LogDirsReport
from relay.errors import Invalid


class TestLogDir:
    def test_total_sums_the_partitions(self):
        d = LogDir(path="/d1", partition_sizes={"t-0": 100, "t-1": 50})
        assert d.total() == 150

    def test_an_offline_dir_refuses_a_total(self):
        d = LogDir(path="/d1", offline=True)
        with pytest.raises(Invalid) as caught:
            d.total()
        assert "unknown, not zero" in str(caught.value)

    def test_largest_partition_is_the_heaviest(self):
        d = LogDir(path="/d1", partition_sizes={"t-0": 100, "t-1": 300})
        assert d.largest_partition() == ("t-1", 300)


class TestImbalance:
    def test_it_names_the_fullest_dir_and_its_heavy_partition(self):
        report = LogDirsReport(
            dirs=[
                LogDir(path="/d1", partition_sizes={"a-0": 900, "a-1": 100}),
                LogDir(path="/d2", partition_sizes={"b-0": 200}),
            ]
        )
        note = report.imbalance()
        assert "/d1 is 800 byte(s) fuller than /d2" in note
        assert "largest partition a-0 holds 900" in note

    def test_a_single_dir_has_nothing_to_balance(self):
        report = LogDirsReport(dirs=[LogDir(path="/d1")])
        assert "nothing to balance" in report.imbalance()


class TestOffline:
    def test_offline_dirs_are_listed(self):
        report = LogDirsReport(
            dirs=[
                LogDir(path="/d1"),
                LogDir(path="/d2", offline=True),
            ]
        )
        assert report.offline_dirs() == ["/d2"]
