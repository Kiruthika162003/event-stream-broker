"""Group type: members of one group must all be the same kind of thing.

A group id is just a string, and different kinds of clients use
groups, a consumer group for plain consumers, a connect group for
connector workers, a group for a custom application built on the
group protocol, and nothing stops two different kinds from picking
the same group id by accident. That would be a disaster: the group
protocol distributes work by having members agree on an assignment,
and a consumer and a connector worker do not speak the same
assignment language, so a group mixing them would hand a consumer
an assignment it cannot honor and a connector a partition list that
means nothing to it. The protocol type prevents it: a group takes
its type from its first member, and every later member must present
the same type or be rejected, so a group is homogeneous, all
consumers or all connect workers, and a client that joined the
wrong group id fails loudly instead of corrupting the group's
coordination. An empty group, one whose members have all left, has
no type and can be re-typed by the next member to join, because
there is no one left whose coordination a re-type would break, which
is what lets a group id be reused for a different purpose once it is
truly empty. The registry types a group on its first member,
rejects a join whose protocol type differs from the group's naming
both, and clears the type when the group empties. It reports the
group's type so an operator seeing a rejected join can tell whether
the client is the wrong kind for this group id, a configuration
mistake, rather than a transient error, because the two look alike
from the client's failed join but need different fixes."
"""

from __future__ import annotations

from dataclasses import dataclass

from relay.errors import Invalid


@dataclass
class GroupTypeRegistry:
    protocol_type: str = ""
    members: int = 0

    def join(self, member_type: str) -> str:
        if not member_type:
            raise Invalid("a member must declare a protocol type")
        if self.members == 0:
            self.protocol_type = member_type
            self.members = 1
            return f"group typed as '{member_type}' by its first member"
        if member_type != self.protocol_type:
            raise Invalid(
                f"member is '{member_type}' but the group is "
                f"'{self.protocol_type}'; a client that joined the wrong "
                "group id, not a transient error"
            )
        self.members += 1
        return f"joined as '{member_type}'; the group stays homogeneous"

    def leave(self) -> str:
        if self.members > 0:
            self.members -= 1
        if self.members == 0:
            self.protocol_type = ""
            return "group empty; type cleared, the id can be reused for another kind"
        return f"member left; {self.members} remaining, still '{self.protocol_type}'"

    def current_type(self) -> str:
        if self.members == 0:
            return "untyped (empty); the next member sets the type"
        return f"'{self.protocol_type}' with {self.members} member(s)"
