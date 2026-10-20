"""The license: one text, and the same identifier everywhere it is named."""

import json
import tomllib

from tests.conftest import PROJECT_ROOT

IDENTIFIER = "AGPL-3.0-or-later"
LICENSE_PATH = PROJECT_ROOT / "LICENSE"
MANIFEST_PATH = PROJECT_ROOT / ".claude-plugin" / "plugin.json"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"


def test_the_license_file_is_the_agpl_version_3():
    text = LICENSE_PATH.read_text(encoding="ascii")
    assert text.lstrip().startswith("GNU AFFERO GENERAL PUBLIC LICENSE")
    assert "Version 3, 19 November 2007" in text


def test_the_license_file_is_the_complete_text():
    text = LICENSE_PATH.read_text(encoding="ascii")
    assert "END OF TERMS AND CONDITIONS" in text
    assert "Remote Network Interaction" in text


def test_the_project_names_the_license():
    project = tomllib.loads(PYPROJECT_PATH.read_text())["project"]
    assert project["license"] == IDENTIFIER


def test_the_plugin_manifest_names_the_same_license():
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert manifest["license"] == IDENTIFIER
