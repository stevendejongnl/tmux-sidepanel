"""Describing panes for a program that reads JSON, and finding a pane by its identifier or name."""

import pytest

from tests.builders import build_pane_record
from tmux_sidepanel.agent_output import AgentCommandError
from tmux_sidepanel.pane_description import (
    describe_pane,
    describe_panes,
    resolve_pane,
)

AGENTS = ("claude",)


def agent_pane(**overrides):
    values = {"current_command": "claude", "agent_state": "working", "agent_kind": "claude"}
    return build_pane_record(**{**values, **overrides})


class TestDescribePane:
    def test_a_plain_pane_has_no_agent_fields(self):
        pane = build_pane_record(current_command="zsh")
        description = describe_pane(pane, AGENTS)
        assert description.command == "zsh"
        assert (description.state, description.kind, description.name) == ("", "", "")

    def test_an_agent_pane_has_its_state_kind_and_name(self):
        description = describe_pane(agent_pane(agent_name="reviewer"), AGENTS)
        assert description.state == "working"
        assert description.kind == "claude"
        assert description.name == "reviewer"

    def test_an_agent_without_a_reported_state_is_unknown(self):
        description = describe_pane(agent_pane(agent_state="", agent_kind=""), AGENTS)
        assert description.state == "unknown"
        assert description.kind == "claude"

    def test_a_stale_state_on_a_pane_that_no_longer_runs_the_agent_is_ignored(self):
        pane = agent_pane(current_command="zsh", agent_name="gone")
        description = describe_pane(pane, AGENTS)
        assert (description.state, description.kind, description.name) == ("", "", "")

    def test_the_position_of_the_pane_is_described(self):
        pane = build_pane_record(
            session_name="main", window_index=2, window_name="shop", pane_index=1
        )
        description = describe_pane(pane, AGENTS)
        assert (description.session, description.window) == ("main", 2)
        assert (description.window_name, description.pane) == ("shop", 1)

    def test_the_pane_is_active_only_when_it_has_the_focus_in_its_window(self):
        pane = build_pane_record(is_active=True, is_window_active=False)
        assert describe_pane(pane, AGENTS).active is False


class TestDescribePanes:
    def test_the_panel_panes_are_left_out(self):
        panes = [build_pane_record(pane_identifier="%1"), build_pane_record(is_panel=True)]
        assert [item.pane_id for item in describe_panes(panes, AGENTS)] == ["%1"]

    def test_only_agents_can_be_asked_for(self):
        panes = [build_pane_record(pane_identifier="%1"), agent_pane(pane_identifier="%2")]
        found = describe_panes(panes, AGENTS, only_agents=True)
        assert [item.pane_id for item in found] == ["%2"]


class TestResolvePane:
    PANES = (
        agent_pane(pane_identifier="%1", agent_name="reviewer"),
        build_pane_record(pane_identifier="%2", current_command="zsh"),
    )

    def resolve(self, target, current="%2"):
        return resolve_pane(list(self.PANES), target, current, AGENTS)

    def test_finds_a_pane_by_its_identifier(self):
        assert self.resolve("%2").pane_identifier == "%2"

    def test_finds_an_agent_by_its_name(self):
        assert self.resolve("reviewer").pane_identifier == "%1"

    def test_current_is_the_pane_of_the_caller(self):
        assert self.resolve("current", current="%1").pane_identifier == "%1"

    def test_no_target_is_the_pane_of_the_caller(self):
        assert self.resolve(None, current="%1").pane_identifier == "%1"

    def test_the_caller_must_be_in_tmux(self):
        with pytest.raises(AgentCommandError) as caught:
            self.resolve("current", current="")
        assert caught.value.code == "not_in_tmux"

    def test_an_unknown_pane_is_reported(self):
        with pytest.raises(AgentCommandError) as caught:
            self.resolve("%99")
        assert caught.value.code == "pane_not_found"

    def test_an_unknown_name_is_reported(self):
        with pytest.raises(AgentCommandError) as caught:
            self.resolve("nobody")
        assert caught.value.code == "agent_not_found"

    def test_a_name_on_two_panes_is_ambiguous(self):
        panes = [agent_pane(pane_identifier=f"%{number}", agent_name="twin") for number in (1, 2)]
        with pytest.raises(AgentCommandError) as caught:
            resolve_pane(panes, "twin", "%1", AGENTS)
        assert caught.value.code == "ambiguous_name"

    def test_a_stale_name_is_not_found(self):
        panes = [agent_pane(current_command="zsh", agent_name="gone")]
        with pytest.raises(AgentCommandError) as caught:
            resolve_pane(panes, "gone", "%1", AGENTS)
        assert caught.value.code == "agent_not_found"
