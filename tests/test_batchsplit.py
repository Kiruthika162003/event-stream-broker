from __future__ import annotations

import pytest

from relay.batchsplit import split_batch, split_report
from relay.errors import Invalid


class TestSplit:
    def test_a_fitting_batch_is_not_split(self):
        assert split_batch([10, 20, 30], max_size=100) == [[10, 20, 30]]

    def test_an_over_large_batch_is_halved(self):
        result = split_batch([40, 40, 40, 40], max_size=100)
        assert result == [[40, 40], [40, 40]]

    def test_splitting_preserves_record_order(self):
        result = split_batch([50, 50, 50], max_size=60)
        flat = [r for batch in result for r in batch]
        assert flat == [50, 50, 50]

    def test_a_single_oversized_record_is_refused_up_front(self):
        with pytest.raises(Invalid) as caught:
            split_batch([10, 500, 10], max_size=100)
        assert "exceeds the maximum" in str(caught.value)

    def test_a_bad_max_size_is_refused(self):
        with pytest.raises(Invalid):
            split_batch([10], max_size=0)


class TestReport:
    def test_the_report_counts_the_produced_batches(self):
        note = split_report([40, 40, 40, 40], max_size=100)
        assert "4 record(s) split into 2 batch(es)" in note
        assert "argues for a smaller batch size" in note
