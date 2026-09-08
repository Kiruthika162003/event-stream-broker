from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.sloppyquorum import CLEAN, FAILED, SLOPPY, SloppyQuorum


class TestOutcome:
    def test_enough_natural_replicas_is_clean(self):
        q = SloppyQuorum(write_quorum=3, natural_up=3, substitutes_available=2)
        assert q.outcome() == CLEAN
        assert "clean write" in q.resolve()

    def test_substitutes_make_it_sloppy(self):
        q = SloppyQuorum(write_quorum=3, natural_up=1, substitutes_available=5)
        assert q.outcome() == SLOPPY
        assert q.substitutes_used() == 2
        assert "sloppy write using 2 substitute(s)" in q.resolve()

    def test_too_few_nodes_fails(self):
        q = SloppyQuorum(write_quorum=3, natural_up=1, substitutes_available=1)
        assert q.outcome() == FAILED
        with pytest.raises(Invalid) as caught:
            q.resolve()
        assert "the write fails" in str(caught.value)


class TestSubstitutes:
    def test_a_clean_write_uses_no_substitutes(self):
        q = SloppyQuorum(write_quorum=3, natural_up=4, substitutes_available=0)
        assert q.substitutes_used() == 0


class TestConfig:
    def test_a_zero_quorum_is_refused(self):
        with pytest.raises(Invalid):
            SloppyQuorum(write_quorum=0, natural_up=1, substitutes_available=1)
