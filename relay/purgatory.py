"""Purgatory: requests that wait on a condition, freed by event or by clock.

Two of the broker's most common operations are waits, not
computations. An acks-all produce waits until the in-sync set
has replicated the record; a long-poll fetch waits until enough
bytes arrive. Blocking a thread per waiting request would cap
concurrency at the thread count, so waiting requests go to a
purgatory: they are parked keyed by the condition that would
satisfy them, and when an event advances that condition the
satisfied requests are completed in one sweep rather than each
polling. The timeout is the safety net that makes the wait
bounded: every parked request carries a deadline, and one whose
condition never arrives is completed with a timeout result
rather than parked forever, because a request that can wait
without end is a resource leak wearing a feature's clothes. The
report separates completions by event from completions by
timeout, since a purgatory where most requests time out is a
purgatory whose conditions are not being met, which is a
different problem from a slow one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class DelayedRequest:
    request_id: str
    threshold: int
    deadline: int
    completed: bool = False
    outcome: str = ""


@dataclass
class Purgatory:
    requests: dict[str, list[DelayedRequest]] = field(
        default_factory=dict
    )
    completed_by_event: int = 0
    completed_by_timeout: int = 0

    def park(
        self,
        key: str,
        request_id: str,
        threshold: int,
        deadline: int,
    ) -> str:
        if deadline < 1:
            raise Invalid(
                "a request with no deadline can wait forever, "
                "which is a leak wearing a feature's clothes"
            )
        self.requests.setdefault(key, []).append(
            DelayedRequest(
                request_id=request_id,
                threshold=threshold,
                deadline=deadline,
            )
        )
        return f"{request_id} parked on {key} at threshold {threshold}"

    def on_progress(self, key: str, value: int) -> list[str]:
        completed = []
        for request in self.requests.get(key, []):
            if not request.completed and value >= request.threshold:
                request.completed = True
                request.outcome = "satisfied"
                self.completed_by_event += 1
                completed.append(request.request_id)
        self._reap(key)
        return sorted(completed)

    def on_tick(self, now: int) -> list[str]:
        timed_out = []
        for requests in self.requests.values():
            for request in requests:
                if (
                    not request.completed
                    and now >= request.deadline
                ):
                    request.completed = True
                    request.outcome = "timeout"
                    self.completed_by_timeout += 1
                    timed_out.append(request.request_id)
        for key in list(self.requests):
            self._reap(key)
        return sorted(timed_out)

    def _reap(self, key: str) -> None:
        self.requests[key] = [
            r for r in self.requests.get(key, []) if not r.completed
        ]
        if not self.requests[key]:
            del self.requests[key]

    def pending(self) -> int:
        return sum(len(v) for v in self.requests.values())

    def report(self) -> str:
        return (
            f"{self.completed_by_event} completed by event, "
            f"{self.completed_by_timeout} by timeout, "
            f"{self.pending()} pending; a purgatory that mostly "
            "times out has unmet conditions, not slow ones"
        )
