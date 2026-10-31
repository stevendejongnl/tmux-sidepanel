"""The whole panel: the sections of the configuration, in order, built from a snapshot."""

from collections.abc import Callable
from dataclasses import dataclass

from tmux_sidepanel.configuration import AgentSettings, Configuration, Section
from tmux_sidepanel.custom_rows import build_custom_section
from tmux_sidepanel.pane_rows import build_pane_section, build_subagent_section
from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.rows import PanelView, SectionView
from tmux_sidepanel.service_rows import build_other_service_section, build_service_section
from tmux_sidepanel.snapshot import Snapshot
from tmux_sidepanel.terminal_text import sanitize_for_terminal
from tmux_sidepanel.zombie_rows import build_zombie_section

SectionBuilder = Callable[[Section, Snapshot, AgentSettings], SectionView]


def build_other_services(
    section: Section, snapshot: Snapshot, agents: AgentSettings
) -> SectionView:
    return build_other_service_section(section, snapshot)


def build_custom(section: Section, snapshot: Snapshot, agents: AgentSettings) -> SectionView:
    return build_custom_section(section, snapshot)


SECTION_BUILDERS: dict[str, SectionBuilder] = {
    "panes": build_pane_section,
    "subagents": build_subagent_section,
    "services": build_service_section,
    "other-services": build_other_services,
    "zombies": build_zombie_section,
    "custom": build_custom,
}


@dataclass(frozen=True)
class BuiltSection:
    section: Section
    view: SectionView

    def is_shown(self) -> bool:
        return not (self.section.hide_when_empty and self.view.is_empty)


def build_section(section: Section, snapshot: Snapshot, agents: AgentSettings) -> BuiltSection:
    view = SECTION_BUILDERS[section.section_type](section, snapshot, agents)
    return BuiltSection(section, view)


def without_home(directory: str, home: str) -> str:
    """The directory with a tilde for the home directory, for a person to read."""
    is_inside_home = home and (directory == home or directory.startswith(f"{home}/"))
    return f"~{directory.removeprefix(home)}" if is_inside_home else directory


def is_pane_in_use(pane: PaneRecord, window_identifier: str) -> bool:
    return pane.is_not_panel() and pane.window_identifier == window_identifier


def panel_directory(snapshot: Snapshot) -> str:
    """The directory of the pane in use: the panel itself can have the focus, so it never counts."""
    panes = filter(lambda item: is_pane_in_use(item, snapshot.window_identifier), snapshot.panes)
    pane = min(panes, key=lambda item: (not item.is_active, not item.is_last), default=None)
    directory = without_home(pane.current_directory, snapshot.home_directory) if pane else ""
    return sanitize_for_terminal(directory)


def build_panel(configuration: Configuration, snapshot: Snapshot) -> PanelView:
    """The enabled sections in the order of the configuration, without empty ones that hide."""
    enabled = filter(lambda section: section.enabled, configuration.sections)
    built = [build_section(section, snapshot, configuration.agents) for section in enabled]
    shown = tuple(item.view for item in filter(BuiltSection.is_shown, built))
    return PanelView(shown, panel_directory(snapshot))
