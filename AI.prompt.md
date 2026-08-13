# AI.prompt.md

This file contains the complete prompt that regenerates this project from
scratch. It is the authoritative specification: when behaviour changes, update
this file in the same commit.

---

Build `plexdo`, an installable Python package providing a command-line
interface to Plex Media Server via the `plexapi` library, ready to publish to
PyPI. The console script is named `plex.do` (with `plexdo` as an alias).

## PROJECT LAYOUT

Use a src layout with setuptools and a PEP 621 `pyproject.toml`:

```
pyproject.toml          setuptools backend, PEP 621 metadata, pylint config
README.md  LICENSE  MANIFEST.in  requirements.txt  .gitignore  AI.prompt.md
completions/plex.do.bash
src/plexdo/
├── __init__.py         __version__
├── __main__.py         python -m plexdo
├── cli.py              _add_global_flags, build_parser, main
├── constants.py        DateInput, MediaItem, CONFIG_PATH, CACHE_DIR, LOG,
│                       PERMISSIVE_MODE_MASK, CONFIG_EXAMPLE
├── logs.py             configure_logging
├── config.py           check_file_permissions, config_optional, load_config,
│                       read_token, connect_plex
├── cache.py            _write_cache
├── convert.py          normalize_rating_key, parse_date
├── console.py          output, _cell, _display_width, _pad, _rule,
│                       print_table, print_metadata
├── titles.py           _display_title, _fetch_show, _non_special_episodes,
│                       _shuffle_list, fetch_item
├── sections.py         resolve_section, resolve_sections
├── accounts.py         _server_for_user, _find_user_by_id, _is_restricted,
│                       _account_type
├── playlists.py        _resolve_playlist, finalize_playlist,
│                       _resolve_dest_name, _copy_playlist_to
├── m3u.py              _write_m3u
├── photos.py           _collect_photos, _collect_library_items, _photo_file_path
├── sorting.py          _alpha_sort_key, _date_sort_key, _apply_sort
├── gallery.py          Spotlight.js HTML gallery
├── airdates.py         missing air-date estimation
├── security.py         argv scrubbing for --password
├── data/plex.do.bash   completion script shipped as package data
└── commands/
    ├── __init__.py     MODULES, register_all, build_registry
    ├── libraries.py    list-libraries, list-titles, list-show, export-titles
    ├── search.py       search
    ├── users.py        list-users
    ├── playlists.py    list-playlists, list-playlist, export-playlist,
    │                   remove-playlist, append-playlist
    ├── metadata.py     show-metadata
    ├── stream.py       read
    ├── rescan.py       rescan
    ├── build.py        build-interleaved, build-chronological, build-randomize
    ├── copy.py         copy-playlist-all-users, copy-playlist-to-user
    ├── watched.py      copy-watched
    └── auth.py         login, write-config-example
```

### Command module contract

Every module in `commands/` exposes exactly three names:

- `register(sub, parents)` — adds its subparsers to the top-level
  `add_subparsers` action, passing `parents=parents` on every `add_parser`
  call so each subcommand inherits the global flags
- `COMMANDS` — maps command name to handler
- `REQUIRES_PLEX` — the subset needing a connected server; `auth` has an empty
  frozenset because `login` and `write-config-example` run before a token exists

`commands/__init__.py` holds a `MODULES` tuple (whose order sets the order of
subcommands in `--help`), plus `register_all(sub)` and `build_registry()`
which merge the per-module tables. Adding a command means adding a module and
listing it in `MODULES`; `cli.py` never changes.

Shared logic must live in the core modules, not be duplicated across command
modules — pylint's `duplicate-code` check will catch it. In particular
`resolve_section` / `resolve_sections` and `fetch_item` exist because the
library-lookup and ratingKey-lookup blocks would otherwise be repeated across
four command modules.

### Packaging

`[project.scripts]` maps both `"plex.do"` and `plexdo` to `plexdo.cli:main` —
a dot in a console-script name is valid. Dependencies are `PlexAPI>=4.15.10`
and `requests>=2.31`; `requires-python = ">=3.11"`. Ship the completion script
as package data via `[tool.setuptools.package-data]` so it can be located at
runtime through `plexdo.__file__`. `python -m build` must produce an sdist and
wheel that both pass `twine check`.

## GENERAL REQUIREMENTS

- Python 3.11+
- Fully type-annotate every function, parameter, and return type
- Must pass pylint ≥ 9.5 (target 10.0) across the whole package
- Follow the Google Python style guide; small, single-purpose functions
- No dead code, no duplicate logic, no unused variables, no global mutable state
- No bare `except`; broad excepts only where explicitly noted, each with `# pylint: disable=broad-except`

