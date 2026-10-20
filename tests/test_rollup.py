"""Roll-ups: the most urgent state of a window or session, and panes whose agent is gone."""

from tests.builders import build_pane_record
from tmux_sidepanel.rollup import session_states, stale_agent_panes, window_states


def agent_pane(window="@1", session="$1", state="idle", **overrides):
    values = {"current_command": "claude", **overrides}
    return build_pane_record(
        window_identifier=window,
        session_identifier=session,
        agent_state=state,
        **values,
    )


class TestWindowStates:
    def test_a_window_takes_the_most_urgent_state_of_its_panes(self):
        panes = [agent_pane(state="idle"), agent_pane(state="blocked"), agent_pane(state="working")]
        assert window_states(panes) == {"@1": "blocked"}

    def test_each_window_gets_its_own_state(self):
        panes = [agent_pane("@1", state="working"), agent_pane("@2", state="done")]
        assert window_states(panes) == {"@1": "working", "@2": "done"}

    def test_a_window_without_an_agent_has_an_empty_state(self):
        panes = [build_pane_record(window_identifier="@1")]
        assert window_states(panes) == {"@1": ""}

    def test_the_panel_never_counts(self):
        panes = [agent_pane(state="blocked", is_panel=True), agent_pane(state="idle")]
        assert window_states(panes) == {"@1": "idle"}

    def test_a_window_that_only_has_the_panel_is_listed_with_an_empty_state(self):
        panes = [build_pane_record(window_identifier="@1", is_panel=True)]
        assert window_states(panes) == {"@1": ""}

    def test_no_panes_give_no_windows(self):
        assert window_states([]) == {}


class TestSessionStates:
    def test_a_session_takes_the_most_urgent_state_across_its_windows(self):
        panes = [
            agent_pane("@1", "$1", state="working"),
            agent_pane("@2", "$1", state="done"),
            agent_pane("@3", "$2", state="idle"),
        ]
        assert session_states(panes) == {"$1": "done", "$2": "idle"}

    def test_a_session_without_an_agent_has_an_empty_state(self):
        assert session_states([build_pane_record(session_identifier="$7")]) == {"$7": ""}

    def test_the_panel_never_counts(self):
        panes = [agent_pane(state="blocked", is_panel=True)]
        assert session_states(panes) == {"$1": ""}


class TestStalePanes:
    def stale_identifiers(self, panes, agent_names=("claude",)):
        return [pane.pane_identifier for pane in stale_agent_panes(panes, agent_names)]

    def test_a_pane_with_a_state_that_no_longer_runs_the_agent_is_stale(self):
        pane = agent_pane(pane_identifier="%4", current_command="zsh")
        assert self.stale_identifiers([pane]) == ["%4"]

    def test_a_pane_that_still_runs_the_agent_is_not_stale(self):
        assert self.stale_identifiers([agent_pane()]) == []

    def test_a_pane_without_a_state_is_not_stale(self):
        pane = build_pane_record(current_command="zsh", agent_state="")
        assert self.stale_identifiers([pane]) == []

    def test_the_panel_is_never_stale(self):
        pane = agent_pane(current_command="python3", is_panel=True)
        assert self.stale_identifiers([pane]) == []

    def test_agent_names_can_be_changed(self):
        pane = agent_pane(current_command="codex")
        assert self.stale_identifiers([pane]) == ["%1"]
        assert self.stale_identifiers([pane], agent_names=("codex",)) == []
