from __future__ import annotations

import pytest

from relay.aggregatemerge import (
    MeanPartial,
    is_associative,
    merge_associative,
    merge_means,
)
from relay.errors import Invalid


class TestAssociativeMerge:
    def test_sum_partials_merge_to_the_global_sum(self):
        assert merge_associative([10, 20, 30], lambda a, b: a + b) == 60

    def test_max_partials_merge_to_the_global_max(self):
        assert merge_associative([3, 9, 5], max) == 9

    def test_no_partials_is_refused(self):
        with pytest.raises(Invalid):
            merge_associative([], lambda a, b: a + b)


class TestAssociativityCheck:
    def test_sum_is_associative(self):
        assert is_associative(lambda a, b: a + b, [1, 2, 3])

    def test_subtraction_is_not_associative(self):
        assert not is_associative(lambda a, b: a - b, [1, 2, 3])


class TestMeanTrap:
    def test_merged_mean_uses_sum_and_count(self):
        # partition A: total 100 over 10 -> mean 10
        # partition B: total 5 over 1 -> mean 5
        # true mean = 105/11 = 9.55; averaging means = 7.5 (wrong)
        partials = [MeanPartial(100, 10), MeanPartial(5, 1)]
        note = merge_means(partials)
        assert "correct mean 9.55" in note
        assert "averaging the averages would give 7.50" in note

    def test_equal_counts_make_the_two_agree(self):
        partials = [MeanPartial(20, 2), MeanPartial(40, 2)]
        note = merge_means(partials)
        assert "correct mean 15.00" in note

    def test_a_zero_count_mean_is_refused(self):
        with pytest.raises(Invalid):
            MeanPartial(0, 0).mean()