Two pylint traps to design around from the start:

- Splitting `register()` per command module keeps every parser builder well
  under the statement limit; do not centralise argparse in `cli.py`.
- `bar` is on pylint's disallowed-name blacklist. Name the vertical
  box-drawing character `vline`.

## IMPORTS

Each module imports only what it uses, ordered standard library, then
third-party (`requests`, `plexapi`), then first-party (`plexdo.*`) — pylint
enforces this grouping. The full set used across the package:

```python
import argparse, configparser, ctypes, datetime, getpass
import html as html_lib
import json, logging, secrets, statistics, sys, textwrap, unicodedata
from pathlib import Path
from typing import (Any, Dict, Iterator, List, NamedTuple, Optional,
                    Sequence, Tuple, Union)

import requests

from plexapi.audio import Track
from plexapi.photo import Photo
from plexapi.exceptions import BadRequest, NotFound, Unauthorized
from plexapi.myplex import MyPlexAccount, MyPlexUser
from plexapi.playlist import Playlist
from plexapi.server import PlexServer
from plexapi.video import Episode, Movie, Show
```

## TYPE ALIASES AND CONSTANTS

```python
DateInput = Union[str, datetime.date, datetime.datetime, None]
MediaItem = Union[Episode, Movie, Track, Photo]

CONFIG_PATH          = Path("~/.local/etc/plex.do.ini").expanduser()
CACHE_DIR            = Path("~/.cache/plex.do").expanduser()
LOG                  = logging.getLogger("plex.do")
PERMISSIVE_MODE_MASK = 0o077
CONFIG_EXAMPLE       = "...the INI template, see below..."
```

## CONFIGURATION

`~/.local/etc/plex.do.ini`:

```ini
[plex]
url = http://localhost:32400
token_path = ~/usr/tmp/.fsec/plex_token

# Optional credentials used by `plex.do login`.
# The password is stored in plaintext, so keep this file mode 0600.
# Supplying --username on the command line ignores the password below.
# username = you@example.com
# password = your-plex-password
```

Expand `~` in all paths; read the token as UTF-8 and strip it; fail fast with a
clear `sys.exit` if either the config or the token file is missing, pointing at
`write-config-example`.

`CONFIG_EXAMPLE` must be a module-level constant, not a string inside the
writer function, because the `write-config-example` help output echoes it and
the two must never drift apart.

## SECURITY

### `check_file_permissions(path, label)`

Called at startup from `load_config()` (config file) and `read_token()` (token
file). Warns via `LOG.warning` if `st_mode & PERMISSIVE_MODE_MASK` is non-zero,
distinguishing "readable by group" from "readable by group and others", and
printing the literal `chmod 600 <path>` remedy. WARNING level so it shows
without `--verbose`; stderr so it never contaminates `--json`.

### `config_optional(cfg, key)`

Return a stripped optional `[plex]` value, or `None` when absent or empty.

## GLOBAL FLAGS

Every command accepts `--json`, `--verbose`, `--debug`, `--dry-run`, and they
must work **either before or after the command name**. All logging goes to
stderr only, so `--json` output on stdout is always clean.

Implement this with `_add_global_flags(parser, suppress=False)` called twice:
once on the top-level parser with ordinary `False` defaults, and once on an
`add_help=False` parent parser with `default=argparse.SUPPRESS`, which
`build_parser` passes to `register_all` and every subparser inherits via
`parents=`.

The SUPPRESS default is essential, not cosmetic. A subparser parses into its
own namespace and then copies **every** attribute onto the main namespace, so
ordinary `False` defaults on the inherited copies would silently clobber a flag
given before the subcommand — `plex.do --json list-users` would emit a table.
With SUPPRESS the attribute only exists when the flag was actually passed, so
whichever position it appears in wins and the other is left untouched.

## OUTPUT

### `output(data, args)`
`--json` → `json.dumps(data, default=str)`. Otherwise `print_table` for a
list-of-dicts, else plain `print`.

### `_cell(value)`
`str(value).strip()`. Plex metadata contains stray `\r`, which makes a printed
row's trailing pad overwrite the start of the line and appear as a blank line
after every row. Every value that is measured or printed must pass through this.

