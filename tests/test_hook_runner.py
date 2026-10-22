"""Applying a hook event to a real tmux server: the pane state, subagents and the roll-ups."""

import pytest

from tests.tmux_support import (
    add_window,
    first_pane_of_window,
    install_fake_agent,
    split_pane,
    tmux_is_installed,
    wait_for_command,
)
from tmux_sidepanel.hook_runner import (
    HookRequest,
    find_pane,
    reap_stale_panes,
    refresh_rollups,
    run_hook,
)
from tmux_sidepanel.options import (
    OPTION_SESSION_STATE,
    OPTION_STATE,
    OPTION_WINDOW_STATE,
    option_expression,
)

pytestmark = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")


def hook(client, pane, action, payload=None, agent_kind="claude"):
    run_hook(client, HookRequest(pane.pane_identifier, action, payload or {}, agent_kind))


def reload_pane(client, pane):
    return find_pane(client.list_panes(), pane.pane_identifier)


def window_state(client, pane):
    return client.display(pane.pane_identifier, option_expression(OPTION_WINDOW_STATE))


def session_state(client, pane):
    return client.display(pane.pane_identifier, option_expression(OPTION_SESSION_STATE))


class TestState:
    def test_working_sets_the_state_and_the_kind(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        hook(tmux_client, pane, "working")
        record = reload_pane(tmux_client, pane)
        assert (record.agent_state, record.agent_kind) == ("working", "claude")

    def test_the_kind_comes_from_the_request(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        hook(tmux_client, pane, "working", agent_kind="codex")
        assert reload_pane(tmux_client, pane).agent_kind == "codex"

    def test_the_state_rolls_up_to_the_window_and_the_session(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        hook(tmux_client, pane, "working")
        assert window_state(tmux_client, pane) == "working"
        assert session_state(tmux_client, pane) == "working"

    def test_blocked_beats_working_in_the_same_window(self, tmux_client):
        split_pane(tmux_client, "first")
        first, second = tmux_client.list_panes()[:2]
        hook(tmux_client, first, "working")
        hook(tmux_client, second, "blocked")
        assert window_state(tmux_client, first) == "blocked"

    def test_another_window_keeps_its_own_state(self, tmux_client):
        add_window(tmux_client, "second")
        first = first_pane_of_window(tmux_client, "first")
        second = first_pane_of_window(tmux_client, "second")
        hook(tmux_client, first, "working")
        hook(tmux_client, second, "idle")
        assert window_state(tmux_client, first) == "working"
        assert window_state(tmux_client, second) == "idle"
        assert session_state(tmux_client, first) == "working"

    def test_a_finished_turn_in_a_pane_nobody_looks_at_is_done(self, tmux_client):
        add_window(tmux_client, "second")
        second = first_pane_of_window(tmux_client, "second")
        hook(tmux_client, second, "done")
        assert reload_pane(tmux_client, second).agent_state == "done"
        assert window_state(tmux_client, second) == "done"

    def test_looking_at_a_done_pane_makes_it_idle(self, tmux_client):
        add_window(tmux_client, "second")
        second = first_pane_of_window(tmux_client, "second")
        hook(tmux_client, second, "done")
        hook(tmux_client, second, "seen")
        assert reload_pane(tmux_client, second).agent_state == "idle"
        assert window_state(tmux_client, second) == "idle"

    def test_looking_at_a_working_pane_changes_nothing(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        hook(tmux_client, pane, "working")
        hook(tmux_client, pane, "seen")
        assert reload_pane(tmux_client, pane).agent_state == "working"

    def test_a_permission_prompt_blocks_the_pane(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        hook(tmux_client, pane, "notification", {"notification_type": "permission_prompt"})
        assert reload_pane(tmux_client, pane).agent_state == "blocked"

    def test_an_unknown_action_changes_nothing(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        hook(tmux_client, pane, "bogus")
        assert reload_pane(tmux_client, pane).agent_state == ""

    def test_clear_removes_the_state_the_subagents_and_the_roll_ups(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        hook(tmux_client, pane, "working")
        hook(tmux_client, pane, "sub-start", {"agent_id": "aaa111", "agent_type": "Explore"})
        hook(tmux_client, pane, "clear")
        record = reload_pane(tmux_client, pane)
        assert (record.agent_state, record.agent_kind, record.agent_subagents) == ("", "", "")
        assert window_state(tmux_client, pane) == ""
        assert session_state(tmux_client, pane) == ""

    def test_a_pane_that_does_not_exist_is_ignored(self, tmux_client):
        run_hook(tmux_client, HookRequest("%999", "working", {}))
        assert first_pane_of_window(tmux_client, "first").agent_state == ""


class TestSubagents:
    def test_a_start_and_a_stop_update_the_entries(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        hook(tmux_client, pane, "sub-start", {"agent_id": "aaa111", "agent_type": "Explore"})
        hook(tmux_client, pane, "sub-start", {"agent_id": "bbb222"})
        assert reload_pane(tmux_client, pane).agent_subagents == "aaa111:Explore bbb222:agent"
        hook(tmux_client, pane, "sub-stop", {"agent_id": "aaa111"})
        assert reload_pane(tmux_client, pane).agent_subagents == "bbb222:agent"

    def test_the_last_stop_removes_the_option(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        hook(tmux_client, pane, "sub-start", {"agent_id": "aaa111"})
        hook(tmux_client, pane, "sub-stop", {"agent_id": "aaa111"})
        assert reload_pane(tmux_client, pane).agent_subagents == ""

    def test_subagents_do_not_change_the_state(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        hook(tmux_client, pane, "working")
        hook(tmux_client, pane, "sub-start", {"agent_id": "aaa111"})
        assert reload_pane(tmux_client, pane).agent_state == "working"


class TestRefreshRollups:
    def test_repairs_a_roll_up_that_does_not_match_the_panes(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        tmux_client.write_pane_option(pane.pane_identifier, OPTION_STATE, "blocked")
        refresh_rollups(tmux_client)
        assert window_state(tmux_client, pane) == "blocked"
        assert session_state(tmux_client, pane) == "blocked"


class TestReap:
    def test_clears_the_state_of_a_pane_whose_agent_is_gone(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        hook(tmux_client, pane, "working")
        reap_stale_panes(tmux_client, ("claude",))
        assert reload_pane(tmux_client, pane).agent_state == ""
        assert window_state(tmux_client, pane) == ""
        assert session_state(tmux_client, pane) == ""

    def test_keeps_the_state_of_a_pane_that_still_runs_the_agent(self, tmux_client, tmp_path):
        program = install_fake_agent(tmp_path)
        add_window(tmux_client, "agent", f"{program} 600")
        pane = first_pane_of_window(tmux_client, "agent")
        wait_for_command(tmux_client, pane.pane_identifier, "claude")
        hook(tmux_client, pane, "working")
        reap_stale_panes(tmux_client, ("claude",))
        assert reload_pane(tmux_client, pane).agent_state == "working"
        assert window_state(tmux_client, pane) == "working"


class TestBackgroundTasks:
    START = {"tool_response": {"backgroundTaskId": "bvz0tq"}, "tool_input": {}}

    def test_a_start_is_stored_and_the_next_snapshot_replaces_it(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        hook(tmux_client, pane, "working", self.START)
        assert reload_pane(tmux_client, pane).agent_tasks == "bvz0tq:shell"
        snapshot = {"background_tasks": [{"id": "n1", "type": "monitor", "status": "running"}]}
        hook(tmux_client, pane, "done", snapshot)
        assert reload_pane(tmux_client, pane).agent_tasks == "n1:monitor"

    def test_an_empty_snapshot_removes_the_option(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        hook(tmux_client, pane, "working", self.START)
        hook(tmux_client, pane, "done", {"background_tasks": []})
        assert reload_pane(tmux_client, pane).agent_tasks == ""

    def test_the_end_of_the_session_clears_the_tasks(self, tmux_client):
        pane = first_pane_of_window(tmux_client, "first")
        hook(tmux_client, pane, "working", self.START)
        hook(tmux_client, pane, "clear")
        assert reload_pane(tmux_client, pane).agent_tasks == ""
