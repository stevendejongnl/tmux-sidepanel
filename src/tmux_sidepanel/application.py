"""The application: what the panel of one window collects, shows and runs."""

from dataclasses import dataclass
from typing import Any

from tmux_sidepanel.action_outcome import ActionContext, ActionOutcome
from tmux_sidepanel.actions import perform_action
from tmux_sidepanel.collector import Collector, collect_snapshot
from tmux_sidepanel.configuration import Configuration
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.interface_state import Performer
from tmux_sidepanel.panel import build_panel
from tmux_sidepanel.rows import PanelView
from tmux_sidepanel.tmux_client import TmuxClient


@dataclass(frozen=True)
class Application:
    client: TmuxClient
    configuration: Configuration
    window_identifier: str
    collector: Collector
    action_context: ActionContext


def window_of_pane(client: TmuxClient, pane_identifier: str) -> str:
    pane = find_pane(client.list_panes(), pane_identifier)
    return pane.window_identifier if pane else ""


def build_application(
    client: TmuxClient, configuration: Configuration, pane_identifier: str
) -> Application:
    """The application of the window that holds the panel pane."""
    return Application(
        client=client,
        configuration=configuration,
        window_identifier=window_of_pane(client, pane_identifier),
        collector=Collector(client),
        action_context=ActionContext(client, agent_names=configuration.agents.names),
    )


def current_panel(application: Application) -> PanelView:
    snapshot = collect_snapshot(
        application.collector, application.configuration, application.window_identifier
    )
    return build_panel(application.configuration, snapshot)


def perform_for(application: Application) -> Performer:
    def perform(subject: Any, action: str) -> ActionOutcome:
        return perform_action(application.action_context, subject, action)

    return perform
