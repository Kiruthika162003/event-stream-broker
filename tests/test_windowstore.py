from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.windowstore import WindowStore


class TestPutGet:
    def test_the_same_key_has_separate_values_per_window(self):
        s = WindowStore(window_size=10, retention=100)
        s.put("a", window=0, value=1, now=0)
        s.put("a", window=10, value=2, now=10)
        assert s.get("a", 0) == 1
        assert s.get("a", 10) == 2

    def test_a_missing_entry_is_reported(self):
        s = WindowStore(window_size=10, retention=100)
        with pytest.raises(Missing) as caught:
            s.get("a", 0)
        assert "never set or retained away" in str(caught.value)


class TestRetention:
    def test_windows_older_than_retention_are_dropped(self):
        s = WindowStore(window_size=10, retention=100)
        s.put("a", window=0, value=1, now=0)
        s.put("a", window=200, value=2, now=200)
        with pytest.raises(Missing):
            s.get("a", 0)
        assert s.get("a", 200) == 2

    def test_putting_into_an_expired_window_is_refused(self):
        s = WindowStore(window_size=10, retention=100)
        s.put("a", window=200, value=1, now=200)
        with pytest.raises(Invalid) as caught:
            s.put("a", window=0, value=9, now=200)
        assert "already expired" in str(caught.value)

    def test_a_retention_shorter_than_a_window_is_refused(self):
        with pytest.raises(Invalid):
            WindowStore(window_size=100, retention=50)


class TestFetchRange:
    def test_it_returns_a_keys_windows_in_range(self):
        s = WindowStore(window_size=10, retention=1000)
        for w in (0, 10, 20, 30):
            s.put("a", window=w, value=w, now=w)
        assert s.fetch_range("a", 10, 20) == [(10, 10), (20, 20)]


class TestSpan:
    def test_span_reports_live_windows(self):
        s = WindowStore(window_size=10, retention=1000)
        s.put("a", window=0, value=1, now=0)
        s.put("a", window=50, value=2, now=50)
        assert "live windows 0..50" in s.live_span()