### `_display_width(text)`
Terminal display width, **not** `len()`. CJK glyphs (`east_asian_width` in
`W`/`F`) occupy two columns and combining marks occupy none, so a `len()`-padded
table drifts out of alignment on any library holding non-Latin titles. Pair it
with `_pad(text, width)` which replaces `ljust` everywhere.

### `print_table(rows)` / `print_metadata(record)`
UTF-8 box-drawn tables using `┌ ┬ ┐ ├ ┼ ┤ └ ┴ ┘ ─ │`, with a `_rule(widths, l, m, r)`
helper, column widths computed from `_display_width`, and one space of padding
each side of every cell:

```
┌─────┬─────────┬─────────────────┐
│ id  │ type    │ title           │
├─────┼─────────┼─────────────────┤
│ 1   │ managed │ Kids Profile    │
└─────┴─────────┴─────────────────┘
```

## SHARED HELPERS

- `normalize_rating_key(raw) -> int` — `int(raw)`, raising `ValueError` with a clear message
- `parse_date(value: DateInput) -> Optional[datetime]` — accepts `datetime`, `date`, `"%Y-%m-%d %H:%M:%S"`, `"%Y-%m-%d"`
- `_display_title(item) -> str` — `Episode` → `"grandparentTitle - title"`, everything else → `item.title`. Use in every table, preview, M3U `#EXTINF`, and HTML alt/title
- `_non_special_episodes(show)` — episodes with `seasonNumber > 0`
- `_shuffle_list(lst)` — Fisher-Yates via `secrets.randbelow`
- `_resolve_playlist(user_plex, identifier)` — try `int()` → `fetchItem` (assert `isinstance(..., Playlist)`); else look up by title; `sys.exit` if absent

### User identifier resolution

Every argument naming a user accepts **either** a numeric user ID **or** the
user's title, so all such argparse arguments are plain strings with
`metavar="USER"` — never `type=int`.

`accounts.resolve_user_arguments(plex, args)` is called once from `cli.main`
after connecting and before dispatch, rewriting every attribute in
`USER_ID_ARGUMENTS = ("user_id", "user_a", "user_b", "source_user_id")` in
place. Handlers therefore always receive a plain int and need no changes.
Build the roster once per invocation so a two-user command costs one extra API
call, and skip the fetch entirely when no user argument is present.

`resolve_user_identifier(roster, value)` rules, where the roster is
`[(0, admin_title)] + [(id, title) for each shared user]`:

- Titles match exactly first, then case-insensitively.
- More than one title match → `sys.exit`, listing the colliding IDs and asking
  for the numeric ID.
- Numeric value that is a real user ID → use it. If it is *also* some other
  user's title, warn naming the user that was not selected.
- Numeric value that is not a real ID but *is* a title → resolve by title.
- Numeric value matching nothing → return it unchanged so the downstream
  lookup produces the precise error.
- Non-numeric value matching nothing → `sys.exit` pointing at `list-users`.

Note the duplicate-title abort applies only when resolving *by title*; passing
a numeric ID is unambiguous and must still work on a server that happens to
have two identically titled users.

### `_server_for_user(plex, user_id) -> PlexServer`

`user_id == 0` returns the admin `plex` object directly with no API call.
Otherwise call `user.get_token(plex.machineIdentifier)` and build a new
`PlexServer`. **Do not use `switchHomeUser()`** — it only works for Plex Home
and raises 401 for ordinary shared users. Every `user_id` help string must
document `0 = admin`.

## COMPLETION CACHE

`_write_cache(name, data)` writes JSON atomically (`.tmp` then `Path.replace`)
into `CACHE_DIR`, silently swallowing `OSError`. Called as a side effect, before
`output()`, by: `list-libraries` → `libraries.json`; `list-titles <id>` →
`titles.<id>.json`; `list-users` → `users.json`; `list-playlists <uid>` →
`playlists.<uid>.json`.

## PLAYLIST BUILDING MODEL

Every build command must (1) fully construct the item list in memory,
(2) validate it is non-empty, (3) print a numbered preview via `_display_title`,
(4) make exactly one `plex.createPlaylist(name, items=items)` call.
`finalize_playlist(plex, name, items, args)` enforces this and honours `--dry-run`.

## M3U EXPORT — `_write_m3u(items, path)`

Plex **server filesystem paths only**, from `item.media[].parts[].file`. Skip
items with no path (no placeholder line); include every part of a multi-part
item. Duration is `item.duration` ms → seconds, falling back to `-1`. The
`#EXTINF` title uses `_display_title`.

```
#EXTM3U
#EXTINF:3600,Show Name - Episode Name
/server/path/to/file.mkv
```

