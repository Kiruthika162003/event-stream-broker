from __future__ import annotations

import pytest

from relay import cli


class TestTheCli:
    def test_summary_reports_zero_broken(self, capsys):
        code = cli.main(["summary"])
        out = capsys.readouterr().out
        assert "proofs (0 broken)" in out
        assert code == 0

    def test_check_passes_clean(self, capsys):
        code = cli.main(["check"])
        assert "all proofs hold" in capsys.readouterr().out
        assert code == 0

    def test_proofs_prints_the_page(self, capsys):
        cli.main(["proofs"])
        assert "watermarkholds" in capsys.readouterr().out

    def test_no_command_is_refused(self):
        with pytest.raises(SystemExit):
            cli.main([])
