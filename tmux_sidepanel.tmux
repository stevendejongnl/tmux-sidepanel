#!/usr/bin/env bash
# Entry file of the tmux plugin manager: it runs every *.tmux file of a plugin when tmux starts.
# The work is done by the Python code, which installs the hooks of tmux. Running it again is safe.
set -u

plugin_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHONPATH="${plugin_directory}/src" python3 -m tmux_sidepanel setup
