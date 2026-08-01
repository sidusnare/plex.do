Claude Sonnet 5.6 High

Here is the prompt:

---

Write a complete, production-quality Python CLI script named `plex.do` that uses the `plexapi` library to interact with a Plex Media Server. Also produce a `requirements.txt` and a bash completion script with live cached ID/name completion.

---

## GENERAL REQUIREMENTS

* Python 3.11+
* Fully type-annotate all functions, parameters, and return types
* Must pass pylint ≥ 9.5 (target 10.0); add `# pylint: disable=too-many-lines` at module top
* Follow Google Python style guide; small, single-purpose functions
* No unused variables, no bare `except` (except where noted), no duplicate logic
* No global mutable state

---

## IMPORTS

Standard library first, then third-party, then plexapi. Exactly:

```python
import argparse, configparser, datetime
import html as html_lib
import json, logging, requests, secrets, statistics, sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Union

from plexapi.audio import Track
from plexapi.exceptions import NotFound
from plexapi.myplex import MyPlexAccount, MyPlexUser
from plexapi.photo import Photo
from plexapi.playlist import Playlist
from plexapi.server import PlexServer
from plexapi.video import Episode, Movie, Show
```

---

## TYPE ALIASES AND CONSTANTS

```python
DateInput = Union[str, datetime.date, datetime.datetime, None]
MediaItem = Union[Episode, Movie, Track, Photo]

CONFIG_PATH = Path("~/.local/etc/plex.do.ini").expanduser()
CACHE_DIR   = Path("~/.cache/plex.do").expanduser()
LOG         = logging.getLogger("plex.do")
```

---

## CONFIGURATION

* Config: `~/.local/etc/plex.do.ini`
  ```ini
  [plex]
  url = http://localhost:32400
  token_path = /tmp/plex_token
  ```
* Expand `~` in all paths; read token as UTF-8 strip; fail fast with clear `sys.exit` messages if either is missing

---

## COMPLETION CACHE

`_write_cache(name, data)` — atomically write JSON to `CACHE_DIR/<name>.json` (write to `.tmp` then `Path.replace`); silently swallow `OSError`. Called as a side-effect (before `output()`) in: `list-libraries` → `libraries.json`; `list-titles <id>` → `titles.<id>.json`; `list-users` → `users.json`; `list-playlists <uid>` → `playlists.<uid>.json`.

---

## SHARED HELPERS

### `normalize_rating_key(raw) -> int`
`int(raw)`; raise `ValueError` with clear message on failure.

### `parse_date(value: DateInput) -> Optional[datetime.datetime]`
Accept `datetime`, `date`, `"%Y-%m-%d %H:%M:%S"`, `"%Y-%m-%d"` strings; raise `ValueError`/`TypeError` otherwise.

### `_cell(value) -> str`
`str(value).strip()` — used everywhere a value is measured or printed to eliminate `\r` and other control characters that cause blank-line artefacts.

### `_display_title(item) -> str`
`Episode` → `"grandparentTitle - title"`. All others → `item.title`. Use everywhere a title is shown, written to M3U, previewed, or placed in HTML.

### `_server_for_user(plex, user_id) -> PlexServer`
`user_id == 0` → return admin `plex` directly. Otherwise → `user.get_token(plex.machineIdentifier)` and construct a new `PlexServer`. **Never** use `switchHomeUser()`. All `user_id` help strings must document `0 = admin`.

### `_resolve_playlist(user_plex, identifier) -> Playlist`
Try `int(identifier)` → `fetchItem` (assert `isinstance(item, Playlist)`); fall back to `user_plex.playlist(identifier)` by name; `sys.exit` if not found.

### `_non_special_episodes(show) -> List[Episode]`
Episodes where `seasonNumber > 0`.

### `_shuffle_list(lst) -> List`
Fisher-Yates using `secrets.randbelow`.

---

## OUTPUT

### `output(data, args)`
`--json` → `json.dumps(data, default=str)` to stdout. Otherwise → `print_table` for list-of-dicts, else `print`.

### `print_table(rows)`
Auto-compute column widths using `_cell`; print header, divider, then rows — all via `_cell` to strip control characters.

### `print_metadata(record)`
Key-value display aligned to widest key; used by `show-metadata`.

---

## PLAYLIST BUILDING MODEL

All build commands: (1) fully construct list in memory, (2) validate non-empty, (3) print numbered preview via `_display_title`, (4) exactly one `plex.createPlaylist(name, items=items)`.

