from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.streammerge import StreamMerge


class TestMergedWatermark:
    def test_it_is_the_minimum_across_inputs(self):
        m = StreamMerge()
        m.observe("a", 1000)
        m.observe("b", 800)
        m.observe("c", 1200)
        assert m.merged_watermark() == 800

    def test_a_slow_input_holds_the_merged_clock(self):
        m = StreamMerge()
        m.observe("fast", 5000)
        m.observe("slow", 100)
        assert m.merged_watermark() == 100
        assert m.laggard() == "slow"

    def test_no_inputs_is_zero(self):
        assert StreamMerge().merged_watermark() == 0


class TestRefusals:
    def test_a_backwards_watermark_is_refused(self):
        m = StreamMerge()
        m.observe("a", 1000)
        with pytest.raises(Invalid) as caught:
            m.observe("a", 900)
        assert "only advances" in str(caught.value)


class TestSpread:
    def test_the_spread_names_the_laggard_and_gap(self):
        m = StreamMerge()
        m.observe("fast", 5000)
        m.observe("slow", 100)
        note = m.spread()
        assert "held by 'slow'" in note
        assert "4900 behind the fastest" in note
