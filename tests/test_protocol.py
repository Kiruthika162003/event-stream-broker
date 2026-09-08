from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.protocol import VersionRange, negotiate


class TestNegotiation:
    def test_the_highest_common_version_is_chosen(self):
        version, note = negotiate(
            "fetch",
            broker=VersionRange(3, 8),
            client=VersionRange(1, 6),
        )
        assert version == 6
        assert "negotiated at v6" in note

    def test_a_broker_max_below_client_max_caps_at_broker(self):
        version, _ = negotiate(
            "produce",
            broker=VersionRange(1, 4),
            client=VersionRange(2, 9),
        )
        assert version == 4


class TestFailureModes:
    def test_a_too_new_client_is_refused(self):
        with pytest.raises(Invalid) as caught:
            negotiate(
                "fetch",
                broker=VersionRange(1, 4),
                client=VersionRange(6, 9),
            )
        assert "the client is too new" in str(caught.value)
        assert "a dialect it dropped" in str(caught.value)

    def test_a_too_old_client_is_told_to_upgrade(self):
        with pytest.raises(Invalid) as caught:
            negotiate(
                "fetch",
                broker=VersionRange(6, 9),
                client=VersionRange(1, 4),
            )
        assert "its protocol retired" in str(caught.value)
        assert "must upgrade" in str(caught.value)


class TestRefusals:
    def test_an_inverted_range_is_refused(self):
        with pytest.raises(Invalid):
            VersionRange(5, 2)

    def test_ranges_that_touch_at_one_version_overlap(self):
        assert VersionRange(1, 5).overlaps(VersionRange(5, 9))