`finalize_playlist(plex, name, items, args)` enforces this; respects `--dry-run`.

---

## M3U EXPORT — `_write_m3u(items, path)`

* Plex server filesystem paths: `item.media[].parts[].file` only
* Skip items with no file path; include all parts for multi-part items
* Duration: `item.duration` ms → seconds; fallback `-1`
* `#EXTINF` title: `_display_title(item)`

---

## GLOBAL FLAGS

Every command: `--json`, `--verbose`, `--debug`, `--dry-run`. Logging always to stderr only.

---

## COMMANDS

### `list-libraries`
Columns: `id`, `type`, `title`. Writes `libraries.json` cache.

### `list-titles <library_id> [--album ALBUM]`
* show/movie: `section.all()`
* photo: `_collect_photos(section, album)` — walks `section.all()` (albums) then `palbum.photos()` per album; **never** calls `section.search(libtype="photo")` (returns nothing without a query string)
* Columns: `ratingKey`, `title` via `_display_title`
* Writes `titles.<library_id>.json` cache
* `--album` ignored with warning for non-photo libraries

### `search <user_id> <query> [--media-type TYPE] [--library-id ID]`
* Runs as user (0 = admin); searches all libraries by default
* `--media-type` choices: `movie show episode track photo album artist` → passed as `libtype` to `section.search()`
* `--library-id` scopes to one library; fail fast if not found
* Per-library search failures: log warning, continue
* Columns: `ratingKey`, `libraryId` (from `item.librarySectionID`), `type`, `title` via `_display_title`

### `list-users`
Columns: `id`, `title`. Writes `users.json` cache.

### `list-playlists <user_id>`
Columns: `ratingKey`, `title`, `items`. Writes `playlists.<user_id>.json` cache.

### `list-playlist <user_id> <playlist|ratingKey> [--m3u PATH]`
Accepts playlist by name or ratingKey via `_resolve_playlist`. Columns: `index`, `ratingKey`, `title`. Optional M3U export after listing.

### `list-show <rating_key> [--m3u PATH]`
Fail fast if not a `Show`. Uses `_non_special_episodes`. Columns: `index`, `ratingKey`, `season`, `episode`, `title`. Optional M3U export.

### `show-metadata <rating_key>`
Type-specific metadata builders dispatched via `_METADATA_BUILDERS` dict keyed on `item.type`; fallback to base builder. All types share: `ratingKey, type, title, year, contentRating, rating, duration` (ms → `H:MM:SS` via `_format_duration`), `addedAt, updatedAt, summary`. Extra per type:
* `episode`: `show, season, episode, airDate, studio`
* `movie`: `studio, airDate, tagline, genres, directors`
* `show`: `studio, firstAired, seasons, episodes, genres, network`
* `track`: `album, artist, trackNumber`

JSON → `json.dumps(record)`. Otherwise → `print_metadata(record)`.

### `read <library_id> <rating_key>`
Stream the media file to stdout for piping into a player:
```
plex.do read 3 12345 | mpv -
plex.do read 3 12345 > file.mkv
```
* Validate item's `librarySectionID` matches `library_id`; fail fast if not
* Warn (stderr) if multiple media/parts; stream first part only
* Use `requests.get(url, stream=True, timeout=30)` with 64 KB chunks to `sys.stdout.buffer`
* Catch `BrokenPipeError` silently (player quit early); raise `sys.exit` on `requests.HTTPError`
* If stdout is a tty, warn to stderr then proceed
* `--dry-run` prints title, server file path, and URL to stderr without streaming
* `--json` has no effect; emit a warning to stderr

Obtain the stream URL via `plex.url(part.key, includeToken=True)`.

### `rescan [library_id] [-s/--status] [-n/--now]`
Three modes:

**`--status / -s`** (no `library_id` required): call `plex.activities` (it is a **property**, not a method — do not call with `()`). Display columns: `type`, `title`, `subtitle`, `progress`, `uuid`. Print "No active scan jobs." to stderr if empty.

**`rescan <library_id>`**: call `section.update()` to trigger a library file scan.

**`rescan <library_id> --now / -n`**: first cancel all pending scans by iterating `plex.library.sections()` and calling `section.cancelUpdate()` on each (swallow exceptions for idle sections with `except Exception`), then call `section.update()`. Both steps respect `--dry-run`.

`library_id` is `nargs="?"` (optional positional); `sys.exit` if it is `None` and `--status` was not given.

