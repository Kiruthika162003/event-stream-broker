from __future__ import annotations

import pytest

from relay.becomefollower import FollowerTransition
from relay.errors import Invalid


def _t():
    return FollowerTransition(log_end=1000, high_watermark=980)


class TestOrder:
    def test_the_full_transition_in_order(self):
        t = _t()
        assert "stopped accepting produce" in t.stop_serving()
        assert "discarded 20 uncommitted record(s)" in t.truncate(980)
        assert "resuming at 980" in t.start_fetching()
        assert t.fetching


class TestTruncate:
    def test_truncate_before_stopping_serving_is_refused(self):
        t = _t()
        with pytest.raises(Invalid) as caught:
            t.truncate(980)
        assert "stop accepting writes before truncating" in str(caught.value)

    def test_a_truncation_past_the_log_end_is_refused(self):
        t = _t()
        t.stop_serving()
        with pytest.raises(Invalid) as caught:
            t.truncate(2000)
        assert "records this broker does not have" in str(caught.value)


class TestFetch:
    def test_fetching_before_truncating_is_refused(self):
        t = _t()
        t.stop_serving()
        with pytest.raises(Invalid) as caught:
            t.start_fetching()
        assert "before truncating" in str(caught.value)
