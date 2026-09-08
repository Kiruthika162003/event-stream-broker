from __future__ import annotations

import pytest

from relay.connreaper import Connection, ConnectionReaper
from relay.errors import Invalid


def reaper() -> ConnectionReaper:
    built = ConnectionReaper(idle_timeout=30)
    built.register(Connection("idle", last_activity=0))
    built.register(
        Connection("polling", last_activity=0, long_polling=True)
    )
    built.register(
        Connection("txn", last_activity=0, in_transaction=True)
    )
    built.register(Connection("active", last_activity=0))
    return built


class TestReaping:
    def test_an_idle_connection_is_reaped(self):
        built = reaper()
        built.touch("active", now=25)
        reaped = built.reap(now=40)
        assert "idle" in reaped
        assert built.open_slots_freed() >= 1

    def test_a_recently_active_connection_survives(self):
        built = reaper()
        built.touch("active", now=25)
        assert "active" not in built.reap(now=40)

    def test_a_bad_timeout_is_refused(self):
        with pytest.raises(Invalid):
            ConnectionReaper(idle_timeout=0)

    def test_touching_a_closed_connection_is_refused(self):
        built = reaper()
        built.reap(now=100)
        with pytest.raises(Invalid):
            built.touch("idle", now=101)


class TestProtection:
    def test_a_long_polling_connection_is_protected(self):
        built = reaper()
        reaped = built.reap(now=100)
        assert "polling" not in reaped
        assert built.protected >= 1

    def test_a_transactional_connection_is_protected(self):
        built = reaper()
        reaped = built.reap(now=100)
        assert "txn" not in reaped


class TestTheReport:
    def test_the_report_separates_reaped_from_protected(self):
        built = reaper()
        built.reap(now=100)
        report = built.report()
        assert "idle connection(s) reaped" in report
        assert "before it causes a reconnect storm" in report
