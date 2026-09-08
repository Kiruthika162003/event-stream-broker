from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.wal import WriteAheadLog


class TestOrdering:
    def test_append_durable_then_apply(self):
        w = WriteAheadLog()
        off = w.append("set x=1")
        w.mark_durable(off)
        assert "applied entry 0" in w.apply(off)

    def test_applying_before_durable_is_refused(self):
        w = WriteAheadLog()
        off = w.append("set x=1")
        with pytest.raises(Invalid) as caught:
            w.apply(off)
        assert "not durable yet" in str(caught.value)

    def test_entries_apply_in_order(self):
        w = WriteAheadLog()
        w.append("a")
        w.append("b")
        w.mark_durable(1)  # durable to offset 1 -> durable_to=2
        with pytest.raises(Invalid):
            w.apply(1)  # cannot apply 1 before 0


class TestCheckpoint:
    def test_checkpoint_records_applied_position(self):
        w = WriteAheadLog()
        off = w.append("a")
        w.mark_durable(off)
        w.apply(off)
        assert "checkpoint at 1" in w.take_checkpoint()

    def test_replay_length_after_checkpoint(self):
        w = WriteAheadLog()
        for i in range(3):
            off = w.append(f"e{i}")
            w.mark_durable(off)
            w.apply(off)
        w.take_checkpoint()
        w.append("e3")  # after checkpoint, not yet applied
        assert "1 entry(ies) to replay" in w.replay_length()
