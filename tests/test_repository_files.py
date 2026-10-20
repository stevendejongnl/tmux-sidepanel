"""The files that GitHub reads: who owns the code and how to report a security problem."""

from tests.conftest import PROJECT_ROOT

CODEOWNERS_PATH = PROJECT_ROOT / ".github" / "CODEOWNERS"
SECURITY_PATH = PROJECT_ROOT / "SECURITY.md"
OWNER = "@stevendejongnl"


def test_the_owner_owns_everything():
    lines = CODEOWNERS_PATH.read_text(encoding="ascii").splitlines()
    assert f"* {OWNER}" in lines


def test_the_workflows_and_the_hooks_need_the_owner_as_well():
    text = CODEOWNERS_PATH.read_text(encoding="ascii")
    assert f"/.github/ {OWNER}" in text
    assert f"/hooks/ {OWNER}" in text


def test_security_says_how_to_report_privately():
    text = SECURITY_PATH.read_text(encoding="ascii")
    assert "private vulnerability reporting" in text.lower()
    assert "do not open a public issue" in text.lower()


def test_security_names_the_supported_version():
    assert "latest release" in SECURITY_PATH.read_text(encoding="ascii").lower()


CONTRIBUTING_PATH = PROJECT_ROOT / "CONTRIBUTING.md"


def test_contributing_explains_how_to_run_the_checks():
    text = CONTRIBUTING_PATH.read_text(encoding="ascii")
    for command in ["uv run pytest", "uv run ruff check .", "uv run complexipy"]:
        assert command in text


def test_contributing_names_the_commit_style():
    assert "Conventional Commits" in CONTRIBUTING_PATH.read_text(encoding="ascii")


def test_contributing_points_to_the_security_policy():
    assert "SECURITY.md" in CONTRIBUTING_PATH.read_text(encoding="ascii")


def test_contributing_makes_no_promises():
    text = CONTRIBUTING_PATH.read_text(encoding="ascii").lower()
    assert "within" not in text
    assert "we will" not in text
