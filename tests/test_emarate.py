from __future__ import annotations

import pytest

from relay.emarate import EmaRate
from relay.errors import Invalid


class TestUpdate:
    def test_the_first_sample_seeds_the_average(self):
        e = EmaRate(alpha=0.5)
        assert e.update(100) == 100

    def test_it_moves_toward_a_new_sample_by_the_factor(self):
        e = EmaRate(alpha=0.5)
        e.update(100)
        # 0.5*0 ... seeded at 100, next: 0.5*200 + 0.5*100 = 150
        assert e.update(200) == 150

    def test_a_smoother_factor_moves_less(self):
        e = EmaRate(alpha=0.1)
        e.update(100)
        # 0.1*200 + 0.9*100 = 110
        assert e.update(200) == 110


class TestSeed:
    def test_it_seeds_with_the_first_sample_not_zero(self):
        e = EmaRate(alpha=0.2)
        e.update(500)
        # without seeding, this would still be crawling up from 0
        assert e.current() == 500


class TestConfig:
    def test_a_zero_factor_is_refused(self):
        with pytest.raises(Invalid):
            EmaRate(alpha=0.0)

    def test_a_factor_of_one_is_refused(self):
        with pytest.raises(Invalid):
            EmaRate(alpha=1.0)

    def test_current_before_any_sample_is_refused(self):
        with pytest.raises(Invalid):
            EmaRate(alpha=0.5).current()


class TestResponsiveness:
    def test_a_fast_factor_is_named_noisy(self):
        assert "noisier" in EmaRate(alpha=0.8).responsiveness()

    def test_a_slow_factor_is_named_smooth(self):
        assert "smooth" in EmaRate(alpha=0.1).responsiveness()
