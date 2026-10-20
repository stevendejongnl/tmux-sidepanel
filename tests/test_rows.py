"""Rows and views: the marks of the states and the formatting of a row."""

import pytest

from tmux_sidepanel.rows import PanelView, Row, SectionView, format_row, state_mark


@pytest.mark.parametrize(
    ("state", "mark"),
    [
        ("blocked", "!"),
        ("done", "+"),
        ("working", "~"),
        ("idle", "."),
        ("unknown", "?"),
        ("", " "),
        ("bogus", " "),
    ],
)
def test_state_mark(state, mark):
    assert state_mark(state) == mark


class TestFormatRow:
    def test_fills_the_placeholders(self):
        assert format_row("{mark} {label}", {"mark": "~", "label": "claude"}) == "~ claude"

    def test_collapses_the_gaps_that_empty_values_leave(self):
        fields = {"letter": "D", "command": "", "age": "6h"}
        assert format_row("{letter} {command} {age}", fields) == "D 6h"

    def test_strips_the_ends(self):
        assert format_row("{mark} {label}", {"mark": " ", "label": "zsh"}) == "zsh"

    def test_makes_the_values_safe_for_the_terminal(self):
        text = format_row("{label}", {"label": "\x1b[31mred"})
        assert "\x1b" not in text

    def test_keeps_literal_text_around_the_placeholders(self):
        assert format_row("[{label}]", {"label": "x"}) == "[x]"

    def test_braces_in_a_value_are_not_read_as_placeholders(self):
        assert format_row("{label}", {"label": "{mark}"}) == "{mark}"


class TestViews:
    def test_a_row_carries_text_state_focus_and_its_subject(self):
        row = Row("~ claude", "working", True, "subject")
        assert (row.text, row.state, row.is_active, row.subject) == (
            "~ claude",
            "working",
            True,
            "subject",
        )

    def test_a_section_view_lists_its_rows(self):
        rows = (Row("a", "", False, None), Row("b", "", False, None))
        view = SectionView("panes", "panes", "PANES", "none", rows)
        assert view.is_empty is False
        assert SectionView("panes", "panes", "PANES", "none", ()).is_empty is True

    def test_a_panel_view_lists_its_sections(self):
        view = SectionView("panes", "panes", "PANES", "none", ())
        assert PanelView((view,)).sections == (view,)