## COMMANDS

### `list-libraries`
Columns `id`, `type`, `title`. Writes the libraries cache.

### `list-titles <library_id> [--album ALBUM]`
show/movie use `section.all()`; photo libraries use `_collect_photos`. Columns
`ratingKey`, `title`. Writes `titles.<id>.json`. `--album` warns and is ignored
for non-photo libraries.

### `search <user_id> <query> [--media-type TYPE] [--library-id ID]`
Runs as the given user. Searches every library unless `--library-id` scopes it.
`--media-type` choices `movie show episode track photo album artist`, passed as
`libtype`. A per-library failure logs a warning and continues rather than
aborting. Columns `ratingKey`, `libraryId` (from `item.librarySectionID`),
`type`, `title`. Implement one `_search_in_section` helper and have
`_search_all_sections` call it — do not inline a second copy of the loop.

### `list-users`
Columns `id`, `type`, `title`; writes the users cache.

`_account_type(user)` returns `managed` / `home` / `friend` / `shared`.
Note that plexapi exposes `restricted` as the **raw XML string**, not a bool, so
a plain truth test sees `"0"` as True and mislabels every account as managed.
`_is_restricted` must treat `""`, `"0"`, and `"false"` as false while still
accepting a real bool.

### `list-playlists <user_id>`
Columns `ratingKey`, `title`, `items`; writes the playlists cache.

### `list-playlist <user_id> <playlist|ratingKey> [--m3u PATH]`
Accepts either form via `_resolve_playlist`. Columns `index`, `ratingKey`, `title`.

### `list-show <rating_key> [--m3u PATH]`
Fails fast if the item is not a `Show`. Columns `index`, `ratingKey`, `season`,
`episode`, `title`.

### `show-metadata <rating_key>`
Dispatch through a `_METADATA_BUILDERS` dict keyed on `item.type`, falling back
to the base builder. Base fields: `ratingKey, type, title, year, contentRating,
rating, duration` (ms → `H:MM:SS` via `_format_duration`), `addedAt, updatedAt,
summary`. Extra fields — `episode`: `show, season, episode, airDate, studio`;
`movie`: `studio, airDate, tagline, genres, directors`; `show`: `studio,
firstAired, seasons, episodes, genres, network`; `track`: `album, artist,
trackNumber`.

### `read <library_id> <rating_key>`
Streams a media file to stdout for redirection or piping:

```
plex.do read 3 12345 | mpv -
plex.do read 3 12345 > file.mkv
```

Validate that the item's `librarySectionID` matches `library_id`. Warn if the
item has multiple media/parts and stream only the first. Use
`requests.get(url, stream=True, timeout=30)` with 64 KB chunks written to
`sys.stdout.buffer`. Catch `BrokenPipeError` silently — that is the normal exit
when a player quits early — and `sys.exit` on `requests.HTTPError`. Warn to
stderr if stdout is a tty, then proceed. `--dry-run` prints title, server path,
and URL to stderr without streaming. Get the URL from
`plex.url(part.key, includeToken=True)`.

### `rescan [library_id] [-s/--status] [-n/--now]`
`library_id` is `nargs="?"`; `sys.exit` if it is absent and `--status` was not given.

- `--status` / `-s`: read `plex.activities` — it is a **property, not a method**;
  calling it raises `TypeError: 'list' object is not callable`. Columns `type`,
  `title`, `subtitle`, `progress`, `uuid`; print "No active scan jobs." to stderr when empty.
- plain: `section.update()` (a file scan, not `refresh()` which only re-fetches metadata)
- `--now` / `-n`: first iterate every section calling `section.cancelUpdate()`,
  swallowing errors from already-idle sections, then `section.update()`. Both steps honour `--dry-run`.

### `build-interleaved <name> <ratingKey...> [--m3u PATH]`
Round-robin across shows using `_non_special_episodes`.

### `build-chronological <name> <ratingKey...> [--m3u PATH]`
Shows and movies, season 0 skipped, globally sorted by resolved air date.

Missing-date resolution, implemented exactly:

1. Look only within the same season
2. Collect up to 6 previous and 6 next episodes that have dates, ordered by `episode.index`
3. Require ≥ 3 known dates (giving ≥ 2 intervals), else fall through to the prompt
4. Compute timedeltas between adjacent sorted dates
5. Require ≥ 2 intervals, else fall through
6. Take `statistics.median` of the interval seconds
7. Estimate from latest-previous (+median) and/or earliest-next (−median); average the timestamps when both exist
8. Otherwise prompt interactively for `YYYY-MM-DD`, offering the last resolved date as the example

