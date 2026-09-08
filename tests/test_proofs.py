from __future__ import annotations

from relay.proofs import (
    aggregateholds,
    bloomholds,
    framingholds,
    integrityholds,
    nosplitbrain,
    registry,
    throttleholds,
)


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
        finding = integrityholds.run()
        assert finding.holds
        assert finding.numbers["flips_missed"] == 0
        assert (
            finding.numbers["flips_caught"]
            == finding.numbers["positions_tested"]
        )

    def test_the_throttle_proof_does_not_beat_the_refill(self):
        finding = throttleholds.run()
        assert finding.holds
        assert finding.numbers["overshoot"] <= 0

    def test_the_framing_proof_agrees_at_every_split(self):
        finding = framingholds.run()
        assert finding.holds
        assert finding.numbers["disagreements"] == 0
        assert finding.numbers["drip_matches"]

    def test_the_aggregate_proof_agrees_across_groupings(self):
        finding = aggregateholds.run()
        assert finding.holds
        assert finding.numbers["all_groupings_agree"]
        assert finding.numbers["avg_trap_wrong_by"] > 0

    def test_the_bloom_proof_has_no_false_negatives(self):
        finding = bloomholds.run()
        assert finding.holds
        assert finding.numbers["false_negatives"] == 0

    def test_the_split_brain_proof_shows_the_one_voter_rule(self):
        finding = nosplitbrain.run()
        assert finding.holds
        assert finding.numbers["single_voter_disjoint_majority_pairs"] == 0
        assert finding.numbers["two_voter_disjoint_majority_pairs"] > 0
