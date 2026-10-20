"""Builders for test data: a complete default record that a test changes in one or two fields."""

from dataclasses import replace

from tmux_sidepanel.panes import PaneRecord

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
    is_panel=False,
)


def build_pane_record(**overrides):
    return replace(DEFAULT_PANE_RECORD, **overrides)