### `build-randomize <user_id> <source> <dest> [--m3u PATH]`

### `copy-playlist-all-users <source_user_id> <source_playlist> [-o/--overwrite]`
Resolve the source through `_server_for_user`, then copy to every user from
`account.users()`, **skipping the source user itself**. A failure for one user
logs a warning and the loop continues.

### `copy-playlist-to-user <source_user_id> <source_playlist> <user_id> <dest> [-o/--overwrite]`

Both copy commands share `_resolve_dest_name(user_plex, desired_name, force_overwrite)`,
returning `Optional[Tuple[str, bool]]` of `(final_name, delete_first)` or `None`
meaning skip:

| destination state | default | `-o` |
|---|---|---|
| nothing there | `Mix` | `Mix` |
| `Mix` exists | `Mix admin copy` | `Mix` (replaced) |
| `Mix` and `Mix admin copy` exist | **skip, warn, touch nothing** | `Mix` (replaced) |

`_copy_playlist_to` takes a `target_label` argument so the skip warning names
the affected user — essential in the all-users loop, where the run continues.
The warning must name both conflicting titles and point at `--overwrite`.

### `copy-watched <user_a> <user_b> [-1/--one-way] [-l/--library ID] [-t/--title KEY] [--unwatch]`

Synchronises watched state and resume points between two users. Collects
`isPlayed`, `viewOffset`, and `lastViewedAt` for every item both users can see,
then writes the winning state onto the other user. Only the intersection of the
two users' visible ratingKeys is considered.

Scope: `--library` restricts to one section, `--title` to one ratingKey
(skipping the library scan entirely). Watch state lives on leaf items, so map
section type to leaf libtype — `movie`→`movie`, `show`→`episode`,
`artist`→`track` — and skip photo libraries, which have no watch state. Use
`section.all(libtype=...)`, **not** `section.search(...)`, which needs a
non-empty query and would silently return nothing.

Winner selection, `_select_winner(first, second, unwatch)` returning
`(winner, loser)` or `None`:

| situation | default | `--unwatch` |
|---|---|---|
| neither has data | skip | skip |
| states already match | skip | skip |
| exactly one has data | the one **with** data wins | the one **without** data wins |
| both have data | **latest** `lastViewedAt` wins | **earliest** `lastViewedAt` wins |

A `lastViewedAt` of `None` must never win: map it to `datetime.min` when the
latest wins and `datetime.max` when the earliest does. Because Plex rewrites
`viewOffset` continuously during playback, treat offsets within
`_OFFSET_TOLERANCE_MS` (10 s) as identical, or every run reports spurious changes.

`--one-way` drops any change whose target is the first user, so the first
user's state is never modified.

Actions are `markPlayed`, `setProgress`, or `markUnplayed`, computed before
applying so `--dry-run` can preview them. Print a preview table of
`ratingKey`, `title`, `action`, `target` and honour `--dry-run`. When nothing
needs changing, print "Watch state already in sync." to stderr (or `[]` for
`--json`). Note that plexapi renamed these methods (`markWatched` →
`markPlayed`, `markUnwatched` → `markUnplayed`), so call through a
`_call_first_method(item, names, *args)` helper that tries both spellings;
likewise read played state from `isPlayed`, then `isWatched`, then `viewCount`.

Register this subparser from its own `_register_copy_watched_subparser(sub)`
helper to keep both `build_parser` and the copy/mutation registrar under
pylint's statement limit. `-1` is a valid short option here: argparse
recognises that an option string looks like a negative number and stops
treating `-1` as a negative numeric positional.

### `export-playlist <user_id> <playlist> <path>`
`path` is a required positional. Rejects an empty playlist.

### `remove-playlist <user_id> <playlist>`

### `append-playlist <user_id> <playlist> <ratingKey...>`
Fetch each item, fail fast on an unknown key, preview, honour `--dry-run`, then
one `playlist.addItems(...)` call.

### `export-titles <library_id> <output_path> [--sort alpha|date|random] [--album ALBUM]`
`_apply_sort` modes: `alpha` (episodes by `(grandparentTitle, seasonNumber, index)`,
others by title), `date` (`originallyAvailableAt` falling back to `addedAt`,
undated sorting last via `datetime.datetime.max`), `random`. Output is M3U for
show/movie libraries and an HTML gallery for photo libraries.

