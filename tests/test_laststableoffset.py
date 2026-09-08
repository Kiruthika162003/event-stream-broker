from __future__ import annotations

import pytest

from relay.errors import Invalid, Missing
from relay.laststableoffset import LastStableOffset


class TestLso:
    def test_with_no_open_transactions_the_lso_is_the_watermark(self):
        lso = LastStableOffset(high_watermark=100)
        assert lso.last_stable_offset() == 100

    def test_an_open_transaction_holds_the_lso_at_its_start(self):
        lso = LastStableOffset(high_watermark=100)
        lso.begin("t1", first_offset=40)
        assert lso.last_stable_offset() == 40

    def test_the_oldest_open_transaction_wins(self):
        lso = LastStableOffset(high_watermark=100)
        lso.begin("t1", first_offset=60)
        lso.begin("t2", first_offset=40)  # older
        assert lso.last_stable_offset() == 40

    def test_resolving_the_oldest_advances_to_the_next(self):
        lso = LastStableOffset(high_watermark=100)
        lso.begin("t1", first_offset=40)
        lso.begin("t2", first_offset=70)
        lso.resolve("t1")  # commit or abort, either way it is decided
        assert lso.last_stable_offset() == 70

    def test_resolving_all_advances_to_the_watermark(self):
        lso = LastStableOffset(high_watermark=100)
        lso.begin("t1", first_offset=40)
        lso.resolve("t1")
        assert lso.last_stable_offset() == 100


class TestVisibility:
    def test_a_record_below_the_lso_is_visible(self):
        lso = LastStableOffset(high_watermark=100)
        lso.begin("t1", first_offset=40)
        assert lso.is_visible_to_read_committed(39)

    def test_a_record_at_or_above_the_lso_is_withheld(self):
        lso = LastStableOffset(high_watermark=100)
        lso.begin("t1", first_offset=40)
        assert not lso.is_visible_to_read_committed(40)
        assert not lso.is_visible_to_read_committed(90)  # committed but withheld

    def test_the_withheld_gap_is_watermark_minus_lso(self):
        lso = LastStableOffset(high_watermark=100)
        lso.begin("t1", first_offset=40)
        assert lso.withheld_gap() == 60


class TestRefusals:
    def test_a_transaction_beginning_past_the_watermark_is_refused(self):
        lso = LastStableOffset(high_watermark=100)
        with pytest.raises(Invalid) as caught:
            lso.begin("t1", first_offset=150)
        assert "do not exist" in str(caught.value)

    def test_resolving_an_unknown_transaction_is_missing(self):
        lso = LastStableOffset(high_watermark=100)
        with pytest.raises(Missing):
            lso.resolve("ghost")


class TestNote:
    def test_the_note_states_the_withheld_count(self):
        lso = LastStableOffset(high_watermark=100)
        lso.begin("t1", first_offset=40)
        assert "60 record(s) withheld" in lso.note()
