from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.records import Record
from relay.topics import TopicRegistry


def registry() -> TopicRegistry:
    built = TopicRegistry()
    built.create("orders", partition_count=4)
    return built


class TestRouting:
    def test_one_key_always_lands_in_one_partition(self):
        topic = registry().get("orders")
        slots = {
            topic.route(Record(value=b"v", key=b"user-7"))
            for _ in range(10)
        }
        assert len(slots) == 1

    def test_unkeyed_records_round_robin(self):
        topic = registry().get("orders")
        slots = [
            topic.route(Record(value=b"v")) for _ in range(4)
        ]
        assert slots == [0, 1, 2, 3]

    def test_append_returns_the_full_address(self):
        topic = registry().get("orders")
        slot, offset = topic.append(
            Record(value=b"v", key=b"user-7")
        )
        assert offset == 0
        slot2, offset2 = topic.append(
            Record(value=b"w", key=b"user-7")
        )
        assert (slot2, offset2) == (slot, 1)


class TestTheRegistry:
    def test_duplicate_and_malformed_names_are_refused(self):
        built = registry()
        with pytest.raises(Invalid):
            built.create("orders", 2)
        with pytest.raises(Invalid):
            built.create("a/b", 2)
        with pytest.raises(Invalid):
            built.create("empty", 0)

    def test_a_missing_topic_is_missing(self):
        with pytest.raises(Missing):
            registry().get("ghost")

    def test_resizing_is_refused_with_the_honest_alternative(self):
        with pytest.raises(Invalid) as caught:
            registry().resize("orders", 8)
        message = str(caught.value)
        assert "breaks per-key order silently" in message
        assert "the same work done honestly" in message

    def test_the_audit_answers_where_a_key_lives(self):
        verdict = registry().audit_key("orders", b"user-7")
        assert "lives in partition" in verdict
        assert "lived there last month too" in verdict
