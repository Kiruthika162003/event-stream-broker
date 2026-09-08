from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.writeamplification import WriteAmplification


class TestRatio:
    def test_the_ratio_sums_the_components(self):
        w = WriteAmplification(
            client_bytes=1000,
            replication_factor=3,
            compaction_rewrites=1,
            index_bytes=200,
        )
        # 3000 replication + 1000 compaction + 200 index = 4200; /1000 = 4.2
        assert w.ratio() == 4.2

    def test_replication_dominated(self):
        w = WriteAmplification(
            client_bytes=1000,
            replication_factor=5,
            compaction_rewrites=0,
            index_bytes=10,
        )
        assert w.dominant() == "replication"
        assert "the factor you chose" in w.report()

    def test_compaction_dominated(self):
        w = WriteAmplification(
            client_bytes=1000,
            replication_factor=1,
            compaction_rewrites=8,
            index_bytes=10,
        )
        assert w.dominant() == "compaction"
        assert "relax the trigger" in w.report()


class TestRefusals:
    def test_zero_client_bytes_is_refused(self):
        with pytest.raises(Invalid):
            WriteAmplification(
                client_bytes=0, replication_factor=3,
                compaction_rewrites=0, index_bytes=0,
            )

    def test_a_zero_factor_is_refused(self):
        with pytest.raises(Invalid):
            WriteAmplification(
                client_bytes=1000, replication_factor=0,
                compaction_rewrites=0, index_bytes=0,
            )
