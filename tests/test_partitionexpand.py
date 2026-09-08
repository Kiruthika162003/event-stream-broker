from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.partitionexpand import (
    ExpansionRequest,
    evaluate_expansion,
    keys_would_split,
)


class TestUnkeyed:
    def test_an_unkeyed_topic_expands_freely(self):
        request = ExpansionRequest("logs", keyed=False, current_partitions=4, new_partitions=8)
        verdict = evaluate_expansion(request)
        assert "safe to expand 4 -> 8" in verdict
        assert "nothing moves" in verdict


class TestKeyed:
    def test_a_keyed_topic_expansion_is_refused(self):
        request = ExpansionRequest("orders", keyed=True, current_partitions=4, new_partitions=8)
        with pytest.raises(Invalid) as caught:
            evaluate_expansion(request)
        assert "breaking per-key order" in str(caught.value)
        assert "create a new topic and migrate" in str(caught.value)

    def test_an_operator_assertion_permits_it_with_a_warning(self):
        request = ExpansionRequest("orders", keyed=True, current_partitions=4, new_partitions=8)
        verdict = evaluate_expansion(
            request, operator_asserts_no_keys=True
        )
        assert "a landmine with a note on it, but permitted" in (
            verdict
        )


class TestRefusals:
    def test_a_non_increasing_expansion_is_refused(self):
        with pytest.raises(Invalid):
            ExpansionRequest("t", keyed=False, current_partitions=8, new_partitions=4)


class TestKeySplitting:
    def test_a_key_that_would_move_is_detected(self):
        # 5 % 4 = 1, 5 % 8 = 5: splits
        assert keys_would_split(5, 4, 8)

    def test_a_key_that_stays_is_detected(self):
        # 8 % 4 = 0, 8 % 8 = 0: same
        assert not keys_would_split(8, 4, 8)
