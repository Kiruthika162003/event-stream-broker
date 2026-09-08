from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.maxblock import BlockBudget


class TestProceed:
    def test_a_send_within_budget_proceeds(self):
        b = BlockBudget(budget=1000)
        b.wait_metadata(200)
        b.wait_buffer(300)
        assert b.can_proceed()
        assert "send proceeds" in b.resolve()
        assert b.remaining() == 500

    def test_a_send_over_budget_fails(self):
        b = BlockBudget(budget=1000)
        b.wait_buffer(1200)
        assert not b.can_proceed()
        assert "send fails" in b.resolve()


class TestCulprit:
    def test_a_metadata_dominated_timeout_names_metadata(self):
        b = BlockBudget(budget=100)
        b.wait_metadata(200)
        assert "cannot reach" in b.resolve()

    def test_a_buffer_dominated_timeout_names_buffer(self):
        b = BlockBudget(budget=100)
        b.wait_buffer(200)
        assert "too slow to drain" in b.resolve()


class TestConfig:
    def test_a_zero_budget_is_refused(self):
        with pytest.raises(Invalid):
            BlockBudget(budget=0)
