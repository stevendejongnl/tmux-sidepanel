"""The JSON that the commands for programs print: a result, or an error with a code."""

import json

from tmux_sidepanel.agent_output import AgentCommandError, error_text, result_text


def test_a_result_is_wrapped_in_a_result_key():
    assert json.loads(result_text({"pane_id": "%1"})) == {"result": {"pane_id": "%1"}}


def test_a_result_can_be_a_list():
    assert json.loads(result_text([1, 2])) == {"result": [1, 2]}


def test_an_error_has_a_code_and_a_message():
    error = AgentCommandError("pane_not_found", "no pane %9")
    assert json.loads(error_text(error)) == {
        "error": {"code": "pane_not_found", "message": "no pane %9"}
    }


def test_the_error_is_an_exception_with_the_message():
    assert str(AgentCommandError("code", "the message")) == "the message"
