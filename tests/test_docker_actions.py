"""Talking to docker: safe names, starting a command in the background, and the logs command."""

import pytest

from tests.fake_docker import install_fake_docker
from tmux_sidepanel.docker_actions import (
    UnsafeNameError,
    logs_command,
    require_safe_names,
    start_docker,
)


class TestSafeNames:
    @pytest.mark.parametrize("name", ["shop-web-1", "a", "a_b.c-d", "Shop1", "9lives"])
    def test_accepts_the_names_docker_allows(self, name):
        require_safe_names([name])

    @pytest.mark.parametrize(
        "name", ["", "-rf", "--all", "a b", "a;b", "a$(x)", "a`x`", "a/b", "a\nb", "-", ".hidden"]
    )
    def test_refuses_anything_else(self, name):
        with pytest.raises(UnsafeNameError):
            require_safe_names([name])

    def test_one_bad_name_among_good_ones_is_enough(self):
        with pytest.raises(UnsafeNameError):
            require_safe_names(["good-1", "bad name"])

    def test_no_names_is_fine(self):
        require_safe_names([])


class TestStartDocker:
    def test_runs_the_program_with_the_arguments(self, tmp_path):
        fake = install_fake_docker(tmp_path)
        assert start_docker(str(fake.program), ["stop", "shop-web-1", "shop-web-2"]) is True
        assert fake.wait_for_calls() == ["stop shop-web-1 shop-web-2"]

    def test_a_program_that_is_missing_gives_false_and_no_error(self):
        assert start_docker("/no/such/docker", ["stop", "x"]) is False


class TestLogsCommand:
    def test_one_container_shows_its_own_logs(self):
        command = logs_command("docker", ("shop-web-1",), project="")
        assert command == "docker logs -f --tail 200 shop-web-1"

    def test_a_project_with_several_containers_shows_the_logs_of_the_project(self):
        command = logs_command("docker", ("a-1", "a-2"), project="shop")
        assert command == "docker compose -p shop logs -f --tail 100"

    def test_a_single_container_of_a_project_still_shows_its_own_logs(self):
        command = logs_command("docker", ("shop-web-1",), project="shop")
        assert command == "docker logs -f --tail 200 shop-web-1"

    def test_a_program_path_with_a_space_is_quoted(self):
        command = logs_command("/opt/my docker/docker", ("a-1",), project="")
        assert command.startswith("'/opt/my docker/docker' logs")

    def test_a_project_with_odd_characters_is_refused(self):
        with pytest.raises(UnsafeNameError):
            logs_command("docker", ("a-1", "a-2"), project="x; rm -rf /")

    def test_a_container_name_with_odd_characters_is_refused(self):
        with pytest.raises(UnsafeNameError):
            logs_command("docker", ("a b",), project="")
