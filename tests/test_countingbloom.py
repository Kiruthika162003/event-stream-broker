from __future__ import annotations

import pytest

from relay.countingbloom import CountingBloom
from relay.errors import Invalid


class TestAddRemove:
    def test_an_added_key_is_present(self):
        b = CountingBloom(size=1000, hash_count=4)
        b.add("x")
        assert b.might_contain("x")

    def test_remove_takes_a_key_out(self):
        b = CountingBloom(size=1000, hash_count=4)
        b.add("x")
        b.remove("x")
        assert not b.might_contain("x")

    def test_removing_one_of_two_keys_keeps_the_other(self):
        # the counting property: two keys, remove one, the other stays
        b = CountingBloom(size=5000, hash_count=5)
        b.add("a")
        b.add("b")
        b.remove("a")
        assert b.might_contain("b")

    def test_removing_an_absent_key_is_refused(self):
        b = CountingBloom(size=1000, hash_count=4)
        with pytest.raises(Invalid) as caught:
            b.remove("never")
        assert "corrupting them" in str(caught.value)


class TestNoFalseNegatives:
    def test_added_keys_all_present(self):
        b = CountingBloom(size=5000, hash_count=5)
        keys = [f"k{i}" for i in range(200)]
        for k in keys:
            b.add(k)
        assert all(b.might_contain(k) for k in keys)


class TestSaturation:
    def test_saturation_is_reported(self):
        b = CountingBloom(size=4, hash_count=2, max_count=3)
        for _ in range(20):
            b.add("hot")
        assert "saturated" in b.saturation()


class TestConfig:
    def test_a_zero_size_is_refused(self):
        with pytest.raises(Invalid):
            CountingBloom(size=0, hash_count=1)
