from __future__ import annotations

import pytest

from relay.batching import Batch, CompressionLedger
from relay.errors import Invalid


class TestBatchOverhead:
    def test_batching_amortizes_the_per_record_overhead(self):
        batch = Batch(raw_record_bytes=[100, 100, 100])
        # unbatched: 3*(100+30)=390; batched: 300+60=360
        assert batch.unbatched_bytes() == 390
        assert batch.batched_bytes() == 360
        assert batch.overhead_saved() == 30

    def test_an_empty_batch_is_refused(self):
        with pytest.raises(Invalid):
            Batch(raw_record_bytes=[])


class TestCompression:
    def test_a_compressible_batch_is_stored_smaller(self):
        ledger = CompressionLedger(compressor="zstd")
        batch = Batch(raw_record_bytes=[1000, 1000])
        verdict = ledger.store(batch, compressed_size=400)
        assert "compressed 2060 -> 400" in verdict
        assert ledger.stored_compressed == 1

    def test_an_incompressible_batch_is_stored_raw(self):
        ledger = CompressionLedger(compressor="zstd")
        batch = Batch(raw_record_bytes=[500])
        verdict = ledger.store(batch, compressed_size=9999)
        assert "stored raw" in verdict
        assert "paying to make data bigger" in verdict
        assert ledger.stored_raw_negative == 1

    def test_a_negative_size_is_refused(self):
        ledger = CompressionLedger(compressor="gzip")
        with pytest.raises(Invalid):
            ledger.store(Batch([100]), compressed_size=-1)


class TestTheRatio:
    def test_the_realized_ratio_is_measured_not_advertised(self):
        ledger = CompressionLedger(compressor="zstd")
        ledger.store(Batch([1000, 1000]), 400)
        ledger.store(Batch([500]), 9999)
        report = ledger.realized_ratio()
        assert "realized" in report
        assert "1 stored raw" in report
        assert "disagree on every binary topic" in report

    def test_measuring_nothing_is_refused(self):
        with pytest.raises(Invalid):
            CompressionLedger(compressor="z").realized_ratio()
