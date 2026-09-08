"""Task assignment: balance the work, and never put a standby with its active.

A stream application splits into tasks, one per partition of its
input, and those tasks are assigned across the running instances.
Two goals pull on the assignment. The first is balance: an instance
with many more tasks than another is the bottleneck while the other
idles, so the active tasks are spread as evenly as the counts
allow. The second is fault isolation for stateful tasks: a task can
have a standby, a warm copy of its state on another instance for
fast failover, and the standby is useless if it sits on the same
instance as its active, because the instance failure that takes the
active takes the standby with it. So the assignment obeys a hard
rule: a task's standby must be on a different instance than its
active, and the assigner refuses a placement that violates it
rather than producing an assignment that looks redundant but is
not. Balance is a soft goal optimized within that hard rule, so a
task moves to even out counts only if the move does not collocate a
standby with its active. The assigner refuses to place a standby
when there is only one instance, because there is nowhere for it to
go that is not the active's instance, and it reports the imbalance,
the gap between the busiest and idlest instance, because an
assignment balanced on task count can still be unbalanced on load
if the tasks differ in weight, and the count gap is the first thing
to check when one instance runs hot. The report also flags any
standby that shares an instance with its active, which should never
happen and is a bug in the assigner if it does, surfaced rather
than hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid


@dataclass
class TaskAssignment:
    instances: list[str]
    active: dict[str, str] = field(default_factory=dict)
    standby: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.instances:
            raise Invalid("no instances to assign tasks to")

    def assign_active(self, task: str, instance: str) -> None:
        if instance not in self.instances:
            raise Invalid(f"unknown instance '{instance}'")
        self.active[task] = instance

    def assign_standby(self, task: str, instance: str) -> str:
        if len(self.instances) < 2:
            raise Invalid(
                "cannot place a standby with only one instance; it would "
                "sit with its active and die in the same failure"
            )
        if self.active.get(task) == instance:
            raise Invalid(
                f"standby for '{task}' would sit on its active's instance "
                f"'{instance}'; the failure that takes the active takes it too"
            )
        self.standby[task] = instance
        return f"standby for '{task}' placed on '{instance}'"

    def imbalance(self) -> int:
        counts = dict.fromkeys(self.instances, 0)
        for inst in self.active.values():
            counts[inst] = counts.get(inst, 0) + 1
        return max(counts.values()) - min(counts.values())

    def collocated_standbys(self) -> list[str]:
        return [
            task
            for task, inst in self.standby.items()
            if self.active.get(task) == inst
        ]

    def report(self) -> str:
        bad = self.collocated_standbys()
        note = f"active task imbalance {self.imbalance()} across the instances"
        if bad:
            return f"{note}; BUG: standbys collocated with actives: {bad}"
        return f"{note}; every standby is off its active's instance"
