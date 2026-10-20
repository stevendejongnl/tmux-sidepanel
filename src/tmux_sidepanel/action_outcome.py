"""What an action gives back, and what it needs to run.

An action either finishes and has something to say, or it asks the user to confirm first. A
destructive action never runs before the confirmation: it returns the prompt and the function
that does the work, and the caller runs that function only after a yes.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from tmux_sidepanel.process_table import PROCESS_LIST_COMMAND
from tmux_sidepanel.tmux_client import TmuxClient


@dataclass(frozen=True)
class ActionOutcome:
    notice: str = ""
    prompt: str = ""  # when set, the user must confirm before anything happens
    confirmed: Callable[[], "ActionOutcome"] | None = None


@dataclass(frozen=True)
class ActionContext:
    client: TmuxClient
    docker_program: str = "docker"
    agent_names: tuple[str, ...] = ("claude",)
    process_command: Sequence[str] = PROCESS_LIST_COMMAND


def done(notice: str = "") -> ActionOutcome:
    return ActionOutcome(notice=notice)


def ask(prompt: str, then: Callable[[], ActionOutcome]) -> ActionOutcome:
    return ActionOutcome(prompt=prompt, confirmed=then)
