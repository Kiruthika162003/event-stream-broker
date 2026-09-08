from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.watermarkpropagation import WatermarkView


class TestExposure:
    def test_the_follower_exposes_its_last_response_watermark(self):
        view = WatermarkView(leader_watermark=1000, last_response_watermark=940)
        assert view.follower_exposes() == 940

    def test_the_gap_is_records_committed_since_the_last_fetch(self):
        view = WatermarkView(leader_watermark=1000, last_response_watermark=940)
        assert view.propagation_gap() == 60

    def test_a_follower_ahead_of_the_leader_is_refused(self):
        with pytest.raises(Invalid) as caught:
            WatermarkView(leader_watermark=900, last_response_watermark=950)
        assert "not committed" in str(caught.value)


class TestRefresh:
    def test_a_fetch_round_refreshes_the_exposed_watermark(self):
        view = WatermarkView(leader_watermark=1000, last_response_watermark=940)
        view.refresh(1000)
        assert view.follower_exposes() == 1000
        assert view.propagation_gap() == 0

    def test_a_lower_watermark_in_a_response_is_refused(self):
        view = WatermarkView(leader_watermark=1000, last_response_watermark=940)
        with pytest.raises(Invalid) as caught:
            view.refresh(900)
        assert "only advances" in str(caught.value)


class TestDescribe:
    def test_the_description_states_the_gap(self):
        view = WatermarkView(leader_watermark=1000, last_response_watermark=940)
        note = view.describe()
        assert "follower exposes 940" in note
        assert "60 record(s) committed" in note
