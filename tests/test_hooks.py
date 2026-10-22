"""Hook events: how a hook changes the state of its pane and the subagents it lists."""

import pytest

from tmux_sidepanel.agents import Subagent, format_subagents
from tmux_sidepanel.hooks import (
    HookContext,
    StateChange,
    state_change,
    updated_subagents,
    updated_tasks,
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


BACKGROUND_START = {
    "tool_name": "Bash",
    "tool_input": {"command": "sleep 25", "description": "Run sleep 25", "run_in_background": True},
    "tool_response": {"stdout": "", "backgroundTaskId": "bvz0tqfh6"},
}


def snapshot(*tasks, crons=()):
    return {"background_tasks": list(tasks), "session_crons": list(crons)}


def shell_task(identifier="bvz0tqfh6", description="Run sleep 25", status="running"):
    return {"id": identifier, "type": "shell", "status": status, "description": description}


class TestBackgroundTasks:
    def test_a_background_command_is_listed_when_it_starts(self):
        assert updated_tasks("", "working", BACKGROUND_START) == "bvz0tqfh6:shell:Run_sleep_25"

    def test_a_command_in_the_foreground_adds_nothing(self):
        payload = {**BACKGROUND_START, "tool_response": {"stdout": "done"}}
        assert updated_tasks("", "working", payload) == ""

    def test_a_start_keeps_the_tasks_that_run_already(self):
        assert updated_tasks("old1:shell", "working", BACKGROUND_START) == (
            "old1:shell bvz0tqfh6:shell:Run_sleep_25"
        )

    def test_the_same_task_is_listed_once(self):
        current = "bvz0tqfh6:shell:Run_sleep_25"
        assert updated_tasks(current, "working", BACKGROUND_START) == current

    def test_a_snapshot_replaces_the_list(self):
        payload = snapshot(shell_task("new111", "Build"))
        assert updated_tasks("old1:shell", "working", payload) == "new111:shell:Build"

    def test_an_empty_snapshot_ends_every_task(self):
        assert updated_tasks("old1:shell", "working", snapshot()) == ""

    def test_only_running_tasks_are_listed(self):
        payload = snapshot(shell_task("run111"), shell_task("end222", status="completed"))
        assert updated_tasks("", "working", payload) == "run111:shell:Run_sleep_25"

    def test_the_type_is_the_kind(self):
        payload = snapshot({"id": "m1", "type": "monitor", "status": "running"})
        assert updated_tasks("", "working", payload) == "m1:monitor"

    def test_subagents_are_left_to_the_subagent_hooks(self):
        payload = snapshot({"id": "a1", "type": "subagent", "status": "running"})
        assert updated_tasks("", "working", payload) == ""

    def test_scheduled_tasks_are_listed_as_cron(self):
        payload = snapshot(crons=[{"id": "c1", "schedule": "*/5 * * * *", "prompt": "check"}])
        assert updated_tasks("", "working", payload) == "c1:cron"

    def test_a_payload_without_a_snapshot_changes_nothing(self):
        assert (
            updated_tasks("old1:shell", "working", {"last_assistant_message": "ok"}) == "old1:shell"
        )

    def test_odd_characters_are_replaced_and_a_long_description_is_cut(self):
        payload = snapshot(shell_task("a b", "npm run dev --port=3000 " + "x" * 80))
        entry = updated_tasks("", "working", payload)
        assert entry.startswith("a_b:shell:npm_run_dev_--port_3000_")
        assert len(entry.split(":")[2]) == 40


class TestCompaction:
    ENTRY = "compaction:compact:Summarizing_context"

    def test_compacting_lists_a_row(self):
        assert updated_tasks("", "compacting", {"trigger": "auto"}) == self.ENTRY

    def test_compacting_keeps_the_other_tasks(self):
        assert updated_tasks("old1:shell", "compacting", {}) == f"old1:shell {self.ENTRY}"

    def test_compacting_twice_lists_one_row(self):
        assert updated_tasks(self.ENTRY, "compacting", {}) == self.ENTRY

    def test_compacted_removes_only_the_row_of_the_compaction(self):
        assert updated_tasks(f"old1:shell {self.ENTRY}", "compacted", {}) == "old1:shell"

    def test_compacted_without_a_row_changes_nothing(self):
        assert updated_tasks("old1:shell", "compacted", {}) == "old1:shell"


class TestFailure:
    ENTRY = "failure:error:rate_limit"

    def test_a_failed_turn_blocks_the_pane(self):
        assert state_change("failed", build_context()) == StateChange("set", "blocked")

    def test_a_failure_lists_a_row_with_the_reason(self):
        assert updated_tasks("", "failed", {"error": "rate_limit"}) == self.ENTRY

    def test_a_failure_without_a_reason_still_lists_a_row(self):
        assert updated_tasks("", "failed", {}) == "failure:error:Stopped_on_an_error"

    def test_a_second_failure_replaces_the_first(self):
        entry = updated_tasks(self.ENTRY, "failed", {"error": "overloaded"})
        assert entry == "failure:error:overloaded"

    def test_any_new_work_removes_the_row(self):
        assert updated_tasks(f"old1:shell {self.ENTRY}", "working", {}) == "old1:shell"

    def test_a_failure_keeps_the_other_tasks(self):
        assert updated_tasks("old1:shell", "failed", {"error": "rate_limit"}) == (
            f"old1:shell {self.ENTRY}"
        )