### `login [-u USER] [-p PASS] [-c CODE] [-2]`
Authenticate against plex.tv via `MyPlexAccount` and save the token to
`token_path` with mode 0600, creating parent directories. Distinguish
`Unauthorized` (bad credentials or 2FA required — say so) from `BadRequest`.
Verify the saved token by connecting to the configured URL; a failure warns
rather than aborting, since the token did save. Not in `COMMANDS_REQUIRING_PLEX`
— there is no token yet — but it still loads the config to learn where to write.
`--dry-run` authenticates without writing. `--json` emits
`{"token_path": ..., "verified": ...}` and never the token itself.

Credential precedence, `resolve_credentials(cfg, args)`:

| config | args | result |
|---|---|---|
| user + pass | — | ini user, ini pass |
| user + pass | `--username` | arg user, **prompt** (ini pass ignored) |
| user + pass | `--username --password` | arg user, arg pass |
| user + pass | `--password` | ini user, arg pass |
| user only | — | ini user, prompt |
| — | — | prompt both |
| — | `--username` | arg user, prompt |

The ini password is only ever used alongside the ini username; pairing a stored
password with a different username would be a silent credential mismatch.
Passwords are read with `getpass` and never echoed.

`--password` handling, run from `main()` immediately after logging is configured
and before any network call:

- `_overwrite_argv_memory(replacement)` rewrites the real argv block via
  `ctypes.pythonapi.Py_GetArgcArgv`, because `sys.argv` is only a copy and `ps`
  reads the original buffer. Best-effort, broadly guarded, degrading to a second warning.
- `_mask_argv_copy(secret)` redacts `sys.argv` so tracebacks cannot leak it,
  handling both `--password X` and `--password=X`.
- The warning must be blunt about what cannot be fixed: the password is already
  in shell history and was visible to `ps` during interpreter startup.

### `write-config-example`
Writes `CONFIG_EXAMPLE` to `CONFIG_PATH` with mode 0600, creating parent dirs.
Requires no Plex connection.

Its `--help` must print the exact template that would be written. This needs
`formatter_class=argparse.RawDescriptionHelpFormatter` so the epilog's newlines
survive — but that same formatter also stops argparse wrapping the description,
so pre-wrap the description with `textwrap.fill(..., width=78)` and indent the
epilog template with `textwrap.indent(CONFIG_EXAMPLE, "  ")`.

## PHOTO LIBRARIES

### `_collect_photos(section, album=None)`
Walk `section.all()` to get album objects, then `palbum.photos()` on each —
mirroring how show libraries walk shows then episodes. **Do not use
`section.search(libtype="photo")`**: Plex requires a non-empty query string and
returns nothing for an empty one, so the library silently appears empty. When
`album` is given, match `palbum.title` case-insensitively at the album level and
`sys.exit` if nothing matches, suggesting `list-titles`.

### `_collect_library_items(section, album=None)`
`show` → walk `_non_special_episodes`; `movie` → `section.all()`; `photo` →
`_collect_photos`; anything else → `sys.exit` listing the supported types.

## PHOTO GALLERY — `_write_gallery_html(photos, output_path, library_title)`

A single self-contained HTML file using Spotlight.js from jsDelivr for the
lightbox. **No `plex` parameter and no Plex HTTP URLs anywhere in the output** —
every `href` and `src` is a server filesystem path from
`_photo_file_path(photo)` (`photo.media[0].parts[0].file`, `None` on
`IndexError`/`AttributeError`). A photo with no resolvable path is skipped,
matching `_write_m3u`.

Split into `_gallery_css()`, `_gallery_photo_anchor(photo)`,
`_gallery_album_section(album_name, photos)`, and `_group_photos_by_album(photos)`
to stay under pylint's local-variable limit.

Photos are grouped by `parentTitle` (falling back to `"Uncategorised"`) and
albums sorted alphabetically. Design: near-black `#0d0d0d` background, warm
amber `#a0835c` library title, muted small-caps album headings with counts,
192×192px cover-fit grid, `scale(1.06)` hover, `loading="lazy"` on every
thumbnail, and `prefers-reduced-motion` respected. Spotlight `data-title` is the
photo title and `data-description` the `originallyAvailableAt` date. For a
single-album export the gallery title is `"Library — Album"`.

## MAKEFILE

Provide a `Makefile` whose default target is `help`, listing every target and
printing the completion path currently in effect.

`install` runs `pip install .` and installs the completion; `uninstall` runs
`pip uninstall -y plexdo` and removes it; `develop` does an editable install
with the dev extras. Also provide `reinstall`, `install-completion`,
`uninstall-completion`, `build`, `lint`, `dist-check`, `check`, `clean`, and
`distclean`, and mark them all `.PHONY`.

