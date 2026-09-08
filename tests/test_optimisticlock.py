from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.optimisticlock import OptimisticValue


class TestCompareAndSet:
    def test_a_matching_version_commits(self):
        v = OptimisticValue()
        _val, ver = v.read()
        assert "version now 1" in v.compare_and_set(ver, 42)
        assert v.value == 42

    def test_a_stale_version_conflicts(self):
        v = OptimisticValue()
        _val, ver = v.read()
        v.compare_and_set(ver, 10)  # version -> 1
        # a second writer using the old version 0 conflicts
        with pytest.raises(Invalid) as caught:
            v.compare_and_set(ver, 20)
        assert "another writer changed it" in str(caught.value)

    def test_retry_after_reread_succeeds(self):
        v = OptimisticValue()
        _val, ver = v.read()
        v.compare_and_set(ver, 10)
        # re-read and retry on the new version
        _val2, ver2 = v.read()
        assert "version now 2" in v.compare_and_set(ver2, 20)


class TestConflictRate:
    def test_it_tracks_conflicts(self):
        v = OptimisticValue()
        _val, ver = v.read()
        v.compare_and_set(ver, 1)  # commit
        with pytest.raises(Invalid):
            v.compare_and_set(ver, 2)  # conflict on stale version
        assert "1/2 writes conflicted (50%)" in v.conflict_rate()

    def test_no_writes_yet(self):
        assert "no writes yet" in OptimisticValue().conflict_rate()
