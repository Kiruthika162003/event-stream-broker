from __future__ import annotations

import pytest

from relay.deserialize import DIVERT, SKIP, STOP, PoisonHandler
from relay.errors import Invalid


class TestStop:
    def test_stop_halts_and_does_not_advance(self):
        h = PoisonHandler(policy=STOP)
        with pytest.raises(Invalid) as caught:
            h.on_poison(42)
        assert "stopping the partition" in str(caught.value)
        assert h.committed == 0


class TestSkip:
    def test_skip_advances_past_the_poison(self):
        h = PoisonHandler(policy=SKIP)
        note = h.on_poison(42)
        assert "skipped offset 42" in note
        assert h.committed == 43

    def test_skip_names_the_loss_as_chosen(self):
        h = PoisonHandler(policy=SKIP)
        assert "a loss the operator chose" in h.on_poison(1)


class TestDivert:
    def test_divert_keeps_the_record_and_advances(self):
        h = PoisonHandler(policy=DIVERT)
        note = h.on_poison(42)
        assert "diverted offset 42" in note
        assert h.committed == 43
        assert h.diverted == [42]


class TestConfigAndHealth:
    def test_an_unknown_policy_is_refused(self):
        with pytest.raises(Invalid):
            PoisonHandler(policy="ignore")

    def test_health_counts_hits(self):
        h = PoisonHandler(policy=SKIP)
        h.on_poison(1)
        h.on_poison(2)
        assert "2 poison pill(s) hit" in h.health()
