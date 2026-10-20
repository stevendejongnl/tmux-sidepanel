"""Roll-ups: the most urgent state of a window or session, and panes whose agent is gone."""

from collections.abc import Callable, Collection, Iterable
from itertools import groupby
from operator import attrgetter

from tmux_sidepanel.agents import most_urgent_state
from tmux_sidepanel.panes import PaneRecord


def regular_states(members: Iterable[PaneRecord]) -> list[str]:
    return [pane.agent_state for pane in filter(PaneRecord.is_not_panel, members)]


def states_by(panes: Iterable[PaneRecord], key_of: Callable[[PaneRecord], str]) -> dict[str, str]:
    """The most urgent state per key. A key without an agent still appears, with no state."""
    ordered = sorted(panes, key=key_of)
    return {
        key: most_urgent_state(regular_states(members))
        for key, members in groupby(ordered, key=key_of)
    }


def window_states(panes: Iterable[PaneRecord]) -> dict[str, str]:
    return states_by(panes, attrgetter("window_identifier"))


def session_states(panes: Iterable[PaneRecord]) -> dict[str, str]:
    return states_by(panes, attrgetter("session_identifier"))


def stale_agent_panes(
    panes: Iterable[PaneRecord], agent_names: Collection[str]
) -> list[PaneRecord]:
    """Panes that still carry an agent state although the agent no longer runs in them."""
    with_state = filter(PaneRecord.has_agent_state, filter(PaneRecord.is_not_panel, panes))
    return list(filter(lambda pane: pane.current_command not in agent_names, with_state))
