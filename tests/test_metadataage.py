from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.metadataage import AgeThresholds, age_report, refresh_needed


def thresholds() -> AgeThresholds:
    return AgeThresholds(read_max_age=100, write_max_age=20)


class TestRefresh:
    def test_a_fresh_cache_needs_no_refresh(self):
        assert "no refresh" in refresh_needed(
            thresholds(), age=10, for_durable_write=True
        )

    def test_a_mid_age_cache_is_fine_for_reads(self):
        verdict = refresh_needed(
            thresholds(), age=50, for_durable_write=False
        )
        assert "no refresh" in verdict

    def test_the_same_age_is_stale_for_a_write(self):
        verdict = refresh_needed(
            thresholds(), age=50, for_durable_write=True
        )
        assert "refresh before this durable write" in verdict
        assert "the new leader will not have" in verdict

    def test_a_very_stale_read_still_only_costs_a_round_trip(self):
        verdict = refresh_needed(
            thresholds(), age=200, for_durable_write=False
        )
        assert "one not-leader round trip" in verdict


class TestReport:
    def test_the_report_shows_both_verdicts(self):
        report = age_report(thresholds(), age=50)
        assert "reads ok" in report
        assert "durable writes stale" in report

    def test_a_write_threshold_laxer_than_read_is_refused(self):
        with pytest.raises(Invalid):
            AgeThresholds(read_max_age=20, write_max_age=100)
