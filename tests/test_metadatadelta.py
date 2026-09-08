from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.metadatadelta import MetadataApplier


class TestApply:
    def test_deltas_apply_in_sequence(self):
        m = MetadataApplier()
        m.full_image(10)
        assert "delta 11 applied" in m.apply_delta(11)
        assert "delta 12 applied" in m.apply_delta(12)

    def test_a_gap_forces_a_resync(self):
        m = MetadataApplier()
        m.full_image(10)
        with pytest.raises(Invalid) as caught:
            m.apply_delta(13)
        assert "full resync is required" in str(caught.value)
        assert m.needs_resync

    def test_an_older_delta_is_refused(self):
        m = MetadataApplier()
        m.full_image(10)
        m.apply_delta(11)
        with pytest.raises(Invalid) as caught:
            m.apply_delta(10)
        assert "older than the last applied" in str(caught.value)

    def test_a_duplicate_last_delta_is_a_no_op(self):
        m = MetadataApplier()
        m.full_image(10)
        m.apply_delta(11)
        assert "no-op" in m.apply_delta(11)


class TestResyncRecovery:
    def test_a_full_image_clears_the_gap(self):
        m = MetadataApplier()
        m.full_image(10)
        with pytest.raises(Invalid):
            m.apply_delta(13)
        assert m.needs_resync
        m.full_image(13)
        assert not m.needs_resync
        assert "view whole through sequence 13" in m.view_status()


class TestStatus:
    def test_status_reports_the_gap(self):
        m = MetadataApplier()
        m.full_image(10)
        with pytest.raises(Invalid):
            m.apply_delta(20)
        assert "resync is pending" in m.view_status()
