"""Action menus: which actions a row offers, with the keys and the choices of the configuration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from tmux_sidepanel.configuration import Section
from tmux_sidepanel.custom_rows import CustomSubject
from tmux_sidepanel.pane_rows import PaneSubject, SubagentSubject
from tmux_sidepanel.service_rows import ServiceSubject
from tmux_sidepanel.zombie_rows import ZombieSubject

ACTION_LABELS = {
    "go": "go to pane",
    "zoom": "zoom pane",
    "interrupt": "interrupt (Ctrl-C)",
    "directory": "open directory in new window",
    "close": "close pane (kill)",
    "tasks": "open in /tasks",
    "stop": "stop (graceful)",
    "restart": "restart",
    "logs": "logs in new window",
    "kill": "kill (force)",
    "open": "open (jump or resume in new window)",
    "terminate": "terminate (SIGTERM)",
}


@dataclass(frozen=True)
class MenuItem:
    key: str
    label: str
    action: str


def when(condition: Any, names: set[str]) -> set[str]:
    return set(names) if condition else set()


def pane_actions(subject: PaneSubject) -> set[str]:
    base = {"go", "zoom", "interrupt", "close"}
    return base | when(subject.pane.current_directory, {"directory"})


def subagent_actions(subject: SubagentSubject) -> set[str]:
    return {"go", "tasks"}


def service_actions(subject: ServiceSubject) -> set[str]:
    entry = subject.entry
    return (
        {"stop", "kill"}
        | when(entry.pane_identifier, {"go"})
        | when(entry.is_container, {"restart", "logs"})
        | when(entry.directory, {"directory"})
    )


def zombie_actions(subject: ZombieSubject) -> set[str]:
    can_signal = subject.zombie.reason != "defunct"
    return when(can_signal, {"open", "terminate", "kill"}) | when(subject.directory, {"directory"})


def custom_actions(subject: CustomSubject) -> set[str]:
    return set()


AVAILABLE_ACTIONS: dict[type, Callable[[Any], set[str]]] = {
    PaneSubject: pane_actions,
    SubagentSubject: subagent_actions,
    ServiceSubject: service_actions,
    ZombieSubject: zombie_actions,
    CustomSubject: custom_actions,
}


def pane_label_overrides(subject: PaneSubject) -> dict[str, str]:
    return {"interrupt": "interrupt (Esc)"} if subject.state else {}


def zombie_label_overrides(subject: ZombieSubject) -> dict[str, str]:
    return {"kill": "kill (SIGKILL)"}


def no_label_overrides(subject: Any) -> dict[str, str]:
    return {}


LABEL_OVERRIDES: dict[type, Callable[[Any], dict[str, str]]] = {
    PaneSubject: pane_label_overrides,
    ZombieSubject: zombie_label_overrides,
}


def label_for(action: str, subject: Any) -> str:
    overrides = LABEL_OVERRIDES.get(type(subject), no_label_overrides)(subject)
    return overrides.get(action, ACTION_LABELS[action])


def menu_items(section: Section, subject: Any) -> list[MenuItem]:
    """The menu of a row, in the order of the keys of the section."""
    available = AVAILABLE_ACTIONS[type(subject)](subject)
    disabled = section.menu.disabled_actions
    offered = filter(
        lambda action: action in available and action not in disabled, section.menu.keys
    )
    return [
        MenuItem(section.menu.keys[action], label_for(action, subject), action)
        for action in offered
    ]
