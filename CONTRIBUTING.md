# Contributing

## Before you start

Open an issue to discuss a larger change before you write it. Report a security problem as
described in `SECURITY.md`, not in an issue.

## Set up

```
uv sync
```

The runtime has no packages besides the Python standard library. Keep it that way. Tools for
development are pinned in `uv.lock`.

## Checks

Run all of these. The pull request runs them too.

```
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run complexipy src devtools tests --failed --plain
```

The tests that use tmux start their own server on a private socket, and they do not read your
tmux configuration. They are skipped when tmux is not installed.

## How to write a change

1. Write a test that fails. Run it and read the failure.
2. Write the smallest code that passes the test.
3. Keep each commit small, and keep every commit green on its own.

The code follows these rules, and a test checks them:

- A function does one thing and is short. Blocks are not nested: use early returns, lookup
  tables and small helper functions.
- Names say what a thing is. Use full words and no leading underscore.
- Data that belongs together is a frozen dataclass, not a tuple.
- Files contain plain ASCII. No emoji.

## Docs and screenshots

Every change updates the docs and the screenshots in the same commit. This is a rule with no
exceptions. A change that touches behavior, keys, configuration, sections or what the panel shows
changes at least one of these:

- the text of `README.md`, `CONTRIBUTING.md` or `SECURITY.md`
- the pictures in `assets/`

Search the docs for every term that your change touches, and fix the sentences that are no longer
true. Then make the pictures again and look at them:

```
devtools/screenshots/make.sh
```

The script builds a demo tmux with invented data in its own process namespace, takes the
screenshots and draws the banner and the social preview (1280x640). It needs tmux, Chromium, `rsvg-convert`, ImageMagick and
`unshare`, and it stops without a picture when the text on the screen holds your user name, your
home directory or your host name. The pictures never show real projects, paths or people.

GitHub takes the social preview of the repository only through the settings page. When
`assets/social-preview.png` changes, upload it there (Settings, Social preview).

## Commits

Use Conventional Commits: `type(scope): subject`. The subject is at most 72 characters and has
no final period. The types are `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `build`, `ci`,
`perf`, `style` and `revert`. The body, when there is one, is wrapped at 72 characters.

## Security of changes

- Start programs from a list of arguments. Do not use a shell.
- Clean text from other programs before it reaches the terminal.
- Test data is fake. Do not put real names, hosts, paths or credentials in the repository.
