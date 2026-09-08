from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.exponentialbackoff import ExponentialBackoff


class TestCeiling:
    def test_the_ceiling_doubles_with_the_attempt(self):
        b = ExponentialBackoff(base_ms=100, cap_ms=100000)
        assert b.ceiling_ms(0) == 100
        assert b.ceiling_ms(1) == 200
        assert b.ceiling_ms(2) == 400
        assert b.ceiling_ms(3) == 800

    def test_the_ceiling_is_bounded_by_the_cap(self):
        b = ExponentialBackoff(base_ms=100, cap_ms=500)
        assert b.ceiling_ms(10) == 500  # would be 102400 uncapped


class TestJitter:
    def test_the_delay_is_within_the_ceiling(self):
        b = ExponentialBackoff(base_ms=100, cap_ms=100000, _rand=lambda: 0.5)
        assert b.delay_ms(2) == 200  # 0.5 * 400

    def test_full_jitter_can_be_zero(self):
        b = ExponentialBackoff(base_ms=100, cap_ms=100000, _rand=lambda: 0.0)
        assert b.delay_ms(3) == 0.0

    def test_full_jitter_reaches_the_ceiling(self):
        b = ExponentialBackoff(base_ms=100, cap_ms=100000, _rand=lambda: 1.0)
        assert b.delay_ms(1) == 200

    def test_two_clients_with_different_draws_diverge(self):
        # the whole point of jitter: same failure, different retry instants
        early = ExponentialBackoff(base_ms=100, cap_ms=100000, _rand=lambda: 0.1)
        late = ExponentialBackoff(base_ms=100, cap_ms=100000, _rand=lambda: 0.9)
        assert early.delay_ms(4) != late.delay_ms(4)


class TestRefusals:
    def test_a_negative_attempt_is_refused(self):
        b = ExponentialBackoff(base_ms=100, cap_ms=1000)
        with pytest.raises(Invalid):
            b.ceiling_ms(-1)

    def test_a_non_positive_base_is_refused(self):
        with pytest.raises(Invalid):
            ExponentialBackoff(base_ms=0, cap_ms=1000)

    def test_a_cap_below_the_base_is_refused(self):
        with pytest.raises(Invalid):
            ExponentialBackoff(base_ms=1000, cap_ms=100)


class TestNote:
    def test_the_note_states_the_ceiling(self):
        b = ExponentialBackoff(base_ms=100, cap_ms=100000)
        assert "under 400ms" in b.note(2)
