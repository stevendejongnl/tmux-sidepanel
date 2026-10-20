"""Shared helpers: git runs with an isolated configuration, no signing and no network."""

import os
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def build_environment(**overrides):
    environment = {
        "PATH": os.environ["PATH"],
        "HOME": "/nonexistent-home",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.org",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.org",
    }
    environment.update(overrides)
    return environment


def run_command(command, directory=None, **overrides):
    return subprocess.run(
        [str(part) for part in command],
        cwd=directory,
        text=True,
        capture_output=True,
        env=build_environment(**overrides),
        check=False,
    )


def run_git(repository, *arguments):
    result = run_command(["git", "-c", "commit.gpgsign=false", *arguments], directory=repository)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


@pytest.fixture
def release_repository(tmp_path):
    """A throwaway repository that carries this project's pyproject.toml."""
    repository = tmp_path / "repository"
    repository.mkdir()
    run_git(repository, "init", "-q", "-b", "main")
    # The release tool asks for the remote even when it only prints the next version.
    run_git(repository, "remote", "add", "origin", "https://github.com/example/example.git")
    (repository / "pyproject.toml").write_text((PROJECT_ROOT / "pyproject.toml").read_text())
    run_git(repository, "add", "pyproject.toml")
    run_git(repository, "commit", "-q", "-m", "chore: start")
    return repository


def add_commit(repository, message):
    log_file = repository / "log.txt"
    with log_file.open("a") as handle:
        handle.write(message + "\n")
    run_git(repository, "add", "log.txt")
    run_git(repository, "commit", "-q", "-m", message)


def add_tag(repository, name):
    run_git(repository, "tag", name)
