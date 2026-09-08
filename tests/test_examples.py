from __future__ import annotations

from examples import failoverday, firststream


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
