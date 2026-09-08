from __future__ import annotations

from examples import (
    exactlyonceday,
    failoverday,
    firststream,
    operationsday,
    rebalanceday,
    retentionday,
    securityday,
    streamsday,
    upgradeday,
    wireformatday,
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


class TestRetentionDay:
    def test_the_day_reads_end_to_end(self, capsys):
        assert retentionday.main() == 0
        out = capsys.readouterr().out
        assert "roll by age" in out
        assert "4 records compact to 2 (2.0x)" in out
        assert "held on the clock" in out
        assert "deleted 400 record(s) from 100 to 500" in out


class TestUpgradeDay:
    def test_the_day_reads_end_to_end(self, capsys):
        assert upgradeday.main() == 0
        out = capsys.readouterr().out
        assert "fetch negotiated at v6" in out
        assert "transactions enabled" in out
        assert "2 of 2 partition(s) handed off" in out
        assert "controller b2 at epoch 8, 1 stale change(s) fenced" in out


class TestWireFormatDay:
    def test_the_day_reads_end_to_end(self, capsys):
        assert wireformatday.main() == 0
        out = capsys.readouterr().out
        assert "6 deltas encoded in 8 byte(s)" in out
        assert "decoded back to [0, 1, 2, -1, 300, -300]" in out
        assert "batch verified" in out
        assert "the batch is corrupt and must be refused" in out
        assert "record 2 is offset 1002, next base 1005" in out
        assert "2 offset slot(s) consumed" in out


class TestRebalanceDay:
    def test_the_day_reads_end_to_end(self, capsys):
        assert rebalanceday.main() == 0
        out = capsys.readouterr().out
        assert "leader c1, strategy range" in out
        assert "c2 gets [2, 3]" in out
        assert "stable heartbeat -> acknowledged" in out
        assert "newcomer joined -> rebalance-in-progress" in out
        assert "3 partition(s) paused for nothing (75%)" in out


class TestSecurityDay:
    def test_the_day_reads_end_to_end(self, capsys):
        assert securityday.main() == 0
        out = capsys.readouterr().out
        assert "authentication complete after 2 round(s)" in out
        assert "mapped to 'alice' by rule 0" in out
        assert "authenticated by delegation token" in out
        assert "re-authenticated 'alice'; session now to 300" in out
        assert "at its per-IP cap 2" in out


class TestStreamsDay:
    def test_the_day_reads_end_to_end(self, capsys):
        assert streamsday.main() == 0
        out = capsys.readouterr().out
        assert "extracted 1000, missing fell back to 9999" in out
        assert "watermark at 115" in out
        assert "table now {'cust2': 9}" in out
        assert "early emit [], final emit [(100, 3)]" in out
