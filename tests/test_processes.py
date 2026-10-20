"""Process table logic: find orphaned agent processes and read the session id."""

import pytest

from tests.builders import build_process
from tmux_sidepanel.processes import Zombie, find_zombies, resume_session_identifier

PANE_TERMINALS = {"pts/1", "pts/2"}


def build_table(*processes):
    return {process.process_identifier: process for process in processes}


def find(*processes, **options):
    return find_zombies(build_table(*processes), PANE_TERMINALS, **options)


def zombie_identifiers(zombies):
    return [zombie.process.process_identifier for zombie in zombies]


def test_an_agent_on_a_pane_is_not_a_zombie():
    assert find(build_process(10, terminal="pts/1")) == []


def test_an_agent_without_a_pane_is_a_zombie():
    process = build_process(10, terminal="?")
    assert find(process) == [Zombie(process, "no pane")]


def test_an_agent_on_a_terminal_that_is_not_a_pane_is_a_zombie():
    assert find(build_process(10, terminal="pts/9"))[0].reason == "no pane"


def test_a_helper_below_a_live_session_is_not_a_zombie():
    session = build_process(10, terminal="pts/1")
    helper = build_process(11, arguments="/opt/bin/claude --output-format stream-json", parent=10)
    assert find(session, helper) == []


def test_a_helper_several_levels_below_a_live_session_is_not_a_zombie():
    session = build_process(10, terminal="pts/1")
    middle = build_process(11, arguments="python3 hook.py", parent=10)
    helper = build_process(12, parent=11)
    assert find(session, middle, helper) == []


def test_a_helper_of_a_dead_parent_is_a_zombie():
    parent = build_process(10, arguments="python3 hook.py", parent=1)
    helper = build_process(11, parent=10)
    assert zombie_identifiers(find(parent, helper)) == [11]


def test_a_stopped_agent_is_a_zombie_even_on_a_pane():
    assert find(build_process(10, terminal="pts/1", status_flags="T"))[0].reason == "stopped"


def test_a_stopped_agent_with_extra_status_flags_still_counts():
    assert find(build_process(10, terminal="pts/1", status_flags="Tl+"))[0].reason == "stopped"


def test_a_defunct_agent_is_reported_as_defunct():
    assert find(build_process(10, terminal="pts/1", status_flags="Z"))[0].reason == "defunct"


def test_the_browser_bridge_is_ignored():
    assert find(build_process(10, arguments="/opt/bin/claude --chrome-native-host")) == []


def test_ignored_arguments_can_be_changed():
    process = build_process(10, arguments="/opt/bin/claude --bridge")
    assert find(process, ignored_arguments=("--bridge",)) == []
    assert len(find(process, ignored_arguments=())) == 1


def test_other_programs_are_ignored():
    assert find(build_process(10, arguments="/usr/bin/python3 script.py")) == []


def test_a_program_that_only_contains_the_name_is_ignored():
    assert find(build_process(10, arguments="/usr/bin/claude-helper run")) == []


def test_agent_names_can_be_changed():
    process = build_process(10, arguments="/usr/local/bin/codex exec")
    assert find(process) == []
    assert len(find(process, agent_names=("codex",))) == 1


def test_several_agent_names_are_checked():
    first = build_process(10, arguments="claude")
    second = build_process(11, arguments="codex")
    found = find(first, second, agent_names=("claude", "codex"))
    assert zombie_identifiers(found) == [10, 11]


def test_the_result_is_sorted_by_process_identifier():
    found = find(build_process(30), build_process(10), build_process(20))
    assert zombie_identifiers(found) == [10, 20, 30]


def test_a_parent_loop_does_not_hang():
    first = build_process(10, parent=11)
    second = build_process(11, parent=10)
    assert len(find(first, second)) == 2


def test_a_process_that_is_its_own_parent_does_not_hang():
    assert len(find(build_process(10, parent=10))) == 1


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["claude", "--resume", "abc-123"], "abc-123"),
        (["claude", "-r", "abc-123"], "abc-123"),
        (["claude", "--session-id", "abc-123"], "abc-123"),
        (["claude", "--model", "x", "--resume", "abc"], "abc"),
        (["claude", "--resume", "--verbose"], ""),
        (["claude", "--resume"], ""),
        (["claude"], ""),
        ([], ""),
    ],
)
def test_resume_session_identifier(arguments, expected):
    assert resume_session_identifier(arguments) == expected
