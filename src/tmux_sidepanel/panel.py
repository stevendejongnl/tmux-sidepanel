"""The whole panel: the sections of the configuration, in order, built from a snapshot."""

from collections.abc import Callable
from dataclasses import dataclass

from tmux_sidepanel.configuration import AgentSettings, Configuration, Section
from tmux_sidepanel.custom_rows import build_custom_section
from tmux_sidepanel.pane_rows import build_pane_section, build_subagent_section
from tmux_sidepanel.rows import PanelView, SectionView
from tmux_sidepanel.service_rows import build_other_service_section, build_service_section
from tmux_sidepanel.snapshot import Snapshot
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


def build_panel(configuration: Configuration, snapshot: Snapshot) -> PanelView:
    """The enabled sections in the order of the configuration, without empty ones that hide."""
    enabled = filter(lambda section: section.enabled, configuration.sections)
    built = [build_section(section, snapshot, configuration.agents) for section in enabled]
    return PanelView(tuple(item.view for item in filter(BuiltSection.is_shown, built)))
