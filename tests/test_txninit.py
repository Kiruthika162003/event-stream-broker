from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.txninit import EPOCH_CLAIMED, READY, TransactionalInit


def init() -> TransactionalInit:
    return TransactionalInit(txn_id="payer")


class TestOrder:
    def test_the_handshake_is_claim_then_recover_then_begin(self):
        t = init()
        t.claim_epoch(1)
        assert t.state == EPOCH_CLAIMED
        t.recover(dangling_open=False)
        assert t.state == READY
        assert "may begin a transaction" in t.begin_transaction()

    def test_begin_before_init_is_refused(self):
        with pytest.raises(Invalid) as caught:
            init().begin_transaction()
        assert "could produce while a predecessor's" in str(
            caught.value
        )

    def test_recover_before_claim_is_refused(self):
        with pytest.raises(Invalid) as caught:
            init().recover(dangling_open=False)
        assert "claim-then-recover" in str(caught.value)


class TestFencing:
    def test_a_lower_epoch_is_refused(self):
        t = init()
        t.claim_epoch(5)
        with pytest.raises(Invalid) as caught:
            t.claim_epoch(3)
        assert "would not fence the zombie" in str(caught.value)


class TestRecovery:
    def test_a_dangling_transaction_is_aborted(self):
        t = init()
        t.claim_epoch(1)
        verdict = t.recover(dangling_open=True)
        assert "recovered a dangling transaction" in verdict
        assert "tangled two under one id" in verdict
        assert t.recovered_dangling == 1

    def test_a_clean_slate_is_reported(self):
        t = init()
        t.claim_epoch(1)
        assert "clean slate, ready" in t.recover(
            dangling_open=False
        )
