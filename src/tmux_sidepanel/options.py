"""The tmux user options this plugin sets, in one place so every module spells them the same."""

OPTION_STATE = "@sidepanel_state"
OPTION_KIND = "@sidepanel_kind"
OPTION_NAME = "@sidepanel_name"
OPTION_SUBAGENTS = "@sidepanel_subagents"
OPTION_PANEL = "@sidepanel_panel"
OPTION_WINDOW_STATE = "@sidepanel_window_state"
OPTION_SESSION_STATE = "@sidepanel_session_state"


def option_expression(option: str) -> str:
    """The tmux format expression that reads an option: '@name' becomes '#{@name}'."""
    return "#{" + option + "}"
