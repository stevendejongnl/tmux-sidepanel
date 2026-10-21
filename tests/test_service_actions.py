"""The actions of the menu of a service: stop, restart, logs, kill, go and open the folder."""

import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.fake_docker import install_fake_docker
from tests.tmux_support import (
    add_window,
    captured_text,
    first_pane_of_window,
    first_pane_of_window_starting,
    pane_identifiers,
    tmux_is_installed,
    wait_for_command,
    wait_until,
)
from tmux_sidepanel.action_outcome import ActionContext
from tmux_sidepanel.command_runner import run_text_command
from tmux_sidepanel.hook_runner import find_pane
from tmux_sidepanel.panes import PaneRecord
from tmux_sidepanel.process_table import PROCESS_LIST_COMMAND, parse_process_table
from tmux_sidepanel.service_actions import perform_service_action
from tmux_sidepanel.service_rows import ServiceEntry, ServiceSubject

pytestmark = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")


@dataclass(frozen=True)
class SleepWindow:
    """A window whose pane runs a sleep in the foreground."""

    pane: PaneRecord
    process_identifier: int


def build_context(client, docker_program="docker"):
    return ActionContext(client=client, docker_program=str(docker_program))


def container_entry(**overrides):
    values = {
        "kind": "docker",
        "command": "shop-web-1",
        "age": "6h",
        "is_container": True,
        "pane_identifier": "",
        "directory": "",
        "process_identifier": 0,
        "container_names": ("shop-web-1",),
        "project": "shop",
    }
    return ServiceEntry(**{**values, **overrides})


def process_entry(sleeper, **overrides):
    values = {
        "kind": "test",
        "command": "sleep 600",
        "age": "1m",
        "is_container": False,
        "pane_identifier": sleeper.pane.pane_identifier,
        "directory": "",
        "process_identifier": sleeper.process_identifier,
        "container_names": (),
        "project": "",
    }
    return ServiceEntry(**{**values, **overrides})


def is_foreground_sleep_on(process, terminal):
    is_foreground = "+" in process.status_flags
    return process.terminal == terminal and is_foreground and process.arguments.startswith("sleep")


def foreground_sleep(client, pane):
    wait_for_command(client, pane.pane_identifier, "sleep")
    record = find_pane(client.list_panes(), pane.pane_identifier)
    table = parse_process_table(run_text_command(PROCESS_LIST_COMMAND, 5))
    on_pane = filter(
        lambda process: is_foreground_sleep_on(process, record.terminal), table.values()
    )
    return next(on_pane).process_identifier


def process_exists(process_identifier):
    """A process that ended but is not yet collected by its parent counts as gone."""
    try:
        status = Path(f"/proc/{process_identifier}/stat").read_text()
    except OSError:
        return False
    return status.rsplit(")", 1)[1].split()[0] != "Z"


def start_sleep_window(client):
    add_window(client, "work", "sleep 600")
    pane = first_pane_of_window(client, "work")
    return SleepWindow(pane, foreground_sleep(client, pane))


def perform(context, entry, action):
    return perform_service_action(context, ServiceSubject(entry), action)


