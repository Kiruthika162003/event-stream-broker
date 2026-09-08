from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.prefetch import Prefetcher


def prefetcher() -> Prefetcher:
    return Prefetcher(high_mark=5, low_mark=2)


class TestPausing:
    def test_prefetch_pauses_at_the_high_mark(self):
        p = prefetcher()
        verdict = p.fetched(5)
        assert "prefetch paused" in verdict
        assert p.paused

    def test_prefetch_continues_below_the_mark(self):
        p = prefetcher()
        assert "prefetch continues" in p.fetched(3)
        assert not p.paused


class TestHysteresis:
    def test_resume_waits_for_the_low_mark(self):
        p = prefetcher()
        p.fetched(5)
        # drain by 2 -> buffered 3, still above low mark 2, stays paused
        p.processed(2)
        assert p.paused
        # drain one more -> buffered 2, at low mark, resumes
        verdict = p.processed(1)
        assert "prefetch resumed" in verdict
        assert not p.paused

    def test_a_low_mark_at_or_above_high_is_refused(self):
        with pytest.raises(Invalid) as caught:
            Prefetcher(high_mark=5, low_mark=5)
        assert "thrashes between paused and fetching" in str(
            caught.value
        )


class TestTheReport:
    def test_a_paused_prefetcher_names_the_bottleneck(self):
        p = prefetcher()
        p.fetched(5)
        report = p.report()
        assert "prefetch paused" in report
        assert "the processor, not the network" in report

    def test_an_active_prefetcher_reads_calm(self):
        p = prefetcher()
        p.fetched(2)
        assert "prefetch active" in p.report()