The completion destination defaults to
`$(XDG_DATA_HOME)/bash-completion/completions` (falling back to
`~/.local/share`), switches to `$(PREFIX)/share/bash-completion/completions`
when `PREFIX` is set, and can be overridden outright via `COMPLETION_DIR`.
Honour `DESTDIR` for staged packaging builds. Respect `PYTHON`, `PIP`, and
`PIP_FLAGS` overrides.

Two safety points: `uninstall-completion` must test for the exact file before
removing it and say so when there is nothing to remove, rather than a blind
`rm -rf` on a user-supplied directory; and `uninstall` must prefix the pip call
with `-` so a package that is already absent does not fail the target.

## LICENSING

The project is GPL-3.0-or-later. `LICENSE` holds the complete GPL v3 text and
`pyproject.toml` declares the SPDX expression `license = "GPL-3.0-or-later"`
(a PEP 639 expression, so do not also add a deprecated `License ::` trove
classifier). Every source file carries an
`# SPDX-License-Identifier: GPL-3.0-or-later` tag; `__init__.py`, `__main__.py`,
and `cli.py` additionally carry the full copyright-and-warranty notice from the
GPL's "How to Apply These Terms" appendix. The README states the copyleft
obligation explicitly.

## PLATFORM SUPPORT

Linux, macOS, and Windows. Five portability rules, each guarding a failure
that is invisible when developing on Linux:

- **Console encoding.** `print_table` and `print_metadata` must select box
  glyphs via a `_box()` helper that test-encodes them against
  `sys.stdout.encoding` and falls back to ASCII `+-|`. A legacy Windows
  console is cp1252, which cannot encode U+2500, so the Unicode-only version
  raises `UnicodeEncodeError` and prints *nothing*. Route cell values through
  a `_printable()` helper that substitutes unencodable characters. Apply it
  only in the printers — never in `_cell`, which feeds title matching, where
  mangling `Renée` to `Ren?e` would break comparisons against real Plex data.
  JSON output needs no equivalent: `json.dumps` escapes non-ASCII by default.
- **Permission checks.** `check_file_permissions` must return early when
  `os.name == "nt"`. Windows has no POSIX mode bits; `os.stat` synthesises
  `0o666`, so the check would fire on every run advising a `chmod` that cannot
  help. Guard the `chmod(0o600)` calls the same way.
- **Broken pipes.** After catching `BrokenPipeError` in the `read` command,
  `os.dup2` the null device onto stdout so the interpreter's final flush does
  not print "BrokenPipeError ignored" when the user quits the player.
- **macOS shell tooling.** macOS ships bash 3.2, which has no `mapfile` or
  `readarray`; fill `COMPREPLY` with a `while IFS= read -r` loop instead
  (redirecting into a function does not create a subshell, so the assignment
  survives). Use `stat -c %Y` with a `stat -f %m` fallback in all three
  completions, and restrict the Makefile to `install -d` / `install -m`, since
  `install -D` is GNU-only.
- **Interpreter name.** All three completions must fall back to `python` when
  `python3` is absent, as under Git Bash. In fish, guard `__plexdo_refresh` on
  the binary existing: fish reports an unknown command *before* the
  redirection applies, scribbling on the prompt mid-completion.

## ERROR HANDLING

`sys.exit` with a clear message for: missing config, missing token, unknown
ratingKey, wrong media type, playlist not found, user not found, library ID not
found, unsupported library type, album not found.

## SHELL COMPLETION

Provide completions for **bash, zsh, and fish** in `completions/`, mirrored
into `src/plexdo/data/` as package data: `plex.do.bash`, `_plex.do` (zsh
`#compdef` convention), and `plex.do.fish`. All three share the same cache
strategy and cover the same values, and all three depend only on `python3` —
no `bash-completion` package, no external helpers.

### bash — `completions/plex.do.bash`

Must work **without** the `bash-completion` package: initialise from
`COMP_WORDS` / `COMP_CWORD` directly rather than `_init_completion`, and use
`compgen -f` rather than `_filedir`. Both are absent on many systems and produce
a `command not found` on every Tab press.

Caches live in `~/.cache/plex.do` with a 900-second TTL, checked via `stat`
portable across Linux (`-c %Y`) and macOS (`-f %m`). When a cache is stale or
missing, `_plexdo_bg_refresh` runs the relevant `plex.do` list command with
`>/dev/null 2>&1 &` and `disown`, so completion never blocks — stale results are
shown now and the next Tab sees fresh ones. `_plexdo_json_candidates cache field`
reads a cache with inline Python.