### `build-interleaved <name> <ratingKey...> [--m3u PATH]`
Round-robin via `_non_special_episodes`. `finalize_playlist` then optional M3U.

### `build-chronological <name> <ratingKey...> [--m3u PATH]`
Shows and movies; skip season 0; sort globally by resolved air date; `finalize_playlist` then optional M3U.

#### Missing date resolution (implement exactly):
1. Look only within same season
2. Collect up to 6 previous + 6 next episodes with known dates (by `episode.index`)
3. Require ≥ 3 known dates (→ ≥ 2 intervals); else fallback
4. Compute timedelta intervals between adjacent sorted dates
5. Require ≥ 2 intervals; else fallback
6. `statistics.median` of interval seconds → `timedelta`
7. Estimate from latest-prev (+median) and/or earliest-next (−median); if both → average timestamps
8. Still unresolved → interactive prompt (YYYY-MM-DD; show last resolved date as example)

### `build-randomize <user_id> <source> <dest> [--m3u PATH]`
Materialize source playlist, `_shuffle_list`, `finalize_playlist`, optional M3U.

### `copy-playlist-all-users <source_user_id> <source_playlist>`
Resolve source via `_server_for_user(plex, source_user_id)`. Copy to every user from `account.users()`. Naming rules per target: absent → create; exists → try `+ " admin copy"`; that also exists → overwrite. Warn per-user on failure; don't abort.

### `copy-playlist-to-user <source_user_id> <source_playlist> <user_id> <dest>`
Same source resolution and naming rules; single target.

### `export-playlist <user_id> <playlist> <path>`
`path` is a required positional. Fetch playlist, reject if empty, `_write_m3u`, print confirmation.

### `remove-playlist <user_id> <playlist>`
Delete; respect `--dry-run`; fail fast if not found.

### `append-playlist <user_id> <playlist> <ratingKey...>`
Fetch each item (fail fast on unknown key), numbered preview, `--dry-run`, `playlist.addItems(new_items)`.

### `export-titles <library_id> <output_path> [--sort alpha|date|random] [--album ALBUM]`
Sort modes — `_apply_sort(items, mode)`:
* `alpha` (default): episodes → `(grandparentTitle, seasonNumber, index)`; others → `(title, 0, 0)`
* `date`: `originallyAvailableAt` falling back to `addedAt`; undated → `datetime.datetime.max`
* `random`: `_shuffle_list`

Output by library type:
* `show`/`movie` → `_write_m3u`
* `photo` → `_write_gallery_html` (see below)

`--album` silently ignored with warning for non-photo libraries.

### `write-config-example`
Write template INI to `CONFIG_PATH`; create parent dirs; no Plex connection required.

---

## PHOTO LIBRARY HELPERS

### `_collect_photos(section, album=None) -> List[Photo]`
Walk `section.all()` (album objects) then `palbum.photos()` for each. **Never** use `section.search(libtype="photo")` — Plex requires a non-empty query string and returns nothing otherwise. If `album` given: compare `palbum.title` case-insensitively; skip non-matching albums; `sys.exit` if no photos found (suggest `list-titles`).

### `_collect_library_items(section, album=None) -> List[MediaItem]`
`show` → walk `_non_special_episodes`; `movie` → `section.all()`; `photo` → `_collect_photos(section, album)`; else `sys.exit` with supported types listed.

---

## PHOTO GALLERY — `_write_gallery_html(photos, output_path, library_title)`

**No `plex` parameter.** No Plex HTTP URLs anywhere in the output — all `href` and `src` attributes use server filesystem paths only.

### Path helpers (no `plex` parameter):
* `_photo_file_path(photo) -> Optional[str]`: `photo.media[0].parts[0].file`; return `None` on `IndexError`/`AttributeError`
* `_photo_thumb_url` does **not** exist — removed

### Fragment helpers:
* `_gallery_photo_anchor(photo) -> List[str]`: call `_photo_file_path`; if `None` return `[]` (skip, log debug). Both `href` and `src` use the same filesystem path.
* `_gallery_album_section(album_name, album_photos) -> List[str]`: no `plex` param
* `_group_photos_by_album(photos) -> Dict[str, List[Photo]]`: group by `parentTitle`; fallback `"Uncategorised"`

