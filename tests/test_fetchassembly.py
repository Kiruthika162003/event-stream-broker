from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.fetchassembly import FetchAssembler


class TestFairRotation:
    def test_each_partition_gets_its_turn_over_rounds(self):
        assembler = FetchAssembler(response_budget=100)
        avail = [(0, 60), (1, 60), (2, 60)]
        first = assembler.assemble(list(avail))
        second = assembler.assemble(list(avail))
        third = assembler.assemble(list(avail))
        assert first[0] == [0]
        assert second[0] == [1]
        assert third[0] == [2]

    def test_no_partition_is_permanently_starved(self):
        assembler = FetchAssembler(response_budget=100)
        avail = [(0, 60), (1, 60), (2, 60)]
        served_ever = set()
        for _ in range(3):
            served, _ = assembler.assemble(list(avail))
            served_ever.update(served)
        assert served_ever == {0, 1, 2}

    def test_multiple_small_partitions_pack_together(self):
        assembler = FetchAssembler(response_budget=200)
        served, deferred = assembler.assemble(
            [(0, 60), (1, 60), (2, 60)]
        )
        assert len(served) == 3
        assert deferred == []


class TestOversizedRecord:
    def test_an_oversized_record_is_served_alone(self):
        assembler = FetchAssembler(response_budget=100)
        served, deferred = assembler.assemble([(5, 500)])
        assert served == [5]
        assert deferred == []


class TestRefusals:
    def test_a_zero_budget_is_refused(self):
        with pytest.raises(Invalid):
            FetchAssembler(response_budget=0)

    def test_no_partitions_is_refused(self):
        with pytest.raises(Invalid):
            FetchAssembler(response_budget=100).assemble([])


class TestTheReport:
    def test_deferred_partitions_are_named_calmly(self):
        assembler = FetchAssembler(response_budget=100)
        served, deferred = assembler.assemble(
            [(0, 60), (1, 60), (2, 60)]
        )
        report = assembler.report(served, deferred)
        assert "deferred to a later round" in report
        assert "none starves" in report
