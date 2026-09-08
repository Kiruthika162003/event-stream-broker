"""The error family: every refusal in this broker descends from one name."""

from __future__ import annotations


class RelayError(Exception):
    """Base for everything this broker refuses to do."""


class Invalid(RelayError):
    """The request contradicts itself or the configuration."""


class Missing(RelayError):
    """The thing addressed does not exist."""


class Sealed(RelayError):
    """The target is closed to further writes."""


class Fenced(RelayError):
    """A stale writer tried to act after losing its claim."""


class Lagging(RelayError):
    """The reader has fallen off the retained window."""
