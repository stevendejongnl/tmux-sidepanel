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
    description: str = ""  # one word, as stored: spaces are underscores

    @property
    def label(self) -> str:
        what = self.description.replace("_", " ") or self.identifier[:6]
        return f"{self.kind} {what}"

    @property
    def entry(self) -> str:
        parts = (self.identifier, self.kind, self.description)
        return ":".join(filter(None, parts))

    def has_identifier(self) -> bool:
        return bool(self.identifier)


def format_subagents(subagents: Iterable[Subagent]) -> str:
    """Write 'identifier:kind' entries separated by a space, the inverse of parse_subagents."""
    return " ".join(subagent.entry for subagent in subagents)


def parse_subagent(entry: str) -> Subagent:
    identifier, kind, description = (entry.split(":", 2) + ["", ""])[:3]
    return Subagent(identifier, kind or "agent", description)


def parse_subagents(value: str) -> list[Subagent]:
    """Read 'identifier:kind' or 'identifier:kind:description' entries. No kind is 'agent'."""
    subagents = map(parse_subagent, value.split())
    return list(filter(Subagent.has_identifier, subagents))
