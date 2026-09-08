"""SASL handshake: prove who you are before the connection carries a request.

Authentication happens once per connection, before any produce or
fetch, and it is a small state machine that must complete in order:
the client asks which mechanisms the broker supports, picks one the
broker has enabled, and then exchanges challenge and response
messages until the mechanism declares success or failure. The order
is the security: a connection that has not completed the handshake
must not carry a request, because a request accepted before
authentication is a request from an unauthenticated peer, so the
machine refuses application traffic in every state but complete.
The mechanism choice is negotiated, not assumed: the client must
choose from the mechanisms the broker enabled, and choosing one the
broker does not offer is rejected rather than silently downgraded,
because a silent downgrade to a weaker mechanism is how an attacker
strips authentication. The exchange can take several rounds, one
for a simple password mechanism and more for a challenge-response
one, so the machine counts rounds and lets the mechanism decide
when it is done rather than fixing a round count that would break a
multi-round mechanism. The machine refuses to advance past a failed
authentication, because a failure is terminal for the connection
and a client retrying on the same connection after a failure is
either confused or probing. It also refuses to begin a second
handshake on a connection already authenticated, because re-
authentication mid-connection is a separate flow and treating a new
handshake as if it replaced the identity would let a connection
change who it is after it started sending requests.
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Fenced, Invalid

START = "start"
CHOSEN = "chosen"
AUTHENTICATING = "authenticating"
COMPLETE = "complete"
FAILED = "failed"


@dataclass
class SaslHandshake:
    enabled_mechanisms: tuple[str, ...]
    state: str = START
    mechanism: str = ""
    rounds: int = 0

    def choose(self, mechanism: str) -> str:
        if self.state == COMPLETE:
            raise Fenced(
                "this connection is already authenticated; a second "
                "handshake must not silently change who it is"
            )
        if mechanism not in self.enabled_mechanisms:
            raise Invalid(
                f"mechanism '{mechanism}' is not enabled; refusing "
                "rather than downgrading, because a silent downgrade "
                "strips authentication"
            )
        self.mechanism = mechanism
        self.state = CHOSEN
        return f"chose {mechanism} from {list(self.enabled_mechanisms)}"

    def exchange(self, done: bool, ok: bool = True) -> str:
        if self.state not in (CHOSEN, AUTHENTICATING):
            raise Invalid(
                f"cannot exchange in state '{self.state}'; choose a "
                "mechanism first"
            )
        self.rounds += 1
        if not done:
            self.state = AUTHENTICATING
            return f"round {self.rounds}, more to go"
        self.state = COMPLETE if ok else FAILED
        return f"authentication {self.state} after {self.rounds} round(s)"

    def may_serve(self, request: str) -> str:
        if self.state != COMPLETE:
            raise Invalid(
                f"'{request}' refused: the handshake is '{self.state}', "
                "not complete; an unauthenticated peer sends nothing"
            )
        return f"'{request}' authorized to proceed"
