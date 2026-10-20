"""Hook events: how a hook changes the state of its pane and the subagents it lists."""

import pytest

from tmux_sidepanel.agents import Subagent, format_subagents
from tmux_sidepanel.hooks import (
    HookContext,
    StateChange,
    state_change,
    updated_subagents,
)


def build_context(payload=None, pane_is_focused=False, current_state=""):
    return HookContext(payload or {}, pane_is_focused, current_state)


class TestFixedStates:
    @pytest.mark.parametrize("state", ["working", "idle", "blocked"])
    def test_sets_the_named_state(self, state):
        assert state_change(state, build_context()) == StateChange("set", state)

    def test_clear_removes_the_state(self):
        assert state_change("clear", build_context()) == StateChange("clear")

    def test_an_unknown_action_changes_nothing(self):
        assert state_change("bogus", build_context()) == StateChange("keep")


class TestDone:
    def test_a_finished_turn_in_a_pane_you_look_at_counts_as_seen(self):
        context = build_context(pane_is_focused=True)
        assert state_change("done", context) == StateChange("set", "idle")

    def test_a_finished_turn_in_another_pane_is_done(self):
        context = build_context(pane_is_focused=False)
        assert state_change("done", context) == StateChange("set", "done")


class TestSeen:
    def test_looking_at_a_done_pane_makes_it_idle(self):
        context = build_context(current_state="done")
        assert state_change("seen", context) == StateChange("set", "idle")

    @pytest.mark.parametrize("current_state", ["", "idle", "working", "blocked"])
    def test_looking_at_any_other_pane_changes_nothing(self, current_state):
        context = build_context(current_state=current_state)
        assert state_change("seen", context) == StateChange("keep")


class TestNotification:
    @pytest.mark.parametrize(
        ("notification_type", "expected"),
        [
            ("permission_prompt", "blocked"),
            ("elicitation_dialog", "blocked"),
            ("idle_prompt", "idle"),
        ],
    )
    def test_known_types_set_a_state(self, notification_type, expected):
        context = build_context({"notification_type": notification_type})
        assert state_change("notification", context) == StateChange("set", expected)

    @pytest.mark.parametrize("payload", [{}, {"notification_type": "auth_success"}, {"other": 1}])
    def test_other_notifications_change_nothing(self, payload):
        assert state_change("notification", build_context(payload)) == StateChange("keep")


class TestSubagents:
    def start(self, current, identifier, kind="Explore"):
        payload = {"agent_id": identifier, "agent_type": kind}
        return updated_subagents(current, "sub-start", payload)

    def stop(self, current, identifier):
        return updated_subagents(current, "sub-stop", {"agent_id": identifier})

    def test_a_start_adds_the_entry(self):
        assert self.start("", "aaa111") == "aaa111:Explore"

    def test_a_second_start_is_added_after_the_first(self):
        assert self.start("aaa111:Explore", "bbb222", "general-purpose") == (
            "aaa111:Explore bbb222:general-purpose"
        )

    def test_a_repeated_start_does_not_add_twice(self):
        assert self.start("aaa111:Explore", "aaa111") == "aaa111:Explore"

    def test_a_stop_removes_the_entry(self):
        assert self.stop("aaa111:Explore bbb222:agent", "aaa111") == "bbb222:agent"

    def test_the_last_stop_leaves_nothing(self):
        assert self.stop("aaa111:Explore", "aaa111") == ""

    def test_stopping_an_unknown_entry_changes_nothing(self):
        assert self.stop("aaa111:Explore", "zzz999") == "aaa111:Explore"

    def test_a_missing_kind_becomes_agent(self):
        assert updated_subagents("", "sub-start", {"agent_id": "aaa111"}) == "aaa111:agent"

    def test_a_payload_without_an_identifier_changes_nothing(self):
        assert updated_subagents("aaa111:Explore", "sub-start", {}) == "aaa111:Explore"

    def test_other_actions_change_nothing(self):
        payload = {"agent_id": "bbb222"}
        assert updated_subagents("aaa111:Explore", "working", payload) == "aaa111:Explore"

    def test_odd_characters_are_replaced_so_the_entry_stays_one_word(self):
        payload = {"agent_id": "a b:c", "agent_type": "my kind"}
        assert updated_subagents("", "sub-start", payload) == "a_b_c:my_kind"

    def test_a_payload_value_that_is_not_text_is_made_into_text(self):
        assert updated_subagents("", "sub-start", {"agent_id": 42}) == "42:agent"


def test_format_subagents_writes_entries_separated_by_a_space():
    subagents = [Subagent("aaa111", "Explore"), Subagent("bbb222", "agent")]
    assert format_subagents(subagents) == "aaa111:Explore bbb222:agent"


def test_the_entry_of_a_subagent():
    assert Subagent("aaa111", "Explore").entry == "aaa111:Explore"
