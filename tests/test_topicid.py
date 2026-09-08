from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.topicid import TopicRegistry


class TestCreate:
    def test_each_topic_gets_a_unique_id(self):
        reg = TopicRegistry()
        a = reg.create("orders")
        b = reg.create("billing")
        assert a != b

    def test_a_duplicate_live_name_is_refused(self):
        reg = TopicRegistry()
        reg.create("orders")
        with pytest.raises(Invalid) as caught:
            reg.create("orders")
        assert "already live" in str(caught.value)


class TestResolve:
    def test_a_live_id_resolves_to_its_name(self):
        reg = TopicRegistry()
        tid = reg.create("orders")
        assert reg.resolve_id(tid) == "orders"

    def test_a_deleted_topics_id_is_unknown(self):
        reg = TopicRegistry()
        tid = reg.create("orders")
        reg.delete("orders")
        with pytest.raises(Missing) as caught:
            reg.resolve_id(tid)
        assert "refresh metadata" in str(caught.value)


class TestRecreate:
    def test_a_recreated_topic_gets_a_fresh_id_never_reused(self):
        reg = TopicRegistry()
        first = reg.create("orders")
        reg.delete("orders")
        second = reg.create("orders")
        assert first != second
        # the old id stays retired, never handed out again
        assert first in reg.retired_ids

    def test_a_stale_client_id_is_detected_as_recreated(self):
        reg = TopicRegistry()
        first = reg.create("orders")
        reg.delete("orders")
        reg.create("orders")
        assert reg.is_recreated("orders", client_saw_id=first)

    def test_a_current_client_id_is_not_recreated(self):
        reg = TopicRegistry()
        tid = reg.create("orders")
        assert not reg.is_recreated("orders", client_saw_id=tid)


class TestDelete:
    def test_deleting_an_unknown_topic_is_missing(self):
        reg = TopicRegistry()
        with pytest.raises(Missing):
            reg.delete("nope")
