"""Policy tests for the dependency update configuration."""

import yaml

from tests.conftest import PROJECT_ROOT


class TestDependabot:
    def config(self):
        return yaml.safe_load((PROJECT_ROOT / ".github" / "dependabot.yml").read_text())

    def test_keeps_actions_and_python_dependencies_current(self):
        ecosystems = {entry["package-ecosystem"] for entry in self.config()["updates"]}
        assert {"github-actions", "uv"} <= ecosystems

    def test_checks_every_week(self):
        for entry in self.config()["updates"]:
            assert entry["schedule"]["interval"] == "weekly"
