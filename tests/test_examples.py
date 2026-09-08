from __future__ import annotations

from examples import (
    exactlyonceday,
    failoverday,
    firststream,
    operationsday,
)


class TestFirstStream:
    def test_the_stream_reads_end_to_end(self, capsys):
        assert firststream.main() == 0
        out = capsys.readouterr().out
        assert "4 records per partition -> {0: 4, 1: 4, 2: 4}" in out
        assert "watermarks at {0: 3, 1: 3, 2: 3}" in out
        assert "1 record(s) exist but are not yet promises" in out
        assert "process then commit; a crash replays" in out
        assert "read 9 committed records, lag now 0" in out


class TestFailoverDay:
    def test_the_day_reads_end_to_end(self, capsys):
        assert failoverday.main() == 0
        out = capsys.readouterr().out
        assert "committed through 979" in out
        assert "pace-setter b2 at 980 (20 behind the leader)" in out
        assert "b3 elected at epoch 8" in out
        assert "discarded 40 unpromised record(s)" in out


class TestOperationsDay:
    def test_the_day_reads_end_to_end(self, capsys):
        assert operationsday.main() == 0
        out = capsys.readouterr().out
        assert "400 bytes over, delayed 4 tick(s)" in out
        assert "draining, empty in about 60 tick(s)" in out
        assert "revoked 4 partition(s)" in out
        assert "no partition was ever owned by two" in out
        assert "900 reclaimed for 1000 processed (90%)" in out


class TestExactlyOnceDay:
    def test_the_day_reads_end_to_end(self, capsys):
        assert exactlyonceday.main() == 0
        out = capsys.readouterr().out
        assert "4 accepted, 3 duplicates absorbed" in out
        assert "payer committed at epoch 0" in out
        assert "replays only unshipped input" in out
        assert "read-committed stops at 940" in out
