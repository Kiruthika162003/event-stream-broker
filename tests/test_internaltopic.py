from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.internaltopic import InternalTopicManager


def _mgr():
    return InternalTopicManager(app_id="orders-app")


class TestName:
    def test_the_name_is_prefixed_with_the_app_id(self):
        assert _mgr().name_for("repartition") == "orders-app-repartition"


class TestCreate:
    def test_a_matching_partition_count_creates_the_topic(self):
        m = _mgr()
        note = m.create("repartition", partitions=6, source_partitions=6)
        assert "6 partition(s)" in note
        assert "orders-app-repartition" in m.owned()

    def test_a_collision_with_a_user_topic_is_refused(self):
        m = InternalTopicManager(
            app_id="orders-app",
            user_topics={"orders-app-repartition"},
        )
        with pytest.raises(Invalid) as caught:
            m.create("repartition", partitions=6, source_partitions=6)
        assert "does not own" in str(caught.value)

    def test_a_mismatched_partition_count_is_refused(self):
        m = _mgr()
        with pytest.raises(Invalid) as caught:
            m.create("repartition", partitions=3, source_partitions=6)
        assert "breaks" in str(caught.value)
        assert "co-partitioning" in str(caught.value)


class TestDelete:
    def test_an_internal_topic_is_deleted(self):
        m = _mgr()
        m.create("changelog", partitions=4, source_partitions=4)
        assert "deleted internal topic" in m.delete("orders-app-changelog")

    def test_deleting_a_non_internal_topic_is_refused(self):
        m = _mgr()
        with pytest.raises(Invalid) as caught:
            m.delete("some-user-topic")
        assert "meant to keep" in str(caught.value)
