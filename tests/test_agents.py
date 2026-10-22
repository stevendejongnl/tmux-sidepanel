"""Agent states: roll several up into one, and read the subagent entries of a pane."""

import pytest

from tmux_sidepanel.agents import Subagent, most_urgent_state, parse_subagents, urgency


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        ([], ""),
        ([""], ""),
        (["idle"], "idle"),
        (["idle", "working"], "working"),
        (["working", "done"], "done"),
        (["done", "blocked", "working"], "blocked"),
        (["blocked", "idle"], "blocked"),
        (["", "idle", ""], "idle"),
        (["bogus"], ""),
        (["unknown", "idle"], "unknown"),
        (["idle", "unknown"], "idle"),
        (["unknown", "working"], "working"),
    ],
)
def test_most_urgent_state(states, expected):
    assert most_urgent_state(states) == expected


def test_urgency_orders_the_states():
    assert urgency("blocked") > urgency("done") > urgency("working") > urgency("idle")
    assert urgency("idle") > urgency("")


def test_urgency_of_an_unknown_name_is_zero():
    assert urgency("whatever") == 0


class TestParseSubagents:
    def test_reads_identifier_and_kind(self):
        assert parse_subagents("a7d3bd68dc2e:Explore") == [Subagent("a7d3bd68dc2e", "Explore")]

    def test_reads_several_entries(self):
        entries = parse_subagents("aaa111:Explore bbb222:general-purpose")
        assert [entry.kind for entry in entries] == ["Explore", "general-purpose"]

    def test_a_missing_kind_becomes_agent(self):
        assert parse_subagents("aaa111")[0].kind == "agent"
        assert parse_subagents("aaa111:")[0].kind == "agent"

    def test_empty_text_gives_no_entries(self):
        assert parse_subagents("") == []
        assert parse_subagents("   ") == []

    def test_skips_entries_without_an_identifier(self):
        assert parse_subagents(":Explore") == []

    def test_label_uses_the_kind_and_a_short_identifier(self):
        assert Subagent("a7d3bd68dc2e", "Explore").label == "Explore a7d3bd"


class TestDescription:
    def test_an_entry_can_carry_a_description(self):
        subagent = Subagent("bvz0tq", "shell", "Run_sleep_25")
        assert subagent.entry == "bvz0tq:shell:Run_sleep_25"

    def test_reads_a_description_after_the_kind(self):
        assert parse_subagents("bvz0tq:shell:Run_sleep_25") == [
            Subagent("bvz0tq", "shell", "Run_sleep_25")
        ]

    def test_an_entry_without_a_description_reads_as_before(self):
        assert parse_subagents("aaa111:Explore") == [Subagent("aaa111", "Explore")]

    def test_the_label_shows_the_description_instead_of_the_identifier(self):
        assert Subagent("bvz0tq", "shell", "Run_sleep_25").label == "shell Run sleep 25"
