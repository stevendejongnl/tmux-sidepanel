"""Quoting text for tmux, checked with the real tmux parser."""

import pytest

from tests.tmux_support import tmux_is_installed
from tmux_sidepanel.tmux_syntax import escape_for_format, quote_for_tmux

AWKWARD_TEXTS = [
    "plain",
    "two words",
    "it's",
    'say "hi"',
    "back\\slash",
    "$HOME and ${name}",
    "semi;colon",
    "hash#tag",
    "brace {x}",
    "tilde ~ and * star",
    "caf" + chr(0xE9),
]


class TestQuote:
    def test_wraps_the_text_in_double_quotes(self):
        assert quote_for_tmux("plain") == '"plain"'

    def test_escapes_the_characters_that_have_a_meaning(self):
        assert quote_for_tmux('a"b\\c$d') == '"a\\"b\\\\c\\$d"'

    @pytest.mark.parametrize("text", ["line\nbreak", "tab\there", "bell\a"])
    def test_refuses_control_characters(self, text):
        with pytest.raises(ValueError, match="control"):
            quote_for_tmux(text)

    @pytest.mark.skipif(not tmux_is_installed(), reason="tmux is not installed")
    @pytest.mark.parametrize("text", AWKWARD_TEXTS)
    def test_the_text_survives_the_parser_of_tmux(self, tmux_client, tmp_path, text):
        script = tmp_path / "probe.conf"
        script.write_text(f"set-option -g @probe {quote_for_tmux(text)}\n")
        tmux_client.run("source-file", str(script))
        assert tmux_client.run("show-option", "-gv", "@probe").rstrip("\n") == text


class TestEscapeForFormat:
    def test_doubles_the_hash(self):
        assert escape_for_format("a#b#{c}") == "a##b##{c}"

    def test_leaves_other_text_alone(self):
        assert escape_for_format("plain text") == "plain text"
