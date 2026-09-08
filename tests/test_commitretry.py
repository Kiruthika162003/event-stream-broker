from __future__ import annotations

import pytest

from relay.commitretry import (
    COORDINATOR_MOVED,
    ILLEGAL_GENERATION,
    TRANSIENT,
    CommitRetrier,
)
from relay.errors import Invalid


def retrier() -> CommitRetrier:
    return CommitRetrier(max_retries=3)


class TestTransient:
    def test_a_transient_failure_retries_with_backoff(self):
        verdict = retrier().on_failure(TRANSIENT, attempt=1)
        assert "retry 2 with backoff" in verdict
        assert "offset commits are idempotent" in verdict

    def test_exhausted_transient_retries_abandon(self):
        r = retrier()
        verdict = r.on_failure(TRANSIENT, attempt=3)
        assert "retries exhausted" in verdict
        assert r.abandoned == 1


class TestCoordinatorMoved:
    def test_a_moved_coordinator_routes_not_retries(self):
        r = retrier()
        verdict = r.on_failure(COORDINATOR_MOVED, attempt=1)
        assert "route to the new coordinator" in verdict
        assert "loops forever" in verdict
        assert r.redirects == 1


class TestIllegalGeneration:
    def test_illegal_generation_abandons_and_rejoins(self):
        r = retrier()
        verdict = r.on_failure(ILLEGAL_GENERATION, attempt=1)
        assert "abandon and rejoin" in verdict
        assert "busy and making no progress" in verdict
        assert r.abandoned == 1

    def test_an_unknown_cause_is_refused(self):
        with pytest.raises(Invalid):
            retrier().on_failure("mystery", attempt=1)

    def test_a_zero_retry_budget_is_refused(self):
        with pytest.raises(Invalid):
            CommitRetrier(max_retries=0)


class TestTheReport:
    def test_the_report_separates_the_causes(self):
        r = retrier()
        r.on_failure(TRANSIENT, 1)
        r.on_failure(COORDINATOR_MOVED, 1)
        r.on_failure(ILLEGAL_GENERATION, 1)
        report = r.report()
        assert "1 transient retry(ies), 1 redirect(s), 1 abandoned" in (
            report
        )
        assert "rebalancing too often" in report
