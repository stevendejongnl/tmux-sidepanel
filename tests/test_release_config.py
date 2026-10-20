"""Semantic versioning: the release tool reads the commit messages and picks the next version."""

import shutil
import tomllib

import pytest

from tests.conftest import PROJECT_ROOT, add_commit, add_tag, run_command

RELEASE_TOOL = shutil.which("semantic-release", path=str(PROJECT_ROOT / ".venv" / "bin"))


def release_configuration():
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text())
    return project["tool"]["semantic_release"]


def next_version(repository):
    result = run_command([RELEASE_TOOL, "--noop", "version", "--print"], directory=repository)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()[-1]


def test_tags_look_like_v1_2_3():
    assert release_configuration()["tag_format"] == "v{version}"


def test_releases_come_from_main_only():
    assert release_configuration()["branches"]["main"]["match"] == "main"


def test_commits_are_read_as_conventional_commits():
    assert release_configuration()["commit_parser"] == "conventional"


def test_a_breaking_change_below_1_0_bumps_the_minor_version():
    assert release_configuration()["allow_zero_version"] is True
    assert release_configuration()["major_on_zero"] is False


def test_no_files_are_built_or_changed_by_a_release():
    assert release_configuration().get("build_command", "") == ""


@pytest.mark.skipif(RELEASE_TOOL is None, reason="semantic-release is not installed")
class TestNextVersion:
    def test_the_first_feature_gives_0_1_0(self, release_repository):
        add_commit(release_repository, "feat: add the pane section")
        assert next_version(release_repository) == "0.1.0"

    def test_a_fix_gives_a_patch_release(self, release_repository):
        add_commit(release_repository, "feat: add the pane section")
        add_tag(release_repository, "v0.1.0")
        add_commit(release_repository, "fix: close the menu on escape")
        assert next_version(release_repository) == "0.1.1"

    def test_a_feature_gives_a_minor_release(self, release_repository):
        add_commit(release_repository, "feat: add the pane section")
        add_tag(release_repository, "v0.1.0")
        add_commit(release_repository, "feat: add the service section")
        assert next_version(release_repository) == "0.2.0"

    def test_a_breaking_change_below_1_0_gives_a_minor_release(self, release_repository):
        add_commit(release_repository, "feat: add the pane section")
        add_tag(release_repository, "v0.1.0")
        add_commit(release_repository, "feat!: rename the configuration file")
        assert next_version(release_repository) == "0.2.0"

    def test_a_breaking_change_from_1_0_gives_a_major_release(self, release_repository):
        add_commit(release_repository, "feat: add the pane section")
        add_tag(release_repository, "v1.0.0")
        add_commit(release_repository, "feat!: rename the configuration file")
        assert next_version(release_repository) == "2.0.0"

    def test_a_breaking_change_footer_gives_a_major_release(self, release_repository):
        add_commit(release_repository, "feat: add the pane section")
        add_tag(release_repository, "v1.0.0")
        add_commit(
            release_repository, "fix: change the default key\n\nBREAKING CHANGE: the key moved"
        )
        assert next_version(release_repository) == "2.0.0"

    def test_docs_and_chores_do_not_release(self, release_repository):
        add_commit(release_repository, "feat: add the pane section")
        add_tag(release_repository, "v1.0.0")
        add_commit(release_repository, "docs: explain the configuration file")
        add_commit(release_repository, "chore: update the lock file")
        assert next_version(release_repository) == "1.0.0"
