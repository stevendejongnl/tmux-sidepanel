"""Running a program and reading its output, without ever raising or hanging."""

import os
import sys

import pytest

from tmux_sidepanel.command_runner import (
    MAXIMUM_OUTPUT_CHARACTERS,
    process_directory,
    run_text_command,
)


class TestRunTextCommand:
    def test_returns_what_the_program_prints(self):
        assert run_text_command(["printf", "hello"], timeout_seconds=5) == "hello"

    def test_a_failing_program_gives_no_output(self):
        assert run_text_command(["false"], timeout_seconds=5) == ""

    def test_a_program_that_does_not_exist_gives_no_output(self):
        assert run_text_command(["no-such-program-anywhere"], timeout_seconds=5) == ""

    def test_a_program_that_takes_too_long_is_stopped(self):
        assert run_text_command(["sleep", "30"], timeout_seconds=0.2) == ""

    def test_the_output_is_cut_at_the_maximum(self):
        code = f"print('x' * {MAXIMUM_OUTPUT_CHARACTERS + 500})"
        output = run_text_command([sys.executable, "-c", code], timeout_seconds=10)
        assert len(output) == MAXIMUM_OUTPUT_CHARACTERS

    def test_what_the_program_writes_as_an_error_is_ignored(self):
        code = "import sys; sys.stderr.write('problem'); print('fine')"
        assert run_text_command([sys.executable, "-c", code], timeout_seconds=5).strip() == "fine"

    def test_output_that_is_not_text_is_made_readable(self):
        code = "import sys; sys.stdout.buffer.write(b'caf\\xe9 ok')"
        output = run_text_command([sys.executable, "-c", code], timeout_seconds=5)
        assert output.endswith(" ok")

    def test_no_shell_is_involved(self):
        assert run_text_command(["echo", "$HOME; touch /tmp/should-not-exist"], 5).startswith(
            "$HOME"
        )


@pytest.mark.skipif(not os.path.isdir("/proc"), reason="needs /proc")
class TestProcessDirectory:
    def test_reads_the_working_folder_of_a_process(self):
        assert process_directory(os.getpid()) == os.getcwd()

    def test_a_process_that_does_not_exist_gives_an_empty_text(self):
        assert process_directory(2**22 + 12345) == ""