### `_write_gallery_html(photos, output_path, library_title)`:
Groups photos by album (sorted alphabetically). Spotlight.js and CSS from jsDelivr CDN (for the lightbox JS/CSS only — not for images). Design: near-black `#0d0d0d` bg; amber `#a0835c` library title; muted small-caps album headings with count; `192×192px` cover-fit grid; `scale(1.06)` hover; `loading="lazy"`; `prefers-reduced-motion` respected. `data-title` = photo title; `data-description` = `originallyAvailableAt`. Gallery title for single-album export: `"Library — Album"`.

---

## ARGPARSE STRUCTURE

`build_parser()` registers subparsers up through `build-randomize`, then calls `_register_copy_and_mutation_subparsers(sub)` to stay under pylint's statement limit. That helper registers: `copy-playlist-all-users`, `copy-playlist-to-user`, `export-playlist`, `remove-playlist`, `append-playlist`, `export-titles`, `write-config-example`.

Commands with `--m3u`: `list-playlist`, `list-show`, `build-interleaved`, `build-chronological`, `build-randomize`.

---

## ERROR HANDLING

`sys.exit()` with clear messages for: missing config, missing token, unknown ratingKey, wrong media type, playlist not found, user not found, unsupported library type, album not found, library ID not found. No bare `except` except in `_cancel_all_scans` (swallowing idle-section errors) and per-user copy failures — both with `# pylint: disable=broad-except`.

---

## BASH COMPLETION — `plex.do.bash-completion.inc`

* No `_init_completion` or `_filedir` dependency — init via `COMP_WORDS`/`COMP_CWORD` directly; file completion via `compgen -f`
* 15-minute TTL; `stat` portable between Linux (`-c %Y`) and macOS (`-f %m`)
* Background refresh: `_plexdo_bg_refresh cmd args... >/dev/null 2>&1 &` with `disown`
* `_plexdo_json_candidates cache field` — inline Python reads cache, emits matching values

### Completion helpers:
* `_plexdo_complete_user_id` → `0` + IDs from `users.json`
* `_plexdo_complete_library_id` → IDs from `libraries.json`; background refresh if stale
* `_plexdo_complete_rating_key` → ratingKeys merged from all `titles.*.json`; per-library stale refresh; triggers `list-libraries` → `list-titles` chain if nothing cached
* `_plexdo_complete_playlist(uid)` → titles from `playlists.<uid>.json`
* `_plexdo_complete_playlist_id_or_name(uid)` → both ratingKeys AND titles deduplicated — for `list-playlist` which accepts either form
* `_plexdo_complete_album(library_id)` → unique album prefixes extracted from `titles.<id>.json` by splitting `"Album - Photo Title"` on `" - "`
* `_plexdo_find_cmd`, `_plexdo_positional_count(cmd)` (skips `--m3u <val>` pairs), `_plexdo_nth_positional(cmd, n)`

### Per-command completion table:
| Command | pos 0 | pos 1 | pos 2 | pos 3 | special flags |
|---|---|---|---|---|---|
| `list-titles` | library_id | — | — | — | `--album` → album names |
| `search` | user_id | free | — | — | `--media-type` → type list; `--library-id` → library IDs |
| `list-playlists` | user_id | — | — | — | — |
| `list-playlist` | user_id | playlist-id-or-name | — | — | `--m3u` → file |
| `list-show` | rating_key | — | — | — | `--m3u` → file |
| `show-metadata` | rating_key | — | — | — | — |
| `read` | library_id | rating_key | — | — | — |
| `rescan` | library_id | — | — | — | `-s/--status`; `-n/--now` |
| `build-interleaved` | free (name) | rating_key… | — | — | `--m3u` → file |
| `build-chronological` | free (name) | rating_key… | — | — | `--m3u` → file |
| `build-randomize` | user_id | playlist | free | — | `--m3u` → file |
| `copy-playlist-all-users` | user_id | playlist | — | — | — |
| `copy-playlist-to-user` | user_id | playlist | user_id | playlist | — |
| `remove-playlist` | user_id | playlist | — | — | — |
| `export-playlist` | user_id | playlist | file path | — | — |
| `append-playlist` | user_id | playlist | rating_key… | — | — |
| `export-titles` | library_id | file path | — | — | `--sort` → `alpha date random`; `--album` → album names |

Register as: `complete -F _plexdo_complete plex.do` and `complete -F _plexdo_complete plex_do`.

---

## DELIVERABLES

1. `plex.do` — complete executable Python script (~1900 lines)
2. `requirements.txt` — `PlexAPI>=4.15.10` (requests is a transitive dependency, no separate entry needed)
3. `plex.do.bash-completion.inc` — installable via `source` or drop into `~/.local/share/bash-completion/completions/`
