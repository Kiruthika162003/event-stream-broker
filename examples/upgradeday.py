"""An upgrade day: version negotiation, feature gating, controller failover.

Run with: python -m examples.upgradeday
"""

from __future__ import annotations

from relay.controllerepoch import ControllerFencer
from relay.errors import Fenced
from relay.featureflags import FeatureGate
from relay.gracefulshutdown import ShutdownPlan
from relay.protocol import VersionRange, negotiate


def morning_the_negotiation():
    version, _ = negotiate(
        "fetch",
        broker=VersionRange(3, 8),
        client=VersionRange(1, 6),
    )
    print(f"morning: fetch negotiated at v{version}")


def midday_the_gate():
    gate = FeatureGate(
        feature_min_version={"transactions": 3},
        broker_versions={"b1": 5, "b2": 5, "b3": 3},
    )
    print(f"midday:  {gate.enable('transactions')}")


def afternoon_the_shutdown():
    plan = ShutdownPlan(
        departing="b3",
        led_partitions={0: ["b3", "b1"], 1: ["b3", "b2"]},
        caught_up={0: {"b1"}, 1: {"b2"}},
    )
    plan.execute()
    print(f"afternoon: {plan.report().splitlines()[0]}")


def evening_the_controller():
    fencer = ControllerFencer()
    fencer.take_over("b1", epoch=7)
    fencer.take_over("b2", epoch=8)
    try:
        fencer.apply_change(7, "reassign p0")
    except Fenced:
        print(f"evening: {fencer.report().split(';')[0].strip()}")


def main() -> int:
    morning_the_negotiation()
    midday_the_gate()
    afternoon_the_shutdown()
    evening_the_controller()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
