from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.mirroring import MirrorLink


def link() -> MirrorLink:
    return MirrorLink(
        source_topic="orders",
        dest_topic="orders-dr",
        dest_next_offset=200,
    )


class TestCopying:
    def test_offsets_translate_across_the_clusters(self):
        chosen = link()
        assert chosen.copy(0) == 200
        assert chosen.copy(1) == 201
        assert chosen.translate(0) == 200

    def test_reordering_is_refused(self):
        chosen = link()
        chosen.copy(0)
        chosen.copy(1)
        with pytest.raises(Invalid) as caught:
            chosen.copy(0)
        assert "broke the source's only guarantee" in str(
            caught.value
        )

    def test_a_gap_is_refused(self):
        chosen = link()
        chosen.copy(0)
        with pytest.raises(Invalid) as caught:
            chosen.copy(5)
        assert "a mirror with holes is not a mirror" in str(
            caught.value
        )


class TestTranslation:
    def test_an_unmirrored_offset_cannot_be_translated(self):
        with pytest.raises(Missing) as caught:
            link().translate(50)
        assert "would skip unmirrored records" in str(
            caught.value
        )


class TestLag:
    def test_the_lag_is_stated_honestly(self):
        chosen = link()
        chosen.copy(0)
        chosen.copy(1)
        status = chosen.status(source_end=10)
        assert "trails by 8 record(s)" in status
        assert "calls it zero" in status

    def test_being_caught_up_still_admits_the_next_instant(self):
        chosen = link()
        chosen.copy(0)
        status = chosen.status(source_end=1)
        assert "cannot promise for the next one" in status
