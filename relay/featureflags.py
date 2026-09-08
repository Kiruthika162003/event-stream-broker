"""Feature flags: a new capability turns on only when every broker can speak it.

Upgrading a cluster is a rolling process, brokers restart onto the
new version one at a time, and for a stretch the cluster is mixed:
some brokers understand a new feature, transactions, a new record
format, and some do not. Turning on a feature during that window
is the classic rolling-upgrade disaster, because a broker that
does not understand the feature receives data or requests it
cannot parse, and it either errors or, worse, misinterprets. The
feature gate makes activation cluster-wide and unanimous: a
feature has a minimum version, and it may be enabled only when
every live broker meets that version, so a feature turns on the
moment the last old broker finishes upgrading and not one moment
before. The gate is monotonic within an upgrade but reversible
across a downgrade: if a broker rolls back to an old version, the
feature must turn off, because a feature enabled while one broker
cannot speak it is broken whether the broker is old-and-not-yet-
upgraded or old-and-rolled-back, the cause does not matter, only
the current minimum version does. The gate refuses to enable a
feature on operator request while any broker is below its
minimum, and it names the specific broker holding the feature
back, because an operator who ran the enable command and got a
refusal needs to know which broker to finish upgrading, not a
generic not-yet, and it reports the finalized features, the ones
now unanimously supported and safe to depend on, separately from
the pending ones, so the upgrade's progress is visible as a list
that grows rather than a boolean that flips at the end.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class FeatureGate:
    feature_min_version: dict[str, int]
    broker_versions: dict[str, int] = field(default_factory=dict)
    enabled: set[str] = field(default_factory=set)

    def cluster_min_version(self) -> int:
        if not self.broker_versions:
            raise Invalid("no brokers registered")
        return min(self.broker_versions.values())

    def laggard_for(self, feature: str) -> str | None:
        required = self.feature_min_version.get(feature)
        if required is None:
            raise Invalid(f"unknown feature {feature}")
        behind = sorted(
            (version, broker)
            for broker, version in self.broker_versions.items()
            if version < required
        )
        return behind[0][1] if behind else None

    def enable(self, feature: str) -> str:
        laggard = self.laggard_for(feature)
        if laggard is not None:
            raise Invalid(
                f"cannot enable {feature}: {laggard} is below the "
                f"required version {self.feature_min_version[feature]}"
                "; finish upgrading it, not a generic not-yet"
            )
        self.enabled.add(feature)
        return (
            f"{feature} enabled: every broker can speak it, safe "
            "to depend on"
        )

    def reconcile(self) -> list[str]:
        disabled = []
        for feature in sorted(self.enabled):
            if self.laggard_for(feature) is not None:
                disabled.append(feature)
        for feature in disabled:
            self.enabled.discard(feature)
        return disabled

    def report(self) -> str:
        pending = sorted(
            f
            for f in self.feature_min_version
            if f not in self.enabled
        )
        return (
            f"finalized: {sorted(self.enabled)}, pending: "
            f"{pending}; the upgrade is a list that grows, not a "
            "boolean that flips at the end"
        )
