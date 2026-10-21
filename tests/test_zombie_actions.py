"""The actions of the menu of a zombie: open, terminate, kill and open the folder."""

import os
import signal
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from tests.tmux_support import (
    add_window,
    captured_text,
    first_pane_of_window,
    first_pane_of_window_starting,
    install_argument_agent,
    install_fake_agent,
    tmux_is_installed,
    wait_for_program,
    wait_until,
)
from tmux_sidepanel.action_outcome import ActionContext
from tmux_sidepanel.command_runner import run_text_command
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.process_table import PROCESS_LIST_COMMAND, parse_process_table
from tmux_sidepanel.processes import Zombie
from tmux_sidepanel.zombie_actions import perform_zombie_action
from tmux_sidepanel.zombie_rows import ZombieSubject

CONFIG_FOLDER = "/nonexistent/configuration-folder"

pytestmark = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")


def build_context(client):
    return ActionContext(client=client)


def start_detached(program, *arguments, **environment):
    process = subprocess.Popen(
        [str(program), *arguments],
        env={"PATH": os.environ["PATH"], **environment},
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return wait_for_program(process, Path(program).name)


def start_named_agent(program, *arguments, **environment):
    """Start a shell that reports the name of the program as its own, as a real agent would."""
    process = subprocess.Popen(
        [str(program), "-c", "sleep 30; true", *arguments],
        executable="/bin/sh",
        env={"PATH": os.environ["PATH"], **environment},
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return wait_for_program(process, Path(program).name)


def subject_of(process, directory="", pane_identifier=""):
    table = parse_process_table(run_text_command(PROCESS_LIST_COMMAND, 5))
    return ZombieSubject(Zombie(table[process.pid], "no pane"), directory, pane_identifier)


@pytest.fixture
def started_agents():
    processes = []

    def start(program, *arguments, **environment):
        processes.append(start_named_agent(program, *arguments, **environment))
        return processes[-1]

    yield start
    list(map(subprocess.Popen.kill, processes))
    list(map(subprocess.Popen.wait, processes))


@pytest.fixture
def zombie_process(tmp_path):
    process = start_detached(install_fake_agent(tmp_path), "600")
    yield process
    process.kill()
    process.wait()


class TestSignals:
    def test_terminate_asks_first_and_leaves_the_process_alone_until_then(
        self, tmux_client, zombie_process
    ):
        subject = subject_of(zombie_process)
        outcome = perform_zombie_action(build_context(tmux_client), subject, "terminate")
        assert outcome.prompt == f"terminate {zombie_process.pid}? y/n"
        assert zombie_process.poll() is None

    def test_after_the_confirmation_the_process_ends(self, tmux_client, zombie_process):
        subject = subject_of(zombie_process)
        outcome = perform_zombie_action(build_context(tmux_client), subject, "terminate")
        assert "TERM" in outcome.confirmed().notice
        assert wait_until(lambda: zombie_process.poll() is not None)

    def test_a_stopped_process_is_woken_so_that_it_can_end(self, tmux_client, zombie_process):
        os.kill(zombie_process.pid, signal.SIGSTOP)
        subject = subject_of(zombie_process)
        zombie = Zombie(subject.zombie.process, "stopped")
        stopped = ZombieSubject(zombie, "", "")
        perform_zombie_action(build_context(tmux_client), stopped, "terminate").confirmed()
        assert wait_until(lambda: zombie_process.poll() is not None)

    def test_kill_asks_with_a_loud_prompt_and_then_kills(self, tmux_client, zombie_process):
        subject = subject_of(zombie_process)
        outcome = perform_zombie_action(build_context(tmux_client), subject, "kill")
        assert outcome.prompt.startswith("FORCE kill")
        outcome.confirmed()
        assert wait_until(lambda: zombie_process.poll() is not None)

    def test_a_process_that_is_no_longer_a_zombie_is_left_alone(self, tmux_client, zombie_process):
        subject = subject_of(zombie_process)
        borrowed = replace(subject.zombie.process, process_identifier=os.getpid())
        other = ZombieSubject(Zombie(borrowed, "no pane"), "", "")
        outcome = perform_zombie_action(build_context(tmux_client), other, "kill").confirmed()
        assert "no longer" in outcome.notice

    def test_a_process_that_has_gone_is_reported(self, tmux_client, zombie_process):
        subject = subject_of(zombie_process)
        zombie_process.kill()
        zombie_process.wait()
        outcome = perform_zombie_action(build_context(tmux_client), subject, "kill").confirmed()
        assert "no longer" in outcome.notice


class TestOpen:
    def test_a_stopped_agent_in_a_pane_jumps_to_the_pane(self, tmux_client, zombie_process):
        add_window(tmux_client, "second")
        pane = first_pane_of_window(tmux_client, "second")
        subject = subject_of(zombie_process, pane_identifier=pane.pane_identifier)
        perform_zombie_action(build_context(tmux_client), subject, "open")
        assert find_pane(tmux_client.list_panes(), pane.pane_identifier).is_window_active

    def test_an_agent_without_a_pane_is_resumed_in_a_new_window(
        self, tmux_client, tmp_path, started_agents
    ):
        program = install_argument_agent(tmp_path)
        process = started_agents(program, "--resume", "abc-123", CLAUDE_CONFIG_DIR=CONFIG_FOLDER)
        subject = subject_of(process, directory=str(tmp_path))
        outcome = perform_zombie_action(build_context(tmux_client), subject, "open")
        assert "resume" in outcome.notice
        pane = first_pane_of_window_starting(tmux_client, "resume-")
        expected = f"arguments: --resume abc-123 configuration: {CONFIG_FOLDER}"
        assert wait_until(lambda: expected in captured_text(tmux_client, pane.pane_identifier))

    def test_without_a_session_identifier_the_latest_session_is_continued(
        self, tmux_client, tmp_path, started_agents
    ):
        process = started_agents(install_argument_agent(tmp_path))
        subject = subject_of(process, directory=str(tmp_path))
        perform_zombie_action(build_context(tmux_client), subject, "open")
        pane = first_pane_of_window_starting(tmux_client, "resume-")
        shown = wait_until(
            lambda: "arguments: --continue" in captured_text(tmux_client, pane.pane_identifier)
        )
        assert shown

    def test_an_agent_that_is_not_claude_is_not_resumed(
        self, tmux_client, tmp_path, started_agents
    ):
        program = tmp_path / "codex"
        program.write_text("#!/bin/sh\n")
        process = started_agents(program)
        outcome = perform_zombie_action(build_context(tmux_client), subject_of(process), "open")
        assert "only known for claude" in outcome.notice


class TestDirectory:
    def test_opens_the_folder_of_the_zombie(self, tmux_client, zombie_process, tmp_path):
        subject = subject_of(zombie_process, directory=str(tmp_path))
        outcome = perform_zombie_action(build_context(tmux_client), subject, "directory")
        assert tmp_path.name in outcome.notice
