"""Process table: the output of ps parsed into Process objects."""

from tmux_sidepanel.process_table import PROCESS_LIST_COMMAND, parse_process_table
from tmux_sidepanel.processes import Process

SAMPLE = """\
      1       0 ?        Ss       86400 /sbin/init
   1234     777 pts/3    Sl+       3600 /opt/bin/claude --resume abc-123
  99999    1234 ?        S           12 python3 -c import time; time.sleep(5)
"""


def test_the_command_asks_for_the_columns_the_parser_reads():
    assert PROCESS_LIST_COMMAND == ("ps", "-eo", "pid=,ppid=,tty=,stat=,etimes=,args=")


def test_parses_a_line_into_a_process():
    table = parse_process_table(SAMPLE)
    assert table[1234] == Process(
        process_identifier=1234,
        parent_process_identifier=777,
        terminal="pts/3",
        status_flags="Sl+",
        age_seconds=3600,
        arguments="/opt/bin/claude --resume abc-123",
    )


def test_reads_every_line_and_keys_them_by_process_identifier():
    assert sorted(parse_process_table(SAMPLE)) == [1, 1234, 99999]


def test_a_process_without_a_terminal_keeps_the_question_mark():
    assert parse_process_table(SAMPLE)[1].terminal == "?"


def test_arguments_keep_their_spaces():
    assert parse_process_table(SAMPLE)[99999].arguments == "python3 -c import time; time.sleep(5)"


def test_lines_that_do_not_fit_are_skipped():
    output = "garbage\n" + SAMPLE + "12 34\n\n"
    assert sorted(parse_process_table(output)) == [1, 1234, 99999]


def test_empty_output_gives_an_empty_table():
    assert parse_process_table("") == {}


def test_a_process_with_empty_arguments_is_still_listed():
    table = parse_process_table("  42       1 ?        Z            5 \n")
    assert table[42].arguments == ""
