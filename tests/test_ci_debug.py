import subprocess

import pytest

from tests.tmux_support import install_fake_agent, wait_for_program
from tmux_sidepanel.command_runner import run_text_command
from tmux_sidepanel.process_table import PROCESS_LIST_COMMAND, parse_process_table
from tmux_sidepanel.processes import find_zombies


def test_debug(tmux_client, tmp_path):
    program = install_fake_agent(tmp_path)
    process = subprocess.Popen([str(program), "30"], start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_for_program(process, program.name)
    raw = run_text_command(PROCESS_LIST_COMMAND, 5)
    table = parse_process_table(raw)
    panes = tmux_client.list_panes()
    chain = []
    pid = process.pid
    while pid in table and len(chain) < 15:
        row = table[pid]
        chain.append([pid, row.terminal, row.status_flags, row.arguments[:50]])
        pid = row.parent_process_identifier
    terminals = sorted({pane.terminal for pane in panes})
    zombies = find_zombies(table, set(terminals), ("claude",))
    mine = [line for line in raw.splitlines() if str(process.pid) in line.split()[:1]]
    process.kill()
    pytest.fail(f"DEBUG terminals={terminals} chain={chain} zombies={len(zombies)} mine={mine} rawlines={len(raw.splitlines())}")
