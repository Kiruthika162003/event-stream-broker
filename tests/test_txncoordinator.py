from __future__ import annotations

import pytest

from relay.errors import Fenced, Invalid
from relay.txncoordinator import TransactionCoordinator


def coordinator() -> TransactionCoordinator:
    return TransactionCoordinator()


class TestRegistration:
    def test_the_first_registration_gets_epoch_zero(self):
        assert coordinator().register("payer") == 0

    def test_re_registration_bumps_the_epoch(self):
        chosen = coordinator()
        chosen.register("payer")
        assert chosen.register("payer") == 1


class TestFencing:
    def test_a_zombie_epoch_is_fenced(self):
        chosen = coordinator()
        chosen.register("payer")
        chosen.register("payer")  # epoch now 1
        with pytest.raises(Fenced) as caught:
            chosen.begin("payer", epoch=0)
        assert "resurrected producer cannot commit" in str(
            caught.value
        )
        assert chosen.zombies_fenced == 1

    def test_the_current_epoch_may_act(self):
        chosen = coordinator()
        chosen.register("payer")
        assert "began a transaction" in chosen.begin("payer", 0)


class TestOneOpenTransaction:
    def test_a_second_open_is_refused(self):
        chosen = coordinator()
        chosen.register("payer")
        chosen.begin("payer", 0)
        with pytest.raises(Invalid) as caught:
            chosen.begin("payer", 0)
        assert "blur which records belong" in str(caught.value)

    def test_commit_then_begin_is_fine(self):
        chosen = coordinator()
        chosen.register("payer")
        chosen.begin("payer", 0)
        chosen.complete("payer", 0, commit=True)
        assert "began" in chosen.begin("payer", 0)

    def test_completing_without_an_open_txn_is_refused(self):
        chosen = coordinator()
        chosen.register("payer")
        with pytest.raises(Invalid):
            chosen.complete("payer", 0, commit=True)


class TestTimeout:
    def test_a_timeout_aborts_and_bumps_the_epoch(self):
        chosen = coordinator()
        chosen.register("payer")
        chosen.begin("payer", 0)
        verdict = chosen.timeout_abort("payer")
        assert "epoch bumped to 1" in verdict
        assert "never resurrect" in verdict
        with pytest.raises(Fenced):
            chosen.begin("payer", 0)
