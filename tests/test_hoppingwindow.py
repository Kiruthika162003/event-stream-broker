from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.hoppingwindow import HoppingWindows


class TestWindowsFor:
    def test_a_record_lands_in_overlapping_windows(self):
        w = HoppingWindows(size=10, hop=5)
        assert w.windows_for(12) == [5, 10]

    def test_a_tumbling_config_puts_a_record_in_one_window(self):
        w = HoppingWindows(size=10, hop=10)
        assert w.windows_for(12) == [10]

    def test_windows_near_time_zero_do_not_go_negative(self):
        w = HoppingWindows(size=10, hop=5)
        assert w.windows_for(3) == [0]

    def test_a_boundary_record_belongs_to_the_new_window_only(self):
        w = HoppingWindows(size=10, hop=5)
        # at t=10, window starting 0 has ended (0..10 exclusive), 5 and 10 open
        assert w.windows_for(10) == [5, 10]


class TestRefusals:
    def test_a_hop_larger_than_size_is_refused(self):
        with pytest.raises(Invalid) as caught:
            HoppingWindows(size=5, hop=10)
        assert "leaves gaps" in str(caught.value)

    def test_a_non_positive_hop_is_refused(self):
        with pytest.raises(Invalid):
            HoppingWindows(size=10, hop=0)


class TestOverlap:
    def test_overlap_factor_is_size_over_hop_rounded_up(self):
        assert HoppingWindows(size=10, hop=3).overlap_factor() == 4

    def test_report_states_the_multiplicity(self):
        note = HoppingWindows(size=10, hop=5).report()
        assert "each record lands in 2 window(s)" in note
