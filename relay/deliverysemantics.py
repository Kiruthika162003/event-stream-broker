"""Delivery semantics: the guarantee is the weakest link in the whole chain.

Teams argue about at-most-once, at-least-once, and exactly-once as
if a single setting chose them, but the end-to-end guarantee is a
property of the whole chain, producer through broker to consumer,
and it is the weakest link that decides it. On the producer side,
acks-none can lose a record so it caps the chain at at-most-once no
matter what the consumer does, while acks-all with idempotence
gives no-loss no-duplicate delivery into the log. On the consumer
side, committing the offset before processing means a crash loses
the in-flight records, at-most-once, while committing after
processing means a crash reprocesses them, at-least-once. Exactly-
once end-to-end is the demanding case: it requires the producer to
be idempotent and transactional, the broker to hold the records
committed, and the consumer to commit its offset inside the same
transaction as its output, so that the offset advance and the
output either both happen or neither does. Any link short of that
degrades the whole chain to at-least-once at best. The resolver
takes the settings of each link and returns the guarantee the
combination actually provides, and it refuses to report exactly-
once unless every link supports it, because the most expensive
mistake in this space is a pipeline believed to be exactly-once
that is really at-least-once, quietly double-processing on every
retry. It names the weakest link when the guarantee falls short of
what was hoped, because knowing that the consumer's commit timing,
not the producer, is what caps a chain at at-least-once tells the
operator exactly which setting to change to strengthen it.
"""

from __future__ import annotations

from dataclasses import dataclass

AT_MOST_ONCE = "at-most-once"
AT_LEAST_ONCE = "at-least-once"
EXACTLY_ONCE = "exactly-once"


@dataclass(frozen=True)
class Chain:
    acks_all: bool
    idempotent: bool
    transactional: bool
    consumer_commits_after_process: bool
    consumer_commits_in_txn: bool

    def guarantee(self) -> str:
        if not self.acks_all:
            return AT_MOST_ONCE
        if not self.consumer_commits_after_process:
            return AT_MOST_ONCE
        if (
            self.idempotent
            and self.transactional
            and self.consumer_commits_in_txn
        ):
            return EXACTLY_ONCE
        return AT_LEAST_ONCE

    def weakest_link(self) -> str:
        g = self.guarantee()
        if g == EXACTLY_ONCE:
            return "every link supports exactly-once"
        if not self.acks_all:
            return "producer acks<all can lose a record: caps at at-most-once"
        if not self.consumer_commits_after_process:
            return (
                "consumer commits before processing: a crash loses "
                "in-flight records, at-most-once"
            )
        # at-least-once: name what is missing for exactly-once
        missing = []
        if not self.idempotent:
            missing.append("idempotent producer")
        if not self.transactional:
            missing.append("transactional producer")
        if not self.consumer_commits_in_txn:
            missing.append("consumer commit inside the transaction")
        return (
            "at-least-once; exactly-once needs " + ", ".join(missing)
        )
