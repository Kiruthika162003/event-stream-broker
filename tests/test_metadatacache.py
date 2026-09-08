from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.metadatacache import MetadataCache


def cache() -> MetadataCache:
    c = MetadataCache()
    c.install(5, {0: "b1", 1: "b2"})
    return c


class TestInstall:
    def test_a_newer_version_installs(self):
        c = cache()
        c.install(6, {0: "b3", 1: "b2"})
        assert c.leader_of(0) == "b3"

    def test_an_older_version_is_refused(self):
        c = cache()
        with pytest.raises(Invalid) as caught:
            c.install(4, {})
        assert "route backward in time" in str(caught.value)

    def test_an_unknown_partition_prompts_refresh(self):
        with pytest.raises(Invalid):
            cache().leader_of(99)


class TestErrorRefresh:
    def test_a_not_leader_error_corrects_the_cache(self):
        c = cache()
        verdict = c.on_not_leader(0, new_version=6, new_leader="b5")
        assert "corrected exactly when proven wrong" in verdict
        assert c.leader_of(0) == "b5"
        assert c.refreshes_on_error == 1


class TestProactiveRefresh:
    def test_a_newer_version_seen_refreshes(self):
        c = cache()
        verdict = c.on_newer_version_seen(7, {0: "b1", 1: "b9"})
        assert "refreshed proactively to version 7" in verdict
        assert c.refreshes_proactive == 1

    def test_an_older_seen_version_does_nothing(self):
        c = cache()
        assert "no refresh" in c.on_newer_version_seen(3, {})


class TestHealth:
    def test_mostly_error_refreshes_flags_churn(self):
        c = cache()
        c.on_not_leader(0, 6, "b5")
        c.on_not_leader(1, 7, "b6")
        c.on_newer_version_seen(8, {0: "b5", 1: "b6"})
        health = c.health()
        assert "2 error refresh(es), 1 proactive" in health
        assert "a cluster churning leadership" in health

    def test_a_stable_cache_says_so(self):
        assert "the cache has been stable" in cache().health()
