from __future__ import annotations

import pytest

from relay.errors import Invalid
from relay.featureflags import FeatureGate


def gate() -> FeatureGate:
    return FeatureGate(
        feature_min_version={"transactions": 3, "newformat": 5},
        broker_versions={"b1": 5, "b2": 5, "b3": 3},
    )


class TestEnabling:
    def test_a_feature_all_can_speak_enables(self):
        verdict = gate().enable("transactions")
        assert "every broker can speak it" in verdict

    def test_a_feature_a_laggard_cannot_speak_is_refused(self):
        with pytest.raises(Invalid) as caught:
            gate().enable("newformat")
        assert "b3 is below the required version 5" in str(
            caught.value
        )
        assert "finish upgrading it" in str(caught.value)

    def test_an_unknown_feature_is_refused(self):
        with pytest.raises(Invalid):
            gate().enable("teleport")

    def test_the_laggard_is_named_specifically(self):
        assert gate().laggard_for("newformat") == "b3"
        assert gate().laggard_for("transactions") is None


class TestReconcile:
    def test_a_downgrade_disables_a_finalized_feature(self):
        g = gate()
        g.enable("transactions")
        g.broker_versions["b2"] = 1
        disabled = g.reconcile()
        assert "transactions" in disabled
        assert "transactions" not in g.enabled

    def test_a_stable_cluster_reconciles_to_nothing(self):
        g = gate()
        g.enable("transactions")
        assert g.reconcile() == []


class TestReport:
    def test_the_report_lists_finalized_and_pending(self):
        g = gate()
        g.enable("transactions")
        report = g.report()
        assert "finalized: ['transactions']" in report
        assert "pending: ['newformat']" in report
        assert "a list that grows" in report

    def test_no_brokers_has_no_min_version(self):
        with pytest.raises(Invalid):
            FeatureGate(
                feature_min_version={"x": 1}
            ).cluster_min_version()
