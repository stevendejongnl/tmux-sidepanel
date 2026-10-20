"""The entry file that the tmux plugin manager runs."""

import shutil

import pytest

from tests.conftest import PROJECT_ROOT, run_command
from tests.tmux_support import tmux_is_installed

ENTRY_PATH = PROJECT_ROOT / "tmux_sidepanel.tmux"


def test_the_entry_file_exists_and_can_be_run():
    assert ENTRY_PATH.exists()
    assert ENTRY_PATH.stat().st_mode & 0o111


@pytest.mark.skipif(shutil.which("shellcheck") is None, reason="shellcheck is not installed")
def test_the_entry_file_passes_shellcheck():
    assert run_command(["shellcheck", ENTRY_PATH]).returncode == 0


@pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")
class TestRunning:
    def hooks(self, overrides):
        return run_command(["tmux", "show-hooks", "-g"], **overrides).stdout

    def test_running_it_installs_the_hooks(self, default_server_environment):
        result = run_command([ENTRY_PATH], **default_server_environment)
        assert result.returncode == 0, result.stderr
        assert "after-select-pane[9100]" in self.hooks(default_server_environment)

    def test_running_it_twice_changes_nothing(self, default_server_environment):
        run_command([ENTRY_PATH], **default_server_environment)
        first = self.hooks(default_server_environment)
        run_command([ENTRY_PATH], **default_server_environment)
        assert self.hooks(default_server_environment) == first
