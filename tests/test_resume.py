"""The command that reopens the session of an agent process that no pane shows."""

from tmux_sidepanel.resume import resume_command


def test_a_known_session_is_resumed_by_its_identifier():
    assert resume_command("/opt/bin/claude", "abc-123", "") == "/opt/bin/claude --resume abc-123"


def test_an_unknown_session_continues_the_latest_one():
    assert resume_command("/opt/bin/claude", "", "") == "/opt/bin/claude --continue"


def test_the_configuration_folder_of_the_old_process_is_kept():
    command = resume_command("/opt/bin/claude", "abc", "/home/me/.claude/accounts/work")
    assert command == (
        "CLAUDE_CONFIG_DIR=/home/me/.claude/accounts/work /opt/bin/claude --resume abc"
    )


def test_words_with_spaces_are_quoted():
    command = resume_command("/opt/my tools/claude", "abc", "/home/my folder/.claude")
    assert command == (
        "CLAUDE_CONFIG_DIR='/home/my folder/.claude' '/opt/my tools/claude' --resume abc"
    )


def test_a_session_identifier_cannot_add_a_second_command():
    command = resume_command("/opt/bin/claude", "abc; rm -rf /", "")
    assert command == "/opt/bin/claude --resume 'abc; rm -rf /'"