Helpers: `_plexdo_complete_user_id` (`0` plus cached IDs),
`_plexdo_complete_library_id`, `_plexdo_complete_rating_key` (merged from every
`titles.*.json`, chaining `list-libraries` → per-library `list-titles` when
nothing is cached), `_plexdo_complete_playlist(uid)`,
`_plexdo_complete_playlist_id_or_name(uid)` (both ratingKeys and titles, for
`list-playlist`), `_plexdo_complete_album(library_id)` (unique album prefixes
split from `"Album - Photo Title"`), plus `_plexdo_find_cmd`,
`_plexdo_positional_count` (skipping `--m3u <value>` pairs), and
`_plexdo_nth_positional`.

| command | pos 0 | pos 1 | pos 2 | pos 3 | flags |
|---|---|---|---|---|---|
| `list-titles` | library_id | — | — | — | `--album` → albums |
| `search` | user_id | free | — | — | `--media-type`, `--library-id` |
| `list-playlists` | user_id | — | — | — | — |
| `list-playlist` | user_id | playlist-id-or-name | — | — | `--m3u` → file |
| `list-show` | rating_key | — | — | — | `--m3u` → file |
| `show-metadata` | rating_key | — | — | — | — |
| `read` | library_id | rating_key | — | — | — |
| `rescan` | library_id | — | — | — | `-s/--status`, `-n/--now` |
| `build-interleaved` | free | rating_key… | — | — | `--m3u` → file |
| `build-chronological` | free | rating_key… | — | — | `--m3u` → file |
| `build-randomize` | user_id | playlist | free | — | `--m3u` → file |
| `copy-playlist-all-users` | user_id | playlist | — | — | `-o/--overwrite` |
| `copy-playlist-to-user` | user_id | playlist | user_id | playlist | `-o/--overwrite` |
| `remove-playlist` | user_id | playlist | — | — | — |
| `export-playlist` | user_id | playlist | file path | — | — |
| `append-playlist` | user_id | playlist | rating_key… | — | — |
| `export-titles` | library_id | file path | — | — | `--sort`, `--album` → albums |
| `copy-watched` | user_id | user_id | — | — | `-1`, `-l` → libraries, `-t` → ratingKeys, `--unwatch` |

### zsh — `completions/_plex.do`

Start with `#compdef plex.do plexdo`. Use `_arguments -C` with
`'1:command:_plexdo_commands'` and `'*::command argument:->subcmd'`, then a
`case ${words[1]}` dispatch. Note that under `*::` zsh **rebinds `words` so
that `words[1]` is the subcommand**, which the positional helper must assume.
Offer descriptions via `_describe`, and sanitise `:` out of description text
since `_describe` splits `value:description` on it.

### fish — `completions/plex.do.fish`

Use `complete -c plex.do -f` plus `-c plexdo` for the alias, gating each rule
on `__fish_seen_subcommand_from`. Fish has no positional-index primitive, so
write `__plexdo_positionals` / `__plexdo_at` / `__plexdo_nth` helpers that walk
`(commandline -opc)`, skipping flags and the values consumed by options that
take one (`--m3u`, `--album`, `--sort`, `--media-type`, `--library-id`, `-l`,
`-t`, `-u`, `-p`, `-c`). Global flags are registered without a subcommand
condition so they complete in either position. Emit `value\tdescription` pairs.
| `login` | — | — | — | — | `-u`, `-p`, `-c`, `-2` |

Register with `complete -F _plexdo_complete plex.do` and the same for `plex_do`.

## DELIVERABLES

1. The `plexdo` package under `src/`, laid out as above
2. `pyproject.toml` — PEP 621 metadata, both console scripts, package data, pylint config
3. `README.md` — install, configuration, every command group with examples, completion setup, layout
4. `LICENSE` — the full GNU GPL v3 text, `MANIFEST.in`, `requirements.txt`, `.gitignore`
5. `Makefile` — see below
6. `completions/plex.do.bash`, mirrored into `src/plexdo/data/`
7. `AI.prompt.md` — this file, at the top level of the project, containing the
   full prompt that regenerates the project including this requirement itself

Verification: `pylint src/plexdo` scores 10.00/10, `python -m build` succeeds,
`twine check dist/*` passes, and installing the wheel into a clean virtualenv
gives a working `plex.do` console script.
