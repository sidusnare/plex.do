# Contributing

## Getting set up

```bash
git clone https://github.com/sidusnare/plexdo.git
cd plexdo
make develop      # editable install with the dev extras
```

## Before opening a pull request

```bash
make check
```

That runs, in order:

| step | what it enforces |
| --- | --- |
| `check-version` | the version agrees across `__init__.py`, `pyproject.toml`, and the man page |
| `check-assets` | packaged completions and man page match their sources; all source is ASCII |
| `smoke` | the package imports, the parser builds, every command module is registered |
| `test` | the test suite |
| `lint` | pylint scores 10.00/10 |
| `build` + `dist-check` | the sdist and wheel build and pass `twine check` |

## House rules

- Every function is annotated, and pylint must stay at 10.00/10.
- A leading underscore means module-private. If another module imports it, it
  is package API and must not have one.
- Source files are plain ASCII. Write `-`, not an em dash. The box-drawing
  characters in `console.py` are `\uXXXX` escapes for this reason.
- Adding a command means adding a module under `src/plexdo/commands/` that
  exposes `register(sub, parents)`, `COMMANDS`, and `REQUIRES_PLEX`, then
  listing it in `MODULES`. `cli.py` should not need changing.
- Bump the revision (the third version field) for each release, in all three
  places `check-version` inspects.

`AI.prompt.md` is the authoritative specification. When behaviour changes,
update it in the same commit.
