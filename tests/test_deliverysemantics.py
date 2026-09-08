from __future__ import annotations

from relay.deliverysemantics import (
    AT_LEAST_ONCE,
    AT_MOST_ONCE,
    EXACTLY_ONCE,
    Chain,
)


def _chain(**over):
    base = {
        "acks_all": True,
        "idempotent": True,
        "transactional": True,
        "consumer_commits_after_process": True,
        "consumer_commits_in_txn": True,
    }
    base.update(over)
    return Chain(**base)


class TestGuarantee:
    def test_the_full_chain_is_exactly_once(self):
        assert _chain().guarantee() == EXACTLY_ONCE

    def test_acks_none_caps_at_at_most_once(self):
        assert _chain(acks_all=False).guarantee() == AT_MOST_ONCE

    def test_commit_before_process_is_at_most_once(self):
        assert (
            _chain(consumer_commits_after_process=False).guarantee()
            == AT_MOST_ONCE
        )

    def test_missing_transaction_degrades_to_at_least_once(self):
        assert _chain(transactional=False).guarantee() == AT_LEAST_ONCE

    def test_commit_outside_txn_degrades_to_at_least_once(self):
        assert (
            _chain(consumer_commits_in_txn=False).guarantee() == AT_LEAST_ONCE
        )


class TestWeakestLink:
    def test_it_names_the_full_chain_when_exactly_once(self):
        assert "every link" in _chain().weakest_link()

    def test_it_names_the_producer_acks(self):
        note = _chain(acks_all=False).weakest_link()
        assert "acks<all" in note

    def test_it_names_what_is_missing_for_exactly_once(self):
        note = _chain(idempotent=False, transactional=False).weakest_link()
        assert "idempotent producer" in note
        assert "transactional producer" in note
