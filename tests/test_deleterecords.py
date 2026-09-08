from __future__ import annotations

import pytest

from relay.deleterecords import LogHead
from relay.errors import Invalid


def head() -> LogHead:
    return LogHead(log_start=100, high_watermark=1000)


class TestDeletion:
    def test_deleting_advances_the_log_start(self):
        h = head()
        verdict = h.delete_before(500)
        assert "deleted 400 record(s) from 100 to 500" in verdict
        assert h.log_start == 500

    def test_deleting_past_the_watermark_is_refused(self):
        with pytest.raises(Invalid) as caught:
            head().delete_before(2000)
        assert "desyncs the log-start from reality" in str(
            caught.value
        )

    def test_deleting_below_the_start_is_a_noop(self):
        h = head()
        verdict = h.delete_before(50)
        assert "no-op" in verdict
        assert "a retry after a timeout succeeds" in verdict
        assert h.log_start == 100

    def test_inverted_head_is_refused(self):
        with pytest.raises(Invalid):
            LogHead(log_start=500, high_watermark=100)


class TestConsumerWarning:
    def test_deleting_unread_data_warns_deliberately(self):
        h = head()
        verdict = h.delete_before(
            500, committed_offsets={"billing": 200}
        )
        assert "WARNING" in verdict
        assert "deleting data they never consumed" in verdict

    def test_deleting_read_data_is_clean(self):
        h = head()
        verdict = h.delete_before(
            500, committed_offsets={"billing": 800}
        )
        assert "WARNING" not in verdict
