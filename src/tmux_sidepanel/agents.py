"""Agent states, and the subagent entries that hooks store on a pane."""

from collections.abc import Iterable
from dataclasses import dataclass

# How urgent a state is. Unknown counts like idle: something runs, but nothing needs you.
STATE_URGENCY = {"": 0, "idle": 1, "unknown": 1, "working": 2, "done": 3, "blocked": 4}


def urgency(state: str) -> int:
    """Rank a state. A name that is not a state ranks 0, the same as no agent."""
    return STATE_URGENCY.get(state, 0)


def most_urgent_state(states: Iterable[str]) -> str:
    """Roll several states up into the most urgent one. The first of equal states wins."""
    candidate = max(states, key=urgency, default="")
    return candidate if urgency(candidate) > 0 else ""


@dataclass(frozen=True)
class Subagent:
    identifier: str
    kind: str

    @property
    def label(self) -> str:
        return f"{self.kind} {self.identifier[:6]}"

    def has_identifier(self) -> bool:
        return bool(self.identifier)


def parse_subagent(entry: str) -> Subagent:
    identifier = entry.split(":")[0]
    kind = entry.partition(":")[2] or "agent"
    return Subagent(identifier, kind)


def parse_subagents(value: str) -> list[Subagent]:
    """Read 'identifier:kind' entries. A missing kind becomes 'agent'."""
    subagents = map(parse_subagent, value.split())
    return list(filter(Subagent.has_identifier, subagents))
