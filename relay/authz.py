"""Authorization: deny by default, grant explicitly, and log the deny.

A broker without authorization is a broker where any client can
read any topic, which is fine until the topic holds payroll and
the client is an intern's laptop. The model is deny by default:
a principal may perform an operation on a resource only if a
grant says so, and the absence of a grant is a denial, never a
gap that fails open. Grants are positive only in the common
case, but explicit denies exist and outrank grants, because the
real-world rule is usually allow-the-team-except-this-one, and
a model without deny forces that into a tangle of narrow
grants that drift out of sync. Wildcards are allowed on
resource names so a grant can cover a topic prefix, but a
wildcard deny is evaluated before any grant, keeping the
principle that the most specific protection wins. Every denied
request is recorded with principal, operation, and resource,
because an authorization layer that cannot say who was denied
what is a layer that cannot be audited, and an unauditable
security control is decoration.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from relay.errors import Invalid

OPERATIONS = ("read", "write", "create", "delete", "describe")


@dataclass(frozen=True)
class Rule:
    principal: str
    operation: str
    resource: str
    allow: bool

    def matches(
        self, principal: str, operation: str, resource: str
    ) -> bool:
        return (
            self._match(self.principal, principal)
            and self.operation in (operation, "*")
            and self._resource_match(resource)
        )

    def _resource_match(self, resource: str) -> bool:
        if self.resource.endswith("*"):
            return resource.startswith(self.resource[:-1])
        return self.resource == resource

    @staticmethod
    def _match(pattern: str, value: str) -> bool:
        return pattern in (value, "*")


@dataclass
class Authorizer:
    rules: list[Rule] = field(default_factory=list)
    denials_logged: list[str] = field(default_factory=list)

    def grant(
        self, principal: str, operation: str, resource: str
    ) -> None:
        self._add(principal, operation, resource, allow=True)

    def deny(
        self, principal: str, operation: str, resource: str
    ) -> None:
        self._add(principal, operation, resource, allow=False)

    def _add(
        self,
        principal: str,
        operation: str,
        resource: str,
        allow: bool,
    ) -> None:
        if operation not in (*OPERATIONS, "*"):
            raise Invalid(f"unknown operation {operation}")
        self.rules.append(
            Rule(principal, operation, resource, allow)
        )

    def allowed(
        self, principal: str, operation: str, resource: str
    ) -> bool:
        matching = [
            rule
            for rule in self.rules
            if rule.matches(principal, operation, resource)
        ]
        if any(not rule.allow for rule in matching):
            self._log_denial(principal, operation, resource)
            return False
        if any(rule.allow for rule in matching):
            return True
        self._log_denial(principal, operation, resource)
        return False

    def _log_denial(
        self, principal: str, operation: str, resource: str
    ) -> None:
        self.denials_logged.append(
            f"{principal} denied {operation} on {resource}"
        )

    def authorize(
        self, principal: str, operation: str, resource: str
    ) -> str:
        if self.allowed(principal, operation, resource):
            return f"{principal} may {operation} {resource}"
        raise Invalid(
            f"{principal} denied {operation} on {resource}; "
            "deny by default, and this denial is on the audit "
            "log where a security control's denials must live"
        )
