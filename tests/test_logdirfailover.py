from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.logdirfailover import LogDirManager


def _mgr():
    return LogDirManager(
        dir_partitions={
            "/d1": {"t-0", "t-1"},
            "/d2": {"t-2", "t-3"},
            "/d3": {"t-4"},
        }
    )


class TestFail:
    def test_a_disk_failure_takes_only_its_partitions_offline(self):
        m = _mgr()
        note = m.fail_dir("/d1")
        assert "2 partition(s) offline" in note
        assert m.offline_partitions() == {"t-0", "t-1"}
        assert "/d2" in m.surviving_dirs()

    def test_a_double_failure_is_refused(self):
        m = _mgr()
        m.fail_dir("/d1")
        with pytest.raises(Invalid) as caught:
            m.fail_dir("/d1")
        assert "already failed" in str(caught.value)

    def test_an_unknown_dir_is_refused(self):
        with pytest.raises(Invalid):
            _mgr().fail_dir("/nope")


class TestAllFailed:
    def test_the_last_dir_failing_shuts_the_broker_down(self):
        m = _mgr()
        m.fail_dir("/d1")
        m.fail_dir("/d2")
        note = m.fail_dir("/d3")
        assert "shuts down" in note
        assert m.all_failed()


class TestReport:
    def test_report_counts_surviving_failed_and_offline(self):
        m = _mgr()
        m.fail_dir("/d2")
        note = m.report()
        assert "2 surviving dir(s), 1 failed, 2 partition(s) offline" in note
