"""Cognitive complexity: every function stays small enough to read at a glance."""

import shutil
import textwrap

from tests.conftest import PROJECT_ROOT, run_command

COMPLEXITY_TOOL = shutil.which("complexipy", path=str(PROJECT_ROOT / ".venv" / "bin"))
MEASURED_FOLDERS = ["src", "devtools", "tests"]

SIMPLE_FUNCTION = """
def add(first, second):
    return first + second
"""

TANGLED_FUNCTION = """
def tangled(items):
    total = 0
    for item in items:
        if item > 0:
            for factor in range(3):
                if factor % 2:
                    total += item * factor
    return total
"""


def measure_source(directory, source):
    """Run the tool in a folder that carries this project's configuration and one module."""
    (directory / "pyproject.toml").write_text((PROJECT_ROOT / "pyproject.toml").read_text())
    (directory / "module.py").write_text(textwrap.dedent(source))
    return run_command([COMPLEXITY_TOOL, "module.py", "--plain"], directory=directory)


def test_the_tool_is_installed():
    assert COMPLEXITY_TOOL is not None


def test_the_project_stays_within_the_limit():
    command = [COMPLEXITY_TOOL, *MEASURED_FOLDERS, "--plain"]
    result = run_command(command, directory=PROJECT_ROOT)
    assert result.returncode == 0, result.stdout + result.stderr


def test_a_simple_function_passes(tmp_path):
    assert measure_source(tmp_path, SIMPLE_FUNCTION).returncode == 0


def test_a_tangled_function_fails_under_the_limit_of_the_project(tmp_path):
    result = measure_source(tmp_path, TANGLED_FUNCTION)
    assert result.returncode != 0
    assert "tangled" in result.stdout + result.stderr
