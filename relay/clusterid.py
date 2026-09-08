"""Cluster id: the cluster's name for itself, checked so strangers stay out.

A cluster generates an identifier for itself once, when it is first
formed, and that id never changes for the life of the cluster. Its
job is to catch a mistake that is easy to make and expensive to
undo: a broker configured to point at the wrong cluster, a staging
broker aimed at production by a copied config, joining a cluster it
does not belong to and mixing its data in. Every broker that joins
presents the cluster id it believes it belongs to, and the cluster
rejects one whose id does not match, so a misconfigured broker
fails to join loudly instead of quietly corrupting the cluster's
data with its own. A fresh broker that has never joined any cluster
has no id yet and adopts the cluster's on its first successful
join, recording it so a later attempt to point it at a different
cluster is caught by the mismatch. The immutability is the whole
guarantee: because the id never changes, a mismatch always means
the broker and the cluster disagree about which cluster this is,
never that the cluster renamed itself, so the mismatch is always
the broker's error to fix. The registry generates the id once and
refuses to change it, rejects a join whose presented id differs
from the cluster's, and treats a broker with no id as adopting the
cluster's rather than as a mismatch, distinguishing a fresh broker
from a stray one. It refuses to form a cluster with an empty id,
which would match anything and defeat the check, and reports a
rejected join with both ids, because an operator seeing a broker
fail to join needs to see it is presenting a different cluster's id,
not guess at a network problem.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Fenced, Invalid


@dataclass
class ClusterIdentity:
    cluster_id: str

    def __post_init__(self) -> None:
        if not self.cluster_id:
            raise Invalid(
                "an empty cluster id matches anything and defeats the "
                "cross-cluster check"
            )

    def join(self, broker_presents: str | None) -> str:
        if broker_presents is None or broker_presents == "":
            return (
                f"fresh broker adopts cluster id '{self.cluster_id}' on its "
                "first join"
            )
        if broker_presents != self.cluster_id:
            raise Fenced(
                f"broker presents cluster id '{broker_presents}' but this "
                f"cluster is '{self.cluster_id}'; it belongs to a different "
                "cluster, a misconfigured broker failing loudly not corrupting"
            )
        return f"broker joined; cluster id '{self.cluster_id}' matches"

    def rename(self, _new_id: str) -> str:
        raise Invalid(
            "a cluster id never changes; if it could, a mismatch might mean a "
            "rename rather than a stray broker, defeating the check"
        )
