"""Commit message style: conventional header, line lengths, no emoji."""

import pytest

from devtools.commitlint import check_message, main

GOOD = "feat(panes): add the pane section\n\nShow every pane of the current window.\n"


def test_accepts_a_conventional_message():
    assert check_message(GOOD) == []


def test_accepts_a_header_only_message():
    assert check_message("fix: close the menu on escape\n") == []


@pytest.mark.parametrize(
    "header",
    [
        "Add pane section",
        "feature: add pane section",
        "feat add pane section",
        "feat(): add pane section",
        "FEAT: add pane section",
        "feat:add pane section",
    ],
)
def test_rejects_a_header_that_is_not_conventional(header):
    assert check_message(header + "\n")


def test_rejects_a_header_longer_than_72_characters():
    assert check_message("feat: " + "x" * 70 + "\n")


def test_accepts_a_header_of_exactly_72_characters():
    assert check_message("feat: " + "x" * 66 + "\n") == []


def test_rejects_a_trailing_period_in_the_header():
    assert check_message("feat: add the pane section.\n")


def test_requires_a_blank_line_after_the_header():
    assert check_message("feat: add the pane section\nbody starts too early\n")


def test_rejects_a_body_line_longer_than_72_characters():
    assert check_message("feat: add it\n\n" + "word " * 20 + "\n")


def test_allows_a_long_url_line_in_the_body():
    url = "https://example.org/" + "a" * 90
    assert check_message(f"feat: add it\n\nSee {url}\n") == []


def test_rejects_emoji():
    assert check_message("feat: add the menu \U0001f680\n")


def test_ignores_comment_lines_like_git_does():
    message = "feat: add it\n\n# this line would be far too long to pass " + "x" * 60 + "\n"
    assert check_message(message) == []


def test_reports_every_problem_not_only_the_first():
    problems = check_message("Add it.\nbody starts too early\n")
    assert len(problems) >= 3


def test_main_returns_zero_for_a_good_message(tmp_path):
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text(GOOD)
    assert main([str(path)]) == 0


def test_main_returns_one_and_explains_on_stderr(tmp_path, capsys):
    path = tmp_path / "COMMIT_EDITMSG"
    path.write_text("Add it.\n")
    assert main([str(path)]) == 1
    assert "header" in capsys.readouterr().err.lower()


def test_main_needs_a_path(capsys):
    assert main([]) == 2
    assert "usage" in capsys.readouterr().err.lower()
