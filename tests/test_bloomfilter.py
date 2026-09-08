from __future__ import annotations

import pytest

from relay.bloomfilter import BloomFilter
from relay.errors import Invalid


class TestNoFalseNegatives:
    def test_an_added_key_always_tests_present(self):
        b = BloomFilter(size_bits=1000, hash_count=4)
        for key in ("alpha", "beta", "gamma", "delta"):
            b.add(key)
        for key in ("alpha", "beta", "gamma", "delta"):
            assert b.might_contain(key)

    def test_no_false_negatives_over_many_keys(self):
        b = BloomFilter(size_bits=5000, hash_count=5)
        keys = [f"key-{i}" for i in range(200)]
        for k in keys:
            b.add(k)
        # the defining guarantee: every added key must still be present
        assert all(b.might_contain(k) for k in keys)


class TestDefinitelyAbsent:
    def test_an_empty_filter_reports_absent(self):
        b = BloomFilter(size_bits=1000, hash_count=4)
        assert b.definitely_absent("never-added")

    def test_definitely_absent_is_the_negation(self):
        b = BloomFilter(size_bits=1000, hash_count=4)
        b.add("x")
        assert not b.definitely_absent("x")


class TestRate:
    def test_the_rate_rises_as_the_filter_fills(self):
        b = BloomFilter(size_bits=100, hash_count=3)
        empty_rate = b.estimated_false_positive_rate()
        for i in range(50):
            b.add(f"k{i}")
        assert b.estimated_false_positive_rate() > empty_rate

    def test_report_states_the_rate(self):
        b = BloomFilter(size_bits=1000, hash_count=4)
        b.add("x")
        assert "estimated false-positive rate" in b.report()


class TestConfig:
    def test_a_zero_size_is_refused(self):
        with pytest.raises(Invalid):
            BloomFilter(size_bits=0, hash_count=1)

    def test_zero_hashes_is_refused(self):
        with pytest.raises(Invalid):
            BloomFilter(size_bits=100, hash_count=0)
