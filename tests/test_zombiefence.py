from __future__ import annotations

import pytest

from relay.errors import Fenced, Invalid
from relay.zombiefence import TransactionalIdFencer


def fencer() -> TransactionalIdFencer:
    return TransactionalIdFencer()


class TestEpochs:
    def test_each_initialize_bumps_the_epoch(self):
        f = fencer()
        assert f.initialize("payer") == 1
        assert f.initialize("payer") == 2

    def test_an_uninitialized_id_cannot_write(self):
        with pytest.raises(Invalid):
            fencer().guard_write("ghost", 1)


class TestFencing:
    def test_the_current_epoch_writes_freely(self):
        f = fencer()
        epoch = f.initialize("payer")
        assert "write accepted" in f.guard_write("payer", epoch)

    def test_the_zombie_write_is_fenced(self):
        f = fencer()
        f.initialize("payer")  # epoch 1
        f.initialize("payer")  # epoch 2, replacement
        with pytest.raises(Fenced) as caught:
            f.guard_write("payer", 1)
        assert "the zombie that woke from a pause" in str(
            caught.value
        )
        assert f.fenced_writes == 1

    def test_the_zombie_commit_is_fenced_too(self):
        f = fencer()
        f.initialize("payer")
        f.initialize("payer")
        with pytest.raises(Fenced):
            f.guard_commit("payer", 1)
        assert f.fenced_commits == 1


class TestTheReport:
    def test_the_report_explains_the_commit_guard(self):
        f = fencer()
        f.initialize("payer")
        f.initialize("payer")
        with pytest.raises(Fenced):
            f.guard_write("payer", 1)
        with pytest.raises(Fenced):
            f.guard_commit("payer", 1)
        report = f.report()
        assert "1 write(s) and 1 commit(s) fenced" in report
        assert "make durable the records the fence rejects" in (
            report
        )
