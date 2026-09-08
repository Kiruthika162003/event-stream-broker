from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.zerocopy import FetchPath


class TestZeroCopy:
    def test_a_plain_modern_fetch_is_zero_copy(self):
        path = FetchPath(needs_downconversion=False, needs_encryption=False)
        assert path.is_zero_copy()
        assert path.cpu_multiple() == 1.0
        assert "zero-copy" in path.classify()

    def test_downconversion_breaks_zero_copy(self):
        path = FetchPath(needs_downconversion=True, needs_encryption=False)
        assert not path.is_zero_copy()
        assert path.cpu_multiple() == 8.0
        assert "raises CPU for everyone" in path.classify()

    def test_encryption_breaks_zero_copy(self):
        path = FetchPath(needs_downconversion=False, needs_encryption=True)
        assert not path.is_zero_copy()
        assert path.cpu_multiple() == 2.0
        assert "TLS must encrypt" in path.classify()

    def test_a_conversion_cheaper_than_zero_copy_is_refused(self):
        with pytest.raises(Invalid):
            FetchPath(
                needs_downconversion=True,
                needs_encryption=False,
                convert_cpu_multiple=0.5,
            )
