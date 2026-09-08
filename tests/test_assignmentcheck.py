from __future__ import annotations

import pytest

from relay.assignmentcheck import AssignmentValidator
from relay.errors import Invalid


def validator() -> AssignmentValidator:
    return AssignmentValidator(all_partitions=set(range(6)))


class TestValid:
    def test_a_clean_assignment_passes(self):
        assignment = {"c1": {0, 1}, "c2": {2, 3}, "c3": {4, 5}}
        verdict = validator().validate(assignment)
        assert "each owned exactly once" in verdict


class TestDoubleOwned:
    def test_a_double_owned_partition_is_caught(self):
        assignment = {"c1": {0, 1, 2}, "c2": {2, 3, 4, 5}}
        double = validator().double_owned(assignment)
        assert double == {2: ["c1", "c2"]}

    def test_double_ownership_is_rejected_with_the_pair(self):
        assignment = {"c1": {0, 1, 2}, "c2": {2, 3, 4, 5}}
        with pytest.raises(Invalid) as caught:
            validator().validate(assignment)
        assert "double-owned (2 by c1, c2)" in str(caught.value)
        assert "conflicting offsets" in str(caught.value)


class TestOrphaned:
    def test_an_orphaned_partition_is_caught(self):
        assignment = {"c1": {0, 1}, "c2": {2, 3}}
        assert validator().orphaned(assignment) == {4, 5}

    def test_orphans_are_rejected_as_the_silent_gap(self):
        assignment = {"c1": {0, 1}, "c2": {2, 3}}
        with pytest.raises(Invalid) as caught:
            validator().validate(assignment)
        assert "orphaned [4, 5]" in str(caught.value)
        assert "read by nobody" in str(caught.value)


class TestBoth:
    def test_both_violations_report_together(self):
        assignment = {"c1": {0, 1, 2}, "c2": {2, 3}}
        with pytest.raises(Invalid) as caught:
            validator().validate(assignment)
        message = str(caught.value)
        assert "double-owned" in message
        assert "orphaned" in message
