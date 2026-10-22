"""The sections of the panel that list the panes of a window and the subagents of its agents."""

from tests.builders import build_pane_record, section_named
from tmux_sidepanel.configuration import AgentSettings
from tmux_sidepanel.pane_rows import (
    PaneSubject,
    SubagentSubject,
    build_pane_section,
    build_subagent_section,
    effective_state,
)
from tmux_sidepanel.snapshot import Snapshot

AGENTS = AgentSettings()
WINDOW = "@1"


def snapshot_of(*panes):
    return Snapshot(panes=list(panes), window_identifier=WINDOW)


def pane_view(*panes):
    return build_pane_section(section_named("panes"), snapshot_of(*panes), AGENTS)


def subagent_view(*panes):
    return build_subagent_section(section_named("subagents"), snapshot_of(*panes), AGENTS)


def agent_pane(**overrides):
    values = {
        "current_command": "claude",
        "agent_state": "working",
        "agent_kind": "claude",
        "current_directory": "/home/someone/project",
        **overrides,
    }
    return build_pane_record(**values)


def texts(view):
    return [row.text for row in view.rows]


class TestEffectiveState:
    def test_the_state_of_a_pane_that_runs_the_agent(self):
        assert effective_state(agent_pane(agent_state="blocked"), AGENTS) == "blocked"

    def test_a_state_without_the_agent_is_stale_and_ignored(self):
        pane = agent_pane(current_command="zsh")
        assert effective_state(pane, AGENTS) == ""

    def test_an_agent_without_a_state_is_unknown(self):
        pane = agent_pane(agent_state="")
        assert effective_state(pane, AGENTS) == "unknown"

    def test_a_plain_pane_has_no_state(self):
        assert effective_state(build_pane_record(current_command="zsh"), AGENTS) == ""

    def test_the_agent_names_come_from_the_settings(self):
        pane = agent_pane(current_command="codex", agent_state="")
        assert effective_state(pane, AgentSettings(names=("codex",))) == "unknown"


class TestPaneSection:
    def test_copies_the_title_and_empty_text_of_the_section(self):
        view = pane_view()
        assert (view.identifier, view.title, view.empty_text) == ("panes", "PANES", "none")
        assert view.is_empty

    def test_lists_only_the_panes_of_the_window(self):
        other_window = build_pane_record(window_identifier="@2", current_command="vim")
        mine = build_pane_record(current_command="zsh")
        assert texts(pane_view(other_window, mine)) == ["zsh project"]

    def test_orders_the_panes_by_their_index(self):
        second = build_pane_record(pane_index=2, current_command="vim")
        first = build_pane_record(pane_index=1, current_command="zsh")
        assert texts(pane_view(second, first)) == ["zsh project", "vim project"]

    def test_leaves_out_the_panel_itself(self):
        panel = build_pane_record(is_panel=True, current_command="python3")
        assert pane_view(panel).rows == ()

    def test_a_plain_pane_shows_its_program_and_folder(self):
        assert texts(pane_view(build_pane_record(current_command="zsh"))) == ["zsh project"]

    def test_the_folder_is_left_out_when_it_repeats_the_name(self):
        pane = build_pane_record(current_command="project", current_directory="/x/project")
        assert texts(pane_view(pane)) == ["project"]

    def test_an_agent_shows_its_state_mark_and_kind(self):
        assert texts(pane_view(agent_pane(agent_state="blocked"))) == ["! claude project"]

    def test_a_name_beats_the_kind(self):
        assert texts(pane_view(agent_pane(agent_name="reviewer"))) == ["~ reviewer project"]

    def test_an_agent_without_a_state_shows_the_unknown_mark(self):
        assert texts(pane_view(agent_pane(agent_state="", agent_kind=""))) == ["? claude project"]

    def test_running_subagents_are_counted(self):
        pane = agent_pane(agent_subagents="aaa111:Explore bbb222:agent")
        assert texts(pane_view(pane)) == ["~ claude project (+2 sub)"]

    def test_a_stale_pane_loses_its_subagent_count_and_state(self):
        pane = agent_pane(current_command="zsh", agent_subagents="aaa111:Explore")
        assert texts(pane_view(pane)) == ["zsh project"]

    def test_the_active_pane_is_marked(self):
        active = build_pane_record(pane_index=1, is_active=True)
        other = build_pane_record(pane_index=2, is_active=False)
        assert [row.is_active for row in pane_view(active, other).rows] == [True, False]

    def test_the_row_remembers_its_pane_and_state(self):
        pane = agent_pane(agent_state="done")
        row = pane_view(pane).rows[0]
        assert row.state == "done"
        assert row.subject == PaneSubject(pane, "done")

    def test_a_row_format_of_the_configuration_is_used(self):
        section = section_named("panes")
        custom = type(section)(**{**section.__dict__, "row_format": "{state}:{command}"})
        view = build_pane_section(custom, snapshot_of(agent_pane()), AGENTS)
        assert texts(view) == ["working:claude"]

    def test_hostile_text_in_a_command_cannot_reach_the_terminal(self):
        pane = build_pane_record(current_command="evil\x1b]0;x\x07")
        assert "\x1b" not in texts(pane_view(pane))[0]


class TestSubagentSection:
    def test_lists_the_subagents_of_the_agents_of_the_window(self):
        pane = agent_pane(agent_subagents="a7d3bd68dc2e:Explore bbb222ccc333:general-purpose")
        assert texts(subagent_view(pane)) == [
            "~ Explore a7d3bd",
            "~ general-purpose bbb222",
        ]

    def test_lists_the_background_tasks_after_the_subagents(self):
        pane = agent_pane(
            agent_subagents="aaa111bbb:Explore", agent_tasks="bvz0tq:shell:Run_sleep_25 c1:cron"
        )
        assert texts(subagent_view(pane)) == [
            "~ Explore aaa111",
            "~ shell Run sleep 25",
            "~ cron c1",
        ]

    def test_a_tool_row_shows_the_tool_and_what_it_works_on(self):
        pane = agent_pane(agent_tasks="toolu_01:tool:Edit_export.py")
        assert texts(subagent_view(pane)) == ["~ tool Edit export.py"]

    def test_an_error_row_is_marked_as_blocked(self):
        pane = agent_pane(agent_state="blocked", agent_tasks="failure:error:rate_limit")
        view = subagent_view(pane)
        assert texts(view) == ["! error rate limit"]
        assert view.rows[0].state == "blocked"

    def test_a_stale_pane_has_no_background_tasks(self):
        pane = agent_pane(current_command="zsh", agent_tasks="bvz0tq:shell")
        assert subagent_view(pane).rows == ()

    def test_other_windows_are_left_out(self):
        pane = agent_pane(window_identifier="@2", agent_subagents="aaa111:Explore")
        assert subagent_view(pane).rows == ()

    def test_a_stale_pane_has_no_subagents(self):
        pane = agent_pane(current_command="zsh", agent_subagents="aaa111:Explore")
        assert subagent_view(pane).rows == ()

    def test_a_pane_without_subagents_adds_nothing(self):
        assert subagent_view(agent_pane()).rows == ()

    def test_the_row_remembers_the_pane_and_the_subagent(self):
        pane = agent_pane(agent_subagents="aaa111:Explore")
        row = subagent_view(pane).rows[0]
        assert isinstance(row.subject, SubagentSubject)
        assert row.subject.pane == pane
        assert row.subject.subagent.identifier == "aaa111"
        assert row.subject.parent_state == "working"

    def test_the_title_comes_from_the_section(self):
        assert subagent_view().title == "AGENTS"
