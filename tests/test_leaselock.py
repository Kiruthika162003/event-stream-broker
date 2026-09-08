from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.leaselock import LeaseLock


class TestAcquire:
    def test_acquire_a_free_lock_issues_a_token(self):
        lock = LeaseLock(lease_duration=100)
        assert lock.acquire("a", now=0) == 1

    def test_a_held_lock_is_not_granted_to_another(self):
        lock = LeaseLock(lease_duration=100)
        lock.acquire("a", now=0)
        with pytest.raises(Invalid) as caught:
            lock.acquire("b", now=50)
        assert "held by 'a'" in str(caught.value)

    def test_an_expired_lock_can_be_taken(self):
        lock = LeaseLock(lease_duration=100)
        lock.acquire("a", now=0)
        token = lock.acquire("b", now=150)  # a's lease expired
        assert token == 2
        assert lock.holder == "b"


class TestRenew:
    def test_the_holder_renews(self):
        lock = LeaseLock(lease_duration=100)
        lock.acquire("a", now=0)
        assert "renewed by 'a' until 190" in lock.renew("a", now=90)

    def test_a_non_holder_cannot_renew(self):
        lock = LeaseLock(lease_duration=100)
        lock.acquire("a", now=0)
        with pytest.raises(Invalid):
            lock.renew("b", now=50)


class TestFencing:
    def test_an_old_token_is_fenced(self):
        lock = LeaseLock(lease_duration=100)
        lock.acquire("a", now=0)      # token 1
        lock.acquire("b", now=150)    # token 2
        with pytest.raises(Invalid) as caught:
            lock.guard(token=1)  # a resumed with its stale token
        assert "fenced from acting" in str(caught.value)

    def test_the_current_token_is_allowed(self):
        lock = LeaseLock(lease_duration=100)
        t = lock.acquire("a", now=0)
        assert "allowed" in lock.guard(t)


class TestConfig:
    def test_a_zero_lease_is_refused(self):
        with pytest.raises(Invalid):
            LeaseLock(lease_duration=0)
