from __future__ import annotations

from relay.proofs import registry


class TestTheProofs:
    def test_every_proof_holds(self):
        assert registry.broken() == []

    def test_the_report_counts_them(self):
        report = registry.report()
        assert "proofs," in report

    def test_each_finding_has_a_claim_and_numbers(self):
        for finding in registry.all_findings():
            assert finding.claim
            assert finding.numbers

    def test_the_integrity_proof_misses_no_bit_flip(self):
        from relay.proofs import integrityholds

        finding = integrityholds.run()
        assert finding.holds
        assert finding.numbers["flips_missed"] == 0
        assert (
            finding.numbers["flips_caught"]
            == finding.numbers["positions_tested"]
        )
