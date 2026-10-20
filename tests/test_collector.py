"""Collecting a snapshot: tmux, ps, docker, /proc and the commands of custom sections."""

import os
import shutil
import subprocess
import textwrap

import pytest

from tests.tmux_support import install_fake_agent, tmux_is_installed
from tmux_sidepanel.collector import Collector, collect_snapshot
from tmux_sidepanel.configuration import default_configuration, parse_configuration

pytestmark = pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")

DOCKER_LISTING = "shop-web-1\tUp 6 hours\tweb\t/mnt/data/shop\tshop\n"


def write_fake_docker(directory, output=DOCKER_LISTING, marker=None):
    """A program that stands in for docker: it prints a listing, and notes that it was run."""
    script = directory / "fake-docker"
    note = f"touch {marker}\n" if marker else ""
    script.write_text(f"#!/bin/sh\n{note}printf '{output}'\n")
    script.chmod(0o755)
    return [str(script)]


def build_collector(client, docker_command):
    return Collector(client=client, docker_command=docker_command)


def configuration_from(text):
    return parse_configuration(textwrap.dedent(text))


def window_of(client):
    return client.list_panes()[0].window_identifier


class TestPanesAndProcesses:
    def test_includes_the_panes_of_the_server(self, tmux_client, tmp_path):
        collector = build_collector(tmux_client, write_fake_docker(tmp_path))
        snapshot = collect_snapshot(collector, default_configuration(), window_of(tmux_client))
        assert [pane.session_name for pane in snapshot.panes] == ["main"]
        assert snapshot.window_identifier == window_of(tmux_client)

    def test_includes_the_process_table_with_this_test_process(self, tmux_client, tmp_path):
        collector = build_collector(tmux_client, write_fake_docker(tmp_path))
        snapshot = collect_snapshot(collector, default_configuration(), window_of(tmux_client))
        assert os.getpid() in snapshot.process_table


class TestContainers:
    def test_includes_the_containers_that_docker_lists(self, tmux_client, tmp_path):
        collector = build_collector(tmux_client, write_fake_docker(tmp_path))
        snapshot = collect_snapshot(collector, default_configuration(), window_of(tmux_client))
        assert [container.name for container in snapshot.containers] == ["shop-web-1"]

    def test_a_docker_that_fails_gives_no_containers(self, tmux_client):
        collector = build_collector(tmux_client, ["false"])
        snapshot = collect_snapshot(collector, default_configuration(), window_of(tmux_client))
        assert snapshot.containers == []

    def test_docker_is_not_run_when_no_section_needs_containers(self, tmux_client, tmp_path):
        marker = tmp_path / "docker-was-run"
        collector = build_collector(tmux_client, write_fake_docker(tmp_path, marker=marker))
        configuration = configuration_from('[[sections]]\ntype = "panes"\n')
        snapshot = collect_snapshot(collector, configuration, window_of(tmux_client))
        assert snapshot.containers == []
        assert not marker.exists()

    def test_docker_is_run_for_a_section_of_other_services(self, tmux_client, tmp_path):
        marker = tmp_path / "docker-was-run"
        collector = build_collector(tmux_client, write_fake_docker(tmp_path, marker=marker))
        configuration = configuration_from('[[sections]]\ntype = "other-services"\n')
        collect_snapshot(collector, configuration, window_of(tmux_client))
        assert marker.exists()


class TestCustomSections:
    CONFIGURATION = """
        [[sections]]
        type = "custom"
        identifier = "ports"
        command = ["printf", "8000 api\\n8001 web\\n"]
        """

    def test_runs_the_command_of_a_custom_section(self, tmux_client, tmp_path):
        collector = build_collector(tmux_client, write_fake_docker(tmp_path))
        configuration = configuration_from(self.CONFIGURATION)
        snapshot = collect_snapshot(collector, configuration, window_of(tmux_client))
        assert snapshot.custom_outputs == {"ports": "8000 api\n8001 web\n"}

    def test_a_disabled_custom_section_is_not_run(self, tmux_client, tmp_path):
        collector = build_collector(tmux_client, write_fake_docker(tmp_path))
        configuration = configuration_from(self.CONFIGURATION + "        enabled = false\n")
        snapshot = collect_snapshot(collector, configuration, window_of(tmux_client))
        assert snapshot.custom_outputs == {}

    def test_a_command_that_fails_gives_an_empty_output(self, tmux_client, tmp_path):
        collector = build_collector(tmux_client, write_fake_docker(tmp_path))
        configuration = configuration_from(self.CONFIGURATION.replace('"printf"', '"false"'))
        snapshot = collect_snapshot(collector, configuration, window_of(tmux_client))
        assert snapshot.custom_outputs == {"ports": ""}


class TestZombieDirectories:
    def test_reads_the_folder_of_an_agent_that_no_pane_shows(self, tmux_client, tmp_path):
        program = install_fake_agent(tmp_path)
        working_folder = tmp_path / "shop"
        working_folder.mkdir()
        process = subprocess.Popen(
            [str(program), "30"],
            cwd=working_folder,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            collector = build_collector(tmux_client, write_fake_docker(tmp_path))
            snapshot = collect_snapshot(collector, default_configuration(), window_of(tmux_client))
            assert snapshot.process_directories[process.pid] == str(working_folder)
        finally:
            process.kill()
            process.wait()

    def test_reads_no_folders_when_there_is_no_zombies_section(self, tmux_client, tmp_path):
        collector = build_collector(tmux_client, write_fake_docker(tmp_path))
        configuration = configuration_from('[[sections]]\ntype = "panes"\n')
        snapshot = collect_snapshot(collector, configuration, window_of(tmux_client))
        assert snapshot.process_directories == {}

    def test_the_fake_agent_program_exists(self, tmp_path):
        assert shutil.which("sleep") is not None
        assert install_fake_agent(tmp_path).exists()
