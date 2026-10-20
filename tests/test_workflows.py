"""Policy tests for the GitHub Actions files: pinned, least privilege, no risky triggers."""

import re
from itertools import chain

import pytest
import yaml

from tests.conftest import PROJECT_ROOT

WORKFLOWS_DIRECTORY = PROJECT_ROOT / ".github" / "workflows"
COMMIT_HASH_PATTERN = re.compile(r"^[0-9a-f]{40}$")
UNTRUSTED_FIELDS = (
    "github.event.pull_request.title",
    "github.event.head_commit.message",
    "github.head_ref",
    "github.event.issue.title",
)


def load_workflow(path):
    return yaml.safe_load(path.read_text())


def workflow_triggers(workflow):
    # YAML 1.1 reads the key "on" as the boolean True.
    return workflow.get("on", workflow.get(True))


def workflow_paths():
    return sorted(WORKFLOWS_DIRECTORY.glob("*.yml"))


def all_steps(workflow):
    steps_per_job = (job.get("steps", []) for job in workflow["jobs"].values())
    return list(chain.from_iterable(steps_per_job))


def is_action_step(step):
    return "uses" in step


def action_steps(workflow):
    return list(filter(is_action_step, all_steps(workflow)))


def action_reference(step):
    return step["uses"].partition("@")[2]


def is_unpinned(step):
    return not COMMIT_HASH_PATTERN.match(action_reference(step))


def is_checkout_step(step):
    return step.get("uses", "").startswith("actions/checkout")


def keeps_credentials(step):
    return step.get("with", {}).get("persist-credentials", True)


def checkout_steps(job):
    return list(filter(is_checkout_step, job["steps"]))


def credentials_kept_after_checkout(job):
    return list(map(keeps_credentials, checkout_steps(job)))


def checkout_credentials_by_job(workflow):
    jobs = workflow["jobs"]
    return {name: credentials_kept_after_checkout(job) for name, job in jobs.items()}


def permissions_by_job(workflow):
    return {name: job.get("permissions") for name, job in workflow["jobs"].items()}


def jobs_without_timeout(workflow):
    jobs = workflow["jobs"]
    return list(filter(lambda name: "timeout-minutes" not in jobs[name], jobs))


def used_secrets(path):
    return set(re.findall(r"secrets\.([A-Za-z0-9_]+)", path.read_text()))


def untrusted_fields_in_scripts(path):
    text = path.read_text()
    return list(filter(lambda field: "${{ " + field in text, UNTRUSTED_FIELDS))


def run_commands(job):
    return [step.get("run", "") for step in job["steps"]]


def test_a_ci_workflow_exists():
    assert (WORKFLOWS_DIRECTORY / "ci.yml").exists()


@pytest.mark.parametrize("path", workflow_paths(), ids=lambda path: path.name)
class TestEveryWorkflow:
    def test_actions_are_pinned_to_a_full_commit_hash(self, path):
        unpinned = [step["uses"] for step in filter(is_unpinned, action_steps(load_workflow(path)))]
        assert unpinned == []

    def test_the_default_token_is_read_only(self, path):
        assert load_workflow(path)["permissions"] == {"contents": "read"}

    def test_every_job_has_a_timeout(self, path):
        assert jobs_without_timeout(load_workflow(path)) == []

    def test_no_pull_request_target_trigger(self, path):
        assert "pull_request_target" not in workflow_triggers(load_workflow(path))

    def test_no_secret_other_than_the_default_token(self, path):
        assert used_secrets(path) <= {"GITHUB_TOKEN"}

    def test_no_untrusted_text_is_put_into_a_script(self, path):
        assert untrusted_fields_in_scripts(path) == []


class TestCi:
    @pytest.fixture
    def workflow(self):
        return load_workflow(WORKFLOWS_DIRECTORY / "ci.yml")

    def test_runs_on_pushes_to_main_and_on_pull_requests(self, workflow):
        triggers = workflow_triggers(workflow)
        assert triggers["push"]["branches"] == ["main"]
        assert "pull_request" in triggers

    def test_the_lint_job_checks_the_complexity(self, workflow):
        commands = "\n".join(run_commands(workflow["jobs"]["lint"]))
        assert "uv run complexipy" in commands

    def test_only_the_release_job_keeps_the_token_after_checkout(self, workflow):
        assert checkout_credentials_by_job(workflow) == {
            "test": [False],
            "lint": [False],
            "release": [True],
        }

    def test_only_the_release_job_can_write(self, workflow):
        assert permissions_by_job(workflow) == {
            "test": None,
            "lint": None,
            "release": {"contents": "write"},
        }

    def test_the_release_job_waits_for_the_checks(self, workflow):
        assert set(workflow["jobs"]["release"]["needs"]) == {"test", "lint"}

    def test_the_release_job_runs_only_for_pushes_to_main(self, workflow):
        condition = workflow["jobs"]["release"]["if"]
        assert "refs/heads/main" in condition
        assert "push" in condition

    def test_releases_do_not_overlap(self, workflow):
        assert workflow["jobs"]["release"]["concurrency"]["cancel-in-progress"] is False

    def test_the_release_creates_a_tag_without_a_version_commit(self):
        text = (WORKFLOWS_DIRECTORY / "ci.yml").read_text()
        assert "semantic-release" in text
        assert "--no-commit" in text
        assert "python-semantic-release/python-semantic-release@" not in text
