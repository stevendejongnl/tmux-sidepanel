"""Builders for test data: a complete default record that a test changes in one or two fields."""

from dataclasses import replace

from tmux_sidepanel.configuration import default_configuration
from tmux_sidepanel.containers import Container
from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.processes import Process

DEFAULT_PANE_RECORD = PaneRecord(
    session_name="main",
    session_identifier="$1",
    window_identifier="@1",
    window_index=1,
    window_name="project",
    pane_identifier="%1",
    pane_index=1,
    terminal="pts/1",
    current_command="zsh",
    current_directory="/home/someone/project",
    is_active=True,
    is_window_active=True,
    is_session_attached=True,
    agent_state="",
    agent_kind="",
    agent_name="",
    agent_subagents="",
    agent_tasks="",
    is_panel=False,
    is_last=False,
)


def build_pane_record(**overrides):
    return replace(DEFAULT_PANE_RECORD, **overrides)


def section_named(identifier):
    """A section of the default configuration, for example 'panes' or 'zombies'."""
    sections = default_configuration().sections
    return next(filter(lambda section: section.identifier == identifier, sections))


def build_process(
    identifier,
    arguments="/opt/bin/claude",
    parent=1,
    terminal="?",
    status_flags="Sl",
    age_seconds=10,
):
    return Process(
        process_identifier=identifier,
        parent_process_identifier=parent,
        terminal=terminal,
        status_flags=status_flags,
        age_seconds=age_seconds,
        arguments=arguments,
    )


def build_container(name="app-1", status="Up 6 hours", directory="", project="", service=""):
    return Container(name, status, service, directory, project)
