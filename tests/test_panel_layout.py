"""The lines of the panel: titles, rows, empty texts, clipping and the rows that can be selected."""

import pytest

from tmux_sidepanel.panel_layout import (
    NO_SELECTION,
    Line,
    SelectableRow,
    build_lines,
    clip_start,
    clip_text,
    header_lines,
    selectable_rows,
)
from tmux_sidepanel.rows import PanelView, Row, SectionView


def build_section(identifier, rows=(), empty_text="nothing here"):
    return SectionView(identifier, "panes", identifier.upper(), empty_text, tuple(rows))


def build_row(text, state="", is_active=False):
    return Row(text, state, is_active, f"subject of {text}")


class TestClipText:
    def test_short_text_is_kept(self):
        assert clip_text("abc", 10) == "abc"

    def test_text_of_exactly_the_width_is_kept(self):
        assert clip_text("abcde", 5) == "abcde"

    def test_long_text_ends_in_dots_within_the_width(self):
        assert clip_text("abcdefghij", 6) == "abc..."

    @pytest.mark.parametrize(("width", "expected"), [(3, "abc"), (2, "ab"), (1, "a"), (0, "")])
    def test_a_very_narrow_width_cuts_without_dots(self, width, expected):
        assert clip_text("abcdefghij", width) == expected


class TestSelectableRows:
    def test_lists_the_rows_of_all_sections_in_order(self):
        first = build_row("one")
        second = build_row("two")
        panel = PanelView((build_section("a", [first]), build_section("b", [second])))
        assert selectable_rows(panel) == [
            SelectableRow("a", first),
            SelectableRow("b", second),
        ]

    def test_a_panel_without_rows_has_nothing_to_select(self):
        assert selectable_rows(PanelView((build_section("a"),))) == []


class TestBuildLines:
    def test_a_section_is_a_title_followed_by_its_rows(self):
        panel = PanelView((build_section("a", [build_row("~ claude", "working")]),))
        lines = build_lines(panel, 40)
        assert [(line.kind, line.text) for line in lines] == [
            ("title", "A"),
            ("row", "  ~ claude"),
        ]

    def test_a_row_line_keeps_its_state_and_focus(self):
        panel = PanelView((build_section("a", [build_row("x", "blocked", True)]),))
        line = build_lines(panel, 40)[1]
        assert (line.state, line.is_active) == ("blocked", True)

    def test_an_empty_section_shows_its_empty_text(self):
        lines = build_lines(PanelView((build_section("a"),)), 40)
        assert [(line.kind, line.text) for line in lines] == [
            ("title", "A"),
            ("empty", "  nothing here"),
        ]

    def test_rows_are_numbered_for_the_selection_across_sections(self):
        panel = PanelView(
            (
                build_section("a", [build_row("one"), build_row("two")]),
                build_section("b", [build_row("three")]),
            )
        )
        indexes = [line.selection_index for line in build_lines(panel, 40)]
        assert indexes == [-1, 0, 1, -1, -1, 2]

    def test_a_blank_line_separates_the_sections(self):
        panel = PanelView(
            (
                build_section("a", [build_row("one")]),
                build_section("b", [build_row("two")]),
                build_section("c"),
            )
        )
        assert [(line.kind, line.text) for line in build_lines(panel, 40)] == [
            ("title", "A"),
            ("row", "  one"),
            ("blank", ""),
            ("title", "B"),
            ("row", "  two"),
            ("blank", ""),
            ("title", "C"),
            ("empty", "  nothing here"),
        ]

    def test_lines_are_clipped_to_the_width(self):
        panel = PanelView((build_section("a", [build_row("x" * 50)]),))
        assert all(len(line.text) <= 20 for line in build_lines(panel, 20))

    def test_title_and_row_lines_carry_the_type_of_their_section(self):
        section = SectionView("a", "services", "A", "none", (build_row("one"),))
        lines = build_lines(PanelView((section,)), 40)
        assert [line.section_type for line in lines] == ["services", "services"]

    def test_a_blank_line_belongs_to_no_section(self):
        panel = PanelView((build_section("a", [build_row("one")]), build_section("b")))
        assert build_lines(panel, 40)[2].section_type == ""

    def test_a_line_is_a_plain_value(self):
        assert Line("t", "title", "", False, -1) == Line("t", "title", "", False, -1)


class TestClipStart:
    def test_short_text_is_kept(self):
        assert clip_start("~/project", 20) == "~/project"

    def test_long_text_keeps_its_end_within_the_width(self):
        assert clip_start("/srv/apps/shop-api", 10) == "...hop-api"

    @pytest.mark.parametrize(("width", "expected"), [(3, "api"), (1, "i"), (0, ""), (-1, "")])
    def test_a_very_narrow_width_cuts_without_dots(self, width, expected):
        assert clip_start("shop-api", width) == expected


class TestHeaderLines:
    def test_the_directory_is_a_line_that_cannot_be_selected_with_a_blank_after_it(self):
        lines = header_lines(PanelView((), directory="/srv/apps/shop-api"), 10)
        assert [(line.text, line.kind) for line in lines] == [
            ("...hop-api", "header"),
            ("", "blank"),
        ]
        assert lines[0].selection_index == NO_SELECTION

    def test_without_a_directory_there_is_no_header(self):
        assert header_lines(PanelView(()), 10) == []
