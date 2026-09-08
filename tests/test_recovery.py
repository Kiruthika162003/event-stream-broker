from __future__ import annotations

from relay.recovery import EpochMarker, RecoveryPlan

LEADER = [
    EpochMarker(4, 0),
    EpochMarker(5, 100),
    EpochMarker(6, 150),
]


class TestCleanRecovery:
    def test_a_matching_log_truncates_nothing(self):
        plan = RecoveryPlan(
            local_end=180, local_epochs=list(LEADER)
        )
        verdict = plan.recover(LEADER, leader_end=180)
        assert "nothing truncated" in verdict
        assert plan.discarded == 0
        assert plan.may_serve()


class TestTruncation:
    def test_records_past_the_agreement_are_discarded(self):
        plan = RecoveryPlan(
            local_end=200,
            local_epochs=[EpochMarker(4, 0), EpochMarker(5, 100)],
        )
        verdict = plan.recover(LEADER, leader_end=180)
        assert plan.truncated_to == 150
        assert plan.discarded == 50
        assert "discarded 50 unpromised record(s)" in verdict

    def test_a_divergent_epoch_start_truncates_earlier(self):
        plan = RecoveryPlan(
            local_end=200,
            local_epochs=[EpochMarker(4, 0), EpochMarker(5, 120)],
        )
        plan.recover(LEADER, leader_end=180)
        assert plan.truncated_to == 100
        assert plan.discarded == 100

    def test_the_count_is_logged_not_silent(self):
        plan = RecoveryPlan(
            local_end=200,
            local_epochs=[EpochMarker(4, 0), EpochMarker(5, 100)],
        )
        verdict = plan.recover(LEADER, leader_end=180)
        assert "not mistaken for a bug eating data" in verdict


class TestServingGate:
    def test_a_broker_serves_only_after_recovery(self):
        plan = RecoveryPlan(local_end=100, local_epochs=list(LEADER))
        assert not plan.may_serve()
        plan.recover(LEADER, leader_end=100)
        assert plan.may_serve()

    def test_the_index_is_rebuilt_during_recovery(self):
        plan = RecoveryPlan(local_end=180, local_epochs=list(LEADER))
        plan.recover(LEADER, leader_end=180)
        assert plan.index_rebuilt
