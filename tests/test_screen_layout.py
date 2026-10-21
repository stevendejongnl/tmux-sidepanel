"""Fitting the lines of the panel and the footer on a screen of a given height."""

from tmux_sidepanel.panel_layout import NO_SELECTION, Line
from tmux_sidepanel.screen_layout import compose_screen, line_of_selection


def body_line(text, selection_index=NO_SELECTION):
    return Line(text, "row", "", False, selection_index)


def footer_line(text):
    return Line(text, "notice", "", False, NO_SELECTION)


def texts(lines):
    return [line.text for line in lines]


def numbered(count):
    return [body_line(f"line {number}", number) for number in range(count)]


class TestLineOfSelection:
    def test_finds_the_line_that_holds_the_selected_row(self):
        lines = [body_line("title"), body_line("a", 0), body_line("b", 1)]
        assert line_of_selection(lines, 1) == 2

    def test_without_a_matching_row_it_is_the_first_line(self):
        assert line_of_selection([body_line("title")], 0) == 0


class TestComposeScreen:
    def test_everything_that_fits_is_shown_in_order(self):
        screen = compose_screen(numbered(3), [footer_line("note")], 4, 0)
        assert texts(screen) == ["line 0", "line 1", "line 2", "note"]

    def test_a_short_body_leaves_blank_lines_so_the_footer_is_at_the_bottom(self):
        screen = compose_screen(numbered(2), [footer_line("note")], 5, 0)
        assert texts(screen) == ["line 0", "line 1", "", "", "note"]
        assert [line.kind for line in screen[2:4]] == ["blank", "blank"]

    def test_a_screen_without_a_footer_is_not_padded(self):
        assert texts(compose_screen(numbered(2), [], 5, 0)) == ["line 0", "line 1"]

    def test_the_footer_stays_at_the_bottom_and_the_body_gives_way(self):
        screen = compose_screen(numbered(10), [footer_line("note")], 5, 0)
        assert texts(screen) == ["line 0", "line 1", "line 2", "line 3", "note"]

    def test_the_body_scrolls_to_keep_the_selected_line_visible(self):
        screen = compose_screen(numbered(10), [footer_line("note")], 5, 7)
        assert texts(screen) == ["line 4", "line 5", "line 6", "line 7", "note"]

    def test_the_last_lines_are_shown_when_the_selection_is_at_the_end(self):
        screen = compose_screen(numbered(10), [], 4, 9)
        assert texts(screen) == ["line 6", "line 7", "line 8", "line 9"]

    def test_a_footer_taller_than_the_screen_is_cut_to_fit(self):
        footer = [footer_line(f"item {number}") for number in range(6)]
        screen = compose_screen(numbered(3), footer, 4, 0)
        assert texts(screen) == ["item 0", "item 1", "item 2", "item 3"]

    def test_a_screen_without_height_shows_nothing(self):
        assert compose_screen(numbered(3), [footer_line("note")], 0, 0) == []
