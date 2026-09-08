"""Interceptors: a transform chain that declares what it does to the stream.

Producers and consumers hang interceptors on the record path to
add tracing headers, redact fields, collect metrics, and the
chain is convenient and dangerous in equal measure, because an
interceptor can quietly change delivery semantics. An
interceptor that drops a record turns at-least-once into
maybe-once for everything downstream; one that reorders breaks
the per-partition order the whole broker guarantees; one that
throws and is swallowed makes a metrics bug into silent data
loss. The chain here forces each interceptor to declare its
kind, transform, filter, or observe, and enforces the
declaration: an observe interceptor that returns a changed
record is refused, a transform that returns None is refused
because dropping is the filter's job and a transform that drops
is lying about its kind, and a filter's drops are counted so
maybe-once is a number on a dashboard rather than a mystery in
production. Exceptions are never swallowed: an interceptor that
throws fails the record loudly, because a transform chain that
eats its own errors is how a redaction bug ships PII for a month.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from relay.errors import Invalid

TRANSFORM = "transform"
FILTER = "filter"
OBSERVE = "observe"
KINDS = (TRANSFORM, FILTER, OBSERVE)


@dataclass
class Interceptor:
    name: str
    kind: str
    fn: Callable[[bytes], bytes | None]

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise Invalid(f"unknown interceptor kind {self.kind}")


@dataclass
class InterceptorChain:
    interceptors: list[Interceptor] = field(default_factory=list)
    dropped: int = 0

    def add(self, interceptor: Interceptor) -> None:
        self.interceptors.append(interceptor)

    def run(self, record: bytes) -> bytes | None:
        current = record
        for interceptor in self.interceptors:
            try:
                result = interceptor.fn(current)
            except Exception as exc:
                raise Invalid(
                    f"{interceptor.name} threw; a swallowed "
                    "exception here is how a redaction bug ships "
                    f"PII for a month: {exc}"
                ) from exc
            if interceptor.kind == OBSERVE:
                if result is not None and result != current:
                    raise Invalid(
                        f"{interceptor.name} declared observe but "
                        "changed the record; observe reads, it "
                        "does not write"
                    )
                continue
            if interceptor.kind == TRANSFORM:
                if result is None:
                    raise Invalid(
                        f"{interceptor.name} declared transform "
                        "but dropped the record; dropping is the "
                        "filter's job, and a transform that drops "
                        "lies about its kind"
                    )
                current = result
                continue
            if result is None:
                self.dropped += 1
                return None
            current = result
        return current

    def drop_report(self) -> str:
        return (
            f"{self.dropped} record(s) filtered out; maybe-once "
            "as a number on a dashboard, not a mystery in "
            "production"
        )
