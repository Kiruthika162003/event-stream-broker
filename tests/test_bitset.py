from __future__ import annotations

import pytest

from relay.bitset import Bitset
from relay.errors import Invalid


class TestSetTest:
    def test_set_and_test_are_exact(self):
        b = Bitset(base=1000, size=100)
        b.set(1050)
        assert b.test(1050)
        assert not b.test(1051)

    def test_clear_unmarks_precisely(self):
        b = Bitset(base=1000, size=100)
        b.set(1050)
        b.clear(1050)
        assert not b.test(1050)

    def test_an_offset_below_the_range_is_refused(self):
        b = Bitset(base=1000, size=100)
        with pytest.raises(Invalid):
            b.set(999)

    def test_an_offset_above_the_range_is_refused(self):
        b = Bitset(base=1000, size=100)
        with pytest.raises(Invalid) as caught:
            b.set(1100)
        assert "outside the range" in str(caught.value)


class TestCount:
    def test_count_is_the_set_bits(self):
        b = Bitset(base=0, size=10)
        b.set(1)
        b.set(3)
        b.set(3)  # idempotent
        assert b.count() == 2


class TestDensity:
    def test_a_sparse_bitset_is_named(self):
        b = Bitset(base=0, size=100)
        b.set(1)
        assert "sparse" in b.density()

    def test_a_full_bitset_suggests_a_denser_structure(self):
        b = Bitset(base=0, size=4)
        for o in range(3):
            b.set(o)
        assert "nearly full" in b.density()


class TestConfig:
    def test_a_zero_size_is_refused(self):
        with pytest.raises(Invalid):
            Bitset(base=0, size=0)
