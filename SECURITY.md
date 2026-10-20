# Security policy

## Supported versions

Only the latest release is supported.

## Report a problem

Use private vulnerability reporting: open the Security tab of the repository and choose
"Report a vulnerability". Do not open a public issue, and do not post details in a discussion
or a pull request.

Please include:

- the version, and the versions of tmux and Python
- the steps that show the problem
- what an attacker gains

## What the plugin protects

- It starts programs from a list of arguments, never through a shell.
- It cleans text from other programs before it reaches your terminal.
- It asks before an action that cannot be undone, and it checks a process again before it sends
  a signal.
- It refuses a configuration file that someone else owns or can write to, because custom
  sections run commands from that file.
- It never asks for, reads or stores a password or a token.

Problems in these areas are in scope. A problem that needs write access to your own
configuration file or to your own home directory is not.
