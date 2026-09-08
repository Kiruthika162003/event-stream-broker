"""Produce errors: retriable or fatal, because retrying a fatal one loops.

When a produce fails, the client's next move depends entirely on
whether the error is retriable, and a client that guesses wrong
either gives up on a transient failure or loops forever on a
permanent one. The classifier sorts produce errors into three
responses. Retriable errors are transient conditions the same
request may succeed against later: a not-leader error the client
retries after refreshing metadata, a request-timeout it retries
because the write may or may not have landed, a not-enough-
replicas it retries because the in-sync set may recover. Fatal
errors are permanent for this request and retrying cannot help: a
message-too-large will always be too large, an authorization-
failed will always be denied, a serialization error is the
client's own bug. The third and most dangerous class is the
ambiguous error, where the write may have succeeded but the
acknowledgement was lost, and here the retry decision depends on
idempotence: with idempotence a retry is safe because the broker
dedups it, without it a retry may duplicate, so the classifier
refuses to call an ambiguous error blindly retriable and instead
routes on whether the producer is idempotent. The classifier
names the response and the reason, because a client that gets
retry-this without knowing why cannot decide how long to back
off, and a fatal error mislabeled retriable is the infinite loop
that looks like a slow producer, the worst failure because it
generates load while making no progress.
"""

from __future__ import annotations

from relay.errors import Invalid

RETRIABLE = {
    "not-leader",
    "request-timeout",
    "not-enough-replicas",
    "coordinator-loading",
}
FATAL = {
    "message-too-large",
    "authorization-failed",
    "serialization-error",
    "invalid-topic",
}
AMBIGUOUS = {"ack-lost"}


def classify(error: str, idempotent: bool) -> str:
    if error in RETRIABLE:
        return (
            f"retriable ({error}): a transient condition the same "
            "request may succeed against after a backoff"
        )
    if error in FATAL:
        return (
            f"fatal ({error}): permanent for this request, and "
            "retrying cannot help, so do not loop"
        )
    if error in AMBIGUOUS:
        if idempotent:
            return (
                f"retriable ({error}): the ack was lost but "
                "idempotence dedups a retry, so it is safe"
            )
        return (
            f"fatal without idempotence ({error}): the write may "
            "have landed, and a retry could duplicate; enable "
            "idempotence to make this retriable"
        )
    raise Invalid(f"unknown produce error {error}")


def should_retry(error: str, idempotent: bool) -> bool:
    verdict = classify(error, idempotent)
    return verdict.startswith("retriable")