class TestContainers:
    def test_stop_asks_first_and_does_not_call_docker_yet(self, tmux_client, tmp_path):
        fake = install_fake_docker(tmp_path)
        outcome = perform(build_context(tmux_client, fake.program), container_entry(), "stop")
        assert outcome.prompt == "stop shop-web-1? y/n"
        assert fake.calls() == []

    def test_after_the_confirmation_docker_stops_the_container(self, tmux_client, tmp_path):
        fake = install_fake_docker(tmp_path)
        outcome = perform(build_context(tmux_client, fake.program), container_entry(), "stop")
        assert "stopping" in outcome.confirmed().notice
        assert fake.wait_for_calls() == ["stop shop-web-1"]

    def test_a_group_stops_every_container_of_the_project(self, tmux_client, tmp_path):
        fake = install_fake_docker(tmp_path)
        entry = container_entry(command="shop (2)", container_names=("shop-web-1", "shop-db-1"))
        perform(build_context(tmux_client, fake.program), entry, "stop").confirmed()
        assert fake.wait_for_calls() == ["stop shop-web-1 shop-db-1"]

    def test_restart_asks_and_then_restarts(self, tmux_client, tmp_path):
        fake = install_fake_docker(tmp_path)
        outcome = perform(build_context(tmux_client, fake.program), container_entry(), "restart")
        assert outcome.prompt == "restart shop-web-1? y/n"
        outcome.confirmed()
        assert fake.wait_for_calls() == ["restart shop-web-1"]

    def test_kill_asks_with_a_loud_prompt_and_then_kills(self, tmux_client, tmp_path):
        fake = install_fake_docker(tmp_path)
        outcome = perform(build_context(tmux_client, fake.program), container_entry(), "kill")
        assert outcome.prompt.startswith("FORCE kill")
        outcome.confirmed()
        assert fake.wait_for_calls() == ["kill shop-web-1"]

    def test_an_unsafe_name_is_refused_after_the_confirmation(self, tmux_client, tmp_path):
        fake = install_fake_docker(tmp_path)
        entry = container_entry(container_names=("-rf",))
        outcome = perform(build_context(tmux_client, fake.program), entry, "stop").confirmed()
        assert "unsafe" in outcome.notice
        assert fake.calls() == []

    def test_a_docker_that_is_not_installed_is_reported(self, tmux_client):
        context = build_context(tmux_client, "/no/such/docker")
        outcome = perform(context, container_entry(), "stop").confirmed()
        assert "docker" in outcome.notice

    def test_logs_open_in_a_new_window(self, tmux_client, tmp_path):
        fake = install_fake_docker(tmp_path)
        outcome = perform(build_context(tmux_client, fake.program), container_entry(), "logs")
        assert "logs" in outcome.notice
        pane = first_pane_of_window_starting(tmux_client, "logs-")
        shown = wait_until(
            lambda: "fake logs output" in captured_text(tmux_client, pane.pane_identifier)
        )
        assert shown

    def test_logs_of_a_project_use_compose(self, tmux_client, tmp_path):
        fake = install_fake_docker(tmp_path)
        entry = container_entry(command="shop (2)", container_names=("shop-web-1", "shop-db-1"))
        perform(build_context(tmux_client, fake.program), entry, "logs")
        assert fake.wait_for_calls() == ["compose -p shop logs -f --tail 100"]

    def test_logs_are_only_for_containers(self, tmux_client):
        sleeper = start_sleep_window(tmux_client)
        outcome = perform(build_context(tmux_client), process_entry(sleeper), "logs")
        assert "only for containers" in outcome.notice


class TestProcesses:
    def test_stop_asks_and_then_sends_control_c_to_the_pane(self, tmux_client):
        sleeper = start_sleep_window(tmux_client)
        outcome = perform(build_context(tmux_client), process_entry(sleeper), "stop")
        assert outcome.prompt == "stop sleep 600? y/n"
        assert process_exists(sleeper.process_identifier)
        outcome.confirmed()
        assert wait_until(lambda: not process_exists(sleeper.process_identifier))

    def test_kill_asks_and_then_ends_the_process(self, tmux_client):
        sleeper = start_sleep_window(tmux_client)
        outcome = perform(build_context(tmux_client), process_entry(sleeper), "kill")
        assert outcome.prompt.startswith("FORCE kill")
        assert process_exists(sleeper.process_identifier)
        outcome.confirmed()
        assert wait_until(lambda: not process_exists(sleeper.process_identifier))

    def test_a_process_that_is_not_on_the_pane_is_never_killed(self, tmux_client):
        sleeper = start_sleep_window(tmux_client)
        entry = process_entry(sleeper, process_identifier=os.getpid())
        outcome = perform(build_context(tmux_client), entry, "kill").confirmed()
        assert "no longer" in outcome.notice
        assert process_exists(os.getpid())

    def test_a_process_that_has_gone_is_not_a_problem(self, tmux_client):
        sleeper = start_sleep_window(tmux_client)
        entry = process_entry(sleeper, process_identifier=2**22 + 777)
        outcome = perform(build_context(tmux_client), entry, "kill").confirmed()
        assert "no longer" in outcome.notice
        assert process_exists(sleeper.process_identifier)

    def test_go_jumps_to_the_pane(self, tmux_client):
        sleeper = start_sleep_window(tmux_client)
        perform(build_context(tmux_client), process_entry(sleeper), "go")
        assert find_pane(tmux_client.list_panes(), sleeper.pane.pane_identifier).is_window_active

    def test_directory_opens_the_folder(self, tmux_client, tmp_path):
        sleeper = start_sleep_window(tmux_client)
        entry = process_entry(sleeper, directory=str(tmp_path))
        before = len(pane_identifiers(tmux_client))
        outcome = perform(build_context(tmux_client), entry, "directory")
        assert tmp_path.name in outcome.notice
        assert wait_until(lambda: len(pane_identifiers(tmux_client)) == before + 1)
