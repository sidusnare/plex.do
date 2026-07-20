#!/usr/bin/env python3
"""plex.do – A production-quality CLI for Plex Media Server via plexapi.

Configuration: ~/.local/etc/plex.do.ini
"""

# pylint: disable=too-many-lines

import argparse
import configparser
import datetime
import html as html_lib
import json
import logging
import secrets
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple, Union

from plexapi.audio import Track
from plexapi.photo import Photo
from plexapi.exceptions import NotFound
from plexapi.myplex import MyPlexAccount, MyPlexUser
from plexapi.playlist import Playlist
from plexapi.server import PlexServer
from plexapi.video import Episode, Movie, Show

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
DateInput = Union[str, datetime.date, datetime.datetime, None]
MediaItem = Union[Episode, Movie, Track, Photo]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CONFIG_PATH = Path("~/.local/etc/plex.do.ini").expanduser()
CACHE_DIR = Path("~/.cache/plex.do").expanduser()
LOG = logging.getLogger("plex.do")


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def configure_logging(verbose: bool, debug: bool) -> None:
    """Configure logging to stderr only (never stdout)."""
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(level)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def load_config() -> configparser.ConfigParser:
    """Load and return the INI config, failing fast if absent."""
    if not CONFIG_PATH.exists():
        sys.exit(
            f"Config not found: {CONFIG_PATH}\n"
            "Run `plex.do write-config-example` to create a template."
        )
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH, encoding="utf-8")
    LOG.debug("Loaded config from %s", CONFIG_PATH)
    return cfg


def read_token(token_path_raw: str) -> str:
    """Expand path and read Plex token, failing fast if absent."""
    token_path = Path(token_path_raw).expanduser()
    if not token_path.exists():
        sys.exit(f"Token file not found: {token_path}")
    token = token_path.read_text(encoding="utf-8").strip()
    LOG.debug("Token loaded from %s", token_path)
    return token


def connect_plex(cfg: configparser.ConfigParser) -> PlexServer:
    """Create and return a connected PlexServer instance."""
    url = cfg.get("plex", "url")
    token_path = cfg.get("plex", "token_path")
    token = read_token(token_path)
    LOG.info("Connecting to Plex at %s", url)
    return PlexServer(url, token)


# ---------------------------------------------------------------------------
# Completion cache
# ---------------------------------------------------------------------------

def _write_cache(name: str, data: List[Dict[str, Any]]) -> None:
    """Atomically write data to the completion cache, silently ignoring errors."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / f"{name}.json"
        tmp = cache_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(cache_file)
        LOG.debug("Cache updated: %s", cache_file)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Type helpers
# ---------------------------------------------------------------------------

def normalize_rating_key(raw: Any) -> int:
    """Cast any ratingKey representation to int."""
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid ratingKey: {raw!r}") from exc


def parse_date(value: DateInput) -> Optional[datetime.datetime]:
    """Normalize a date-like value to datetime.datetime, or None."""
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.datetime.strptime(value, fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse date string: {value!r}")
    raise TypeError(f"Unsupported date type: {type(value)}")


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def output(data: Any, args: argparse.Namespace) -> None:
    """Emit data as JSON or delegate to print_table."""
    if args.json:
        print(json.dumps(data, default=str))
    else:
        if isinstance(data, list) and data and isinstance(data[0], dict):
            print_table(data)
        else:
            print(data)


def _cell(value: Any) -> str:
    """Convert a table cell value to a clean string, stripping control characters."""
    return str(value).strip()


def print_table(rows: List[Dict[str, Any]]) -> None:
    """Print a list of dicts as an aligned table to stdout."""
    if not rows:
        return
    headers = list(rows[0].keys())
    col_widths: Dict[str, int] = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            col_widths[h] = max(col_widths[h], len(_cell(row.get(h, ""))))

    sep = "  "
    header_line = sep.join(h.ljust(col_widths[h]) for h in headers)
    divider = sep.join("-" * col_widths[h] for h in headers)
    print(header_line)
    print(divider)
    for row in rows:
        print(sep.join(_cell(row.get(h, "")).ljust(col_widths[h]) for h in headers))


def print_metadata(record: Dict[str, Any]) -> None:
    """Print a key-value metadata record with aligned columns."""
    if not record:
        return
    key_width = max(len(k) for k in record)
    for key, value in record.items():
        print(f"{key.ljust(key_width)}  {_cell(value)}")


# ---------------------------------------------------------------------------
# Playlist finalization
# ---------------------------------------------------------------------------

def _display_title(item: Any) -> str:
    """Return a display title, prepending series name for TV episodes."""
    if isinstance(item, Episode):
        return f"{item.grandparentTitle} - {item.title}"
    return item.title


def finalize_playlist(
    plex: PlexServer,
    name: str,
    items: List[MediaItem],
    args: argparse.Namespace,
) -> None:
    """Validate, preview, and (unless --dry-run) create the playlist via one API call."""
    if not items:
        sys.exit("Playlist is empty — aborting.")

    LOG.info("Playlist '%s': %d items", name, len(items))

    preview_rows = [
        {
            "index": i + 1,
            "ratingKey": normalize_rating_key(item.ratingKey),
            "title": _display_title(item),
        }
        for i, item in enumerate(items)
    ]
    output(preview_rows, args)

    if args.dry_run:
        LOG.info("--dry-run: skipping playlist creation.")
        return

    plex.createPlaylist(name, items=items)
    LOG.info("Playlist '%s' created with %d items.", name, len(items))


# ---------------------------------------------------------------------------
# Command: write-config-example
# ---------------------------------------------------------------------------

def cmd_write_config_example(_plex: Optional[PlexServer], _args: argparse.Namespace) -> None:
    """Write a template config file."""
    example = (
        "[plex]\n"
        "url = http://localhost:32400\n"
        "token_path = ~/usr/tmp/.fsec/plex_token\n"
    )
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(example, encoding="utf-8")
    print(f"Config example written to: {CONFIG_PATH}")


# ---------------------------------------------------------------------------
# Command: list-libraries
# ---------------------------------------------------------------------------

def cmd_list_libraries(plex: PlexServer, args: argparse.Namespace) -> None:
    """List all Plex libraries."""
    rows = [
        {
            "id": normalize_rating_key(lib.key),
            "type": lib.type,
            "title": lib.title,
        }
        for lib in plex.library.sections()
    ]
    _write_cache("libraries", rows)
    output(rows, args)


# ---------------------------------------------------------------------------
# Command: list-titles
# ---------------------------------------------------------------------------

def cmd_list_titles(plex: PlexServer, args: argparse.Namespace) -> None:
    """List titles in a library."""
    library_id = args.library_id
    try:
        section = plex.library.sectionByID(library_id)
    except NotFound:
        sys.exit(f"Library ID not found: {library_id}")

    rows = [
        {
            "ratingKey": normalize_rating_key(item.ratingKey),
            "title": _display_title(item),
        }
        for item in section.all()
    ]
    _write_cache(f"titles.{library_id}", rows)
    output(rows, args)


# ---------------------------------------------------------------------------
# Command: search
# ---------------------------------------------------------------------------

_SEARCH_MEDIA_TYPES = ("movie", "show", "episode", "track", "photo", "album", "artist")


def _search_result_row(item: Any) -> Dict[str, Any]:
    """Build a result row from a search hit, resolving the library id."""
    # plexapi attaches a librarySectionID attribute to all fetched items.
    lib_id = normalize_rating_key(
        getattr(item, "librarySectionID", 0)
    )
    return {
        "ratingKey": normalize_rating_key(item.ratingKey),
        "libraryId": lib_id,
        "type":      item.type,
        "title":     _display_title(item),
    }


def _search_in_section(
    section: Any,
    query: str,
    media_type: Optional[str],
) -> List[Dict[str, Any]]:
    """Search a single library section, optionally filtered by media type."""
    kwargs: Dict[str, Any] = {}
    if media_type:
        kwargs["libtype"] = media_type
    try:
        hits = section.search(query, **kwargs)
    except Exception as exc:  # pylint: disable=broad-except
        LOG.warning("Search failed in library '%s': %s", section.title, exc)
        return []
    return [_search_result_row(item) for item in hits]  # type: ignore[arg-type]


def _search_all_sections(
    user_plex: PlexServer,
    query: str,
    media_type: Optional[str],
    library_id: Optional[int],
) -> List[Dict[str, Any]]:
    """Run the search across one or all library sections."""
    sections = user_plex.library.sections()
    if library_id is not None:
        try:
            sections = [user_plex.library.sectionByID(library_id)]
        except NotFound:
            sys.exit(f"Library ID not found: {library_id}")

    rows: List[Dict[str, Any]] = []
    for section in sections:
        kwargs: Dict[str, Any] = {}
        if media_type:
            kwargs["libtype"] = media_type
        try:
            hits = section.search(query, **kwargs)
        except Exception as exc:  # pylint: disable=broad-except
            LOG.warning("Search failed in library '%s': %s", section.title, exc)
            continue
        for item in hits:
            rows.append(_search_result_row(item))
    return rows


def cmd_search(plex: PlexServer, args: argparse.Namespace) -> None:
    """Search Plex for titles matching a query string."""
    user_plex = _server_for_user(plex, args.user_id)
    library_id: Optional[int] = args.library_id
    media_type: Optional[str] = args.media_type

    LOG.info(
        "Searching for %r (type=%s library=%s)", args.query, media_type, library_id
    )
    rows = _search_all_sections(user_plex, args.query, media_type, library_id)

    if not rows:
        LOG.info("No results found.")
    output(rows, args)


# ---------------------------------------------------------------------------
# Command: list-users
# ---------------------------------------------------------------------------

def cmd_list_users(plex: PlexServer, args: argparse.Namespace) -> None:
    """List managed/home users visible to the admin token."""
    account = plex.myPlexAccount()
    rows = [
        {"id": normalize_rating_key(u.id), "title": u.title}
        for u in account.users()
    ]
    _write_cache("users", rows)
    output(rows, args)


# ---------------------------------------------------------------------------
# Command: list-playlists
# ---------------------------------------------------------------------------

def _server_for_user(plex: PlexServer, user_id: int) -> PlexServer:
    """Return a PlexServer scoped to the given user.

    Pass user_id=0 to use the admin account (the token from config).
    For all other IDs, uses get_token(machineIdentifier) which works for
    both shared users and Plex Home managed users.
    """
    if user_id == 0:
        LOG.debug("user_id=0: using admin account")
        return plex
    account = plex.myPlexAccount()
    user: MyPlexUser = _find_user_by_id(account, user_id)
    token = user.get_token(plex.machineIdentifier)
    LOG.debug("Resolved token for user '%s' (id=%d)", user.title, user_id)
    return PlexServer(plex._baseurl, token)  # pylint: disable=protected-access


def _find_user_by_id(account: MyPlexAccount, user_id: int) -> MyPlexUser:
    """Locate a MyPlexUser by numeric id, failing fast if absent."""
    for user in account.users():
        if normalize_rating_key(user.id) == user_id:
            return user
    sys.exit(f"User ID not found: {user_id}")



def cmd_list_playlists(plex: PlexServer, args: argparse.Namespace) -> None:
    """List playlists for a given user."""
    user_plex = _server_for_user(plex, args.user_id)
    rows = [
        {
            "ratingKey": normalize_rating_key(pl.ratingKey),
            "title": pl.title,
            "items": pl.leafCount,
        }
        for pl in user_plex.playlists()
    ]
    _write_cache(f"playlists.{args.user_id}", rows)
    output(rows, args)


# ---------------------------------------------------------------------------
# Command: list-playlist
# ---------------------------------------------------------------------------

def _resolve_playlist(user_plex: PlexServer, identifier: str) -> Playlist:
    """Return a Playlist located by name or ratingKey string.

    If *identifier* parses as an integer it is treated as a ratingKey;
    otherwise it is treated as a title.  Fails fast with a clear message if
    not found or if the ratingKey refers to a non-playlist item.
    """
    try:
        rk = int(identifier)
        item = user_plex.fetchItem(rk)
        if not isinstance(item, Playlist):
            sys.exit(
                f"ratingKey {rk} is not a playlist (got {type(item).__name__})"
            )
        return item
    except ValueError:
        pass  # identifier is not numeric — fall through to name lookup
    try:
        return user_plex.playlist(identifier)
    except NotFound:
        sys.exit(f"Playlist not found: {identifier!r}")


def cmd_list_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """List items inside a specific playlist for a user."""
    user_plex = _server_for_user(plex, args.user_id)
    playlist: Playlist = _resolve_playlist(user_plex, args.playlist)

    items: List[MediaItem] = list(playlist.items())
    rows = [
        {
            "index": i + 1,
            "ratingKey": normalize_rating_key(item.ratingKey),
            "title": _display_title(item),
        }
        for i, item in enumerate(items)
    ]
    output(rows, args)

    if args.m3u:
        _write_m3u(items, args.m3u)


# ---------------------------------------------------------------------------
# Command: list-show
# ---------------------------------------------------------------------------

def cmd_list_show(plex: PlexServer, args: argparse.Namespace) -> None:
    """List all episodes in a show, optionally exporting an M3U."""
    rating_key = normalize_rating_key(args.rating_key)
    show = _fetch_show(plex, rating_key)
    episodes: List[Episode] = _non_special_episodes(show)

    rows = [
        {
            "index": i + 1,
            "ratingKey": normalize_rating_key(ep.ratingKey),
            "season": ep.seasonNumber,
            "episode": ep.index,
            "title": _display_title(ep),
        }
        for i, ep in enumerate(episodes)
    ]
    output(rows, args)

    if args.m3u:
        _write_m3u(episodes, args.m3u)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Command: show-metadata
# ---------------------------------------------------------------------------

def _format_duration(milliseconds: Optional[int]) -> str:
    """Convert milliseconds to a human-readable H:MM:SS string."""
    if milliseconds is None:
        return ""
    total_seconds = milliseconds // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _base_metadata(item: Any) -> Dict[str, Any]:
    """Return metadata fields common to all media types."""
    return {
        "ratingKey":     normalize_rating_key(item.ratingKey),
        "type":          item.type,
        "title":         _display_title(item),
        "year":          getattr(item, "year", "") or "",
        "contentRating": _cell(getattr(item, "contentRating", "") or ""),
        "rating":        getattr(item, "rating", "") or "",
        "duration":      _format_duration(getattr(item, "duration", None)),
        "addedAt":       str(getattr(item, "addedAt", "") or ""),
        "updatedAt":     str(getattr(item, "updatedAt", "") or ""),
        "summary":       _cell(getattr(item, "summary", "") or ""),
    }


def _episode_metadata(ep: Episode) -> Dict[str, Any]:
    """Return metadata fields specific to Episode items."""
    record = _base_metadata(ep)
    record.update({
        "show":          _cell(ep.grandparentTitle or ""),
        "season":        ep.seasonNumber,
        "episode":       ep.index,
        "airDate":       str(ep.originallyAvailableAt or ""),
        "studio":        _cell(getattr(ep, "studio", "") or ""),
    })
    return record


def _movie_metadata(movie: Movie) -> Dict[str, Any]:
    """Return metadata fields specific to Movie items."""
    record = _base_metadata(movie)
    record.update({
        "studio":        _cell(getattr(movie, "studio", "") or ""),
        "airDate":       str(getattr(movie, "originallyAvailableAt", "") or ""),
        "tagline":       _cell(getattr(movie, "tagline", "") or ""),
        "genres":        ", ".join(g.tag for g in getattr(movie, "genres", [])),
        "directors":     ", ".join(d.tag for d in getattr(movie, "directors", [])),
    })
    return record


def _show_metadata(show: Show) -> Dict[str, Any]:
    """Return metadata fields specific to Show items."""
    record = _base_metadata(show)
    record.update({
        "studio":        _cell(getattr(show, "studio", "") or ""),
        "firstAired":    str(getattr(show, "originallyAvailableAt", "") or ""),
        "seasons":       getattr(show, "childCount", ""),
        "episodes":      getattr(show, "leafCount", ""),
        "genres":        ", ".join(g.tag for g in getattr(show, "genres", [])),
        "network":       _cell(getattr(show, "network", "") or ""),
    })
    return record


def _track_metadata(track: Track) -> Dict[str, Any]:
    """Return metadata fields specific to Track items."""
    record = _base_metadata(track)
    record.update({
        "album":         _cell(getattr(track, "parentTitle", "") or ""),
        "artist":        _cell(getattr(track, "grandparentTitle", "") or ""),
        "trackNumber":   getattr(track, "index", ""),
        "year":          getattr(track, "year", "") or "",
    })
    return record


_METADATA_BUILDERS = {
    "episode": _episode_metadata,
    "movie":   _movie_metadata,
    "show":    _show_metadata,
    "track":   _track_metadata,
}


def cmd_show_metadata(plex: PlexServer, args: argparse.Namespace) -> None:
    """Display metadata for a single item by ratingKey."""
    rating_key = normalize_rating_key(args.rating_key)
    try:
        item = plex.fetchItem(rating_key)
    except NotFound:
        sys.exit(f"ratingKey not found: {rating_key}")

    builder = _METADATA_BUILDERS.get(item.type, _base_metadata)
    record: Dict[str, Any] = builder(item)

    if args.json:
        print(json.dumps(record, default=str))
    else:
        print_metadata(record)


# ---------------------------------------------------------------------------
# Command: build-interleaved
# ---------------------------------------------------------------------------

def _fetch_show(plex: PlexServer, rating_key: int) -> Show:
    """Fetch a Show by ratingKey, failing fast on wrong type."""
    item = plex.fetchItem(rating_key)
    if not isinstance(item, Show):
        sys.exit(f"ratingKey {rating_key} is not a Show (got {type(item).__name__})")
    return item


def _non_special_episodes(show: Show) -> List[Episode]:
    """Return all episodes from non-special (season > 0) seasons."""
    return [
        ep
        for ep in show.episodes()
        if ep.seasonNumber is not None and ep.seasonNumber > 0
    ]


def _round_robin(episode_lists: List[List[Episode]]) -> Iterator[Episode]:
    """Yield episodes in round-robin order across multiple lists."""
    queues = [list(eps) for eps in episode_lists if eps]
    while queues:
        exhausted = []
        for queue in queues:
            if queue:
                yield queue.pop(0)
            if not queue:
                exhausted.append(queue)
        for q in exhausted:
            queues.remove(q)


def cmd_build_interleaved(plex: PlexServer, args: argparse.Namespace) -> None:
    """Build a round-robin interleaved playlist from multiple shows."""
    rating_keys = [normalize_rating_key(k) for k in args.rating_keys]
    episode_lists: List[List[Episode]] = []

    for rk in rating_keys:
        show = _fetch_show(plex, rk)
        eps = _non_special_episodes(show)
        LOG.info("Show '%s': %d episodes", show.title, len(eps))
        episode_lists.append(eps)

    items: List[MediaItem] = list(_round_robin(episode_lists))
    finalize_playlist(plex, args.name, items, args)

    if args.m3u:
        _write_m3u(items, args.m3u)


# ---------------------------------------------------------------------------
# Command: build-chronological – date resolution helpers
# ---------------------------------------------------------------------------

def _aired_dt(ep: Episode) -> Optional[datetime.datetime]:
    """Return parsed originallyAvailableAt, or None."""
    return parse_date(ep.originallyAvailableAt)


def _episodes_in_same_season(ep: Episode, all_eps: List[Episode]) -> List[Episode]:
    """Return all episodes in the same season as ep (excluding ep itself)."""
    return [
        e for e in all_eps
        if e.seasonNumber == ep.seasonNumber
        and normalize_rating_key(e.ratingKey) != normalize_rating_key(ep.ratingKey)
    ]


def _collect_neighbors(
    ep: Episode, season_eps: List[Episode]
) -> Tuple[List[datetime.datetime], List[datetime.datetime]]:
    """
    Return (prev_dates, next_dates) — up to 6 known dates on each side.
    Episodes are ordered by episodeNumber within the season.
    """
    ordered = sorted(
        (e for e in season_eps if e.index is not None),
        key=lambda e: e.index,
    )
    ep_index = ep.index or 0
    prev_dates: List[datetime.datetime] = []
    next_dates: List[datetime.datetime] = []

    for e in reversed(ordered):
        if e.index < ep_index:
            dt = _aired_dt(e)
            if dt is not None:
                prev_dates.append(dt)
            if len(prev_dates) >= 6:
                break

    for e in ordered:
        if e.index > ep_index:
            dt = _aired_dt(e)
            if dt is not None:
                next_dates.append(dt)
            if len(next_dates) >= 6:
                break

    return prev_dates, next_dates


def _median_interval(dates: List[datetime.datetime]) -> Optional[datetime.timedelta]:
    """Compute the median timedelta between adjacent sorted dates."""
    sorted_dates = sorted(dates)
    if len(sorted_dates) < 3:  # need ≥3 dates → ≥2 intervals
        return None
    intervals = [
        (sorted_dates[i + 1] - sorted_dates[i]).total_seconds()
        for i in range(len(sorted_dates) - 1)
    ]
    if len(intervals) < 2:
        return None
    return datetime.timedelta(seconds=statistics.median(intervals))


def _estimate_date(
    prev_dates: List[datetime.datetime],
    next_dates: List[datetime.datetime],
) -> Optional[datetime.datetime]:
    """Estimate a missing air date from neighboring known dates."""
    all_known = prev_dates + next_dates
    median_td = _median_interval(all_known)
    if median_td is None:
        return None

    estimates: List[datetime.datetime] = []
    if prev_dates:
        latest_prev = max(prev_dates)
        estimates.append(latest_prev + median_td)
    if next_dates:
        earliest_next = min(next_dates)
        estimates.append(earliest_next - median_td)

    if not estimates:
        return None
    if len(estimates) == 1:
        return estimates[0]
    avg_ts = sum(e.timestamp() for e in estimates) / len(estimates)
    return datetime.datetime.fromtimestamp(avg_ts)


def _prompt_for_date(ep: Episode, last_used: Optional[datetime.datetime]) -> datetime.datetime:
    """Interactively ask the user for a missing air date."""
    example = last_used.strftime("%Y-%m-%d") if last_used else "2000-01-01"
    prompt = (
        f"\nCannot resolve air date for: {ep.grandparentTitle} "
        f"S{ep.seasonNumber:02d}E{ep.index:02d} – {ep.title}\n"
        f"Enter date (YYYY-MM-DD) [example: {example}]: "
    )
    while True:
        raw = input(prompt).strip()
        try:
            return datetime.datetime.strptime(raw, "%Y-%m-%d")
        except ValueError:
            print("Invalid format, please use YYYY-MM-DD.")


def _resolve_episode_date(
    ep: Episode,
    season_peers: List[Episode],
    last_used: Optional[datetime.datetime],
) -> datetime.datetime:
    """Return a resolved datetime for an episode, estimating or prompting if needed."""
    dt = _aired_dt(ep)
    if dt is not None:
        return dt

    prev_dates, next_dates = _collect_neighbors(ep, season_peers)
    estimated = _estimate_date(prev_dates, next_dates)
    if estimated is not None:
        LOG.info(
            "Estimated date for '%s' S%02dE%02d: %s",
            ep.grandparentTitle,
            ep.seasonNumber,
            ep.index,
            estimated.date(),
        )
        return estimated

    return _prompt_for_date(ep, last_used)


def _chronological_sort_key(
    item_date: Tuple[MediaItem, datetime.datetime]
) -> datetime.datetime:
    return item_date[1]


def _build_chronological_items(
    plex: PlexServer,
    rating_keys: List[int],
) -> List[Tuple[MediaItem, datetime.datetime]]:
    """Build (item, resolved_datetime) pairs for all given shows/movies."""
    dated_items: List[Tuple[MediaItem, datetime.datetime]] = []
    last_used_date: Optional[datetime.datetime] = None

    for rk in rating_keys:
        media_item = plex.fetchItem(rk)
        LOG.debug("Processing ratingKey=%d type=%s", rk, type(media_item).__name__)

        if isinstance(media_item, Show):
            all_eps = _non_special_episodes(media_item)
            for ep in all_eps:
                season_peers = _episodes_in_same_season(ep, all_eps)
                resolved = _resolve_episode_date(ep, season_peers, last_used_date)
                last_used_date = resolved
                dated_items.append((ep, resolved))

        elif isinstance(media_item, Movie):
            dt = parse_date(media_item.originallyAvailableAt)
            if dt is None:
                dt = _prompt_for_date(media_item, last_used_date)  # type: ignore[arg-type]
            last_used_date = dt
            dated_items.append((media_item, dt))

        else:
            sys.exit(
                f"ratingKey {rk} is type '{type(media_item).__name__}' "
                "— only Show and Movie are supported."
            )

    return dated_items


def _write_m3u(sorted_items: List[MediaItem], path: str) -> None:
    """Write an M3U playlist using Plex server filesystem paths."""
    lines: List[str] = ["#EXTM3U"]
    for item in sorted_items:
        duration_ms = getattr(item, "duration", None)
        seconds = int(duration_ms / 1000) if duration_ms else -1
        for media in getattr(item, "media", []):
            for part in getattr(media, "parts", []):
                file_path = getattr(part, "file", None)
                if not file_path:
                    continue
                lines.append(f"#EXTINF:{seconds},{_display_title(item)}")
                lines.append(file_path)

    output_path = Path(path).expanduser()
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOG.info("M3U written to %s (%d lines)", output_path, len(lines))


def cmd_build_chronological(plex: PlexServer, args: argparse.Namespace) -> None:
    """Build a date-sorted playlist from shows and/or movies."""
    rating_keys = [normalize_rating_key(k) for k in args.rating_keys]
    dated_items = _build_chronological_items(plex, rating_keys)

    dated_items.sort(key=_chronological_sort_key)
    items: List[MediaItem] = [item for item, _ in dated_items]

    finalize_playlist(plex, args.name, items, args)

    if args.m3u:
        _write_m3u(items, args.m3u)


# ---------------------------------------------------------------------------
# Command: build-randomize
# ---------------------------------------------------------------------------

def _shuffle_list(lst: List[Any]) -> List[Any]:
    """Fisher-Yates shuffle using secrets.randbelow."""
    result = list(lst)
    for i in range(len(result) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        result[i], result[j] = result[j], result[i]
    return result


def cmd_build_randomize(plex: PlexServer, args: argparse.Namespace) -> None:
    """Randomize a playlist and save to a new destination playlist."""
    user_plex = _server_for_user(plex, args.user_id)
    try:
        src: Playlist = user_plex.playlist(args.source)
    except NotFound:
        sys.exit(f"Source playlist not found: {args.source!r}")

    all_items: List[MediaItem] = list(src.items())
    randomized: List[MediaItem] = _shuffle_list(all_items)

    LOG.info("Randomized %d items", len(randomized))
    finalize_playlist(user_plex, args.dest, randomized, args)

    if args.m3u:
        _write_m3u(randomized, args.m3u)


# ---------------------------------------------------------------------------
# Command: export-titles
# ---------------------------------------------------------------------------

_LIBRARY_ITEM_TYPES = ("show", "movie", "photo")

_DATE_SENTINEL = datetime.datetime.max  # sort undated items last


def _collect_library_items(section: Any) -> List[MediaItem]:
    """Expand a library section into a flat list of playable items.

    TV show libraries are walked show -> season (>0) -> episode.
    Movie libraries return movies directly.
    """
    if section.type == "show":
        items: List[MediaItem] = []
        for show in section.all():
            items.extend(_non_special_episodes(show))
        return items
    if section.type == "movie":
        return list(section.all())
    if section.type == "photo":
        return list(section.search(libtype="photo"))
    sys.exit(
        f"Library type '{section.type}' is not supported. "
        f"Supported types: {', '.join(_LIBRARY_ITEM_TYPES)}."
    )


def _alpha_sort_key(item: MediaItem) -> Tuple[str, int, int]:
    """Sort key for alphabetical ordering.

    Episodes sort by show title, then season, then episode index so that all
    episodes of a show stay together in air order.  Movies sort by title.
    """
    if isinstance(item, Episode):
        return (
            _cell(item.grandparentTitle or ""),
            item.seasonNumber or 0,
            item.index or 0,
        )
    return (_cell(item.title or ""), 0, 0)


def _date_sort_key(item: MediaItem) -> datetime.datetime:
    """Sort key for air-date ordering; undated items sort last.

    Falls back to addedAt (useful for photos that lack EXIF dates).
    """
    raw = (getattr(item, "originallyAvailableAt", None)
           or getattr(item, "addedAt", None))
    return parse_date(raw) or _DATE_SENTINEL


def _apply_sort(items: List[MediaItem], sort_mode: str) -> List[MediaItem]:
    """Return a new list sorted according to sort_mode."""
    if sort_mode == "date":
        return sorted(items, key=_date_sort_key)
    if sort_mode == "random":
        return _shuffle_list(items)
    return sorted(items, key=_alpha_sort_key)  # default: "alpha"


def _photo_thumb_url(plex: PlexServer, photo: Photo) -> str:
    """Return the Plex-served thumbnail URL for a photo, token included."""
    return plex.url(photo.thumb, includeToken=True)


def _photo_full_url(plex: PlexServer, photo: Photo) -> str:
    """Return the Plex-served full-resolution URL for a photo, token included."""
    try:
        return plex.url(photo.media[0].parts[0].key, includeToken=True)
    except (IndexError, AttributeError):
        return _photo_thumb_url(plex, photo)


def _gallery_css() -> str:
    """Return the embedded CSS for the photo gallery."""
    return """
    :root {
      --bg:     #0d0d0d;
      --surf:   #141414;
      --accent: #a0835c;
      --text:   #e0e0e0;
      --muted:  #4a4a4a;
      --gap:    4px;
      --thumb:  192px;
    }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, sans-serif;
      min-height: 100vh;
    }
    #hdr {
      display: flex;
      align-items: baseline;
      gap: 1.2rem;
      padding: 1.2rem 2rem;
      background: var(--surf);
      border-bottom: 1px solid #1c1c1c;
      position: sticky;
      top: 0;
      z-index: 10;
    }
    #hdr h1 {
      font-size: .9rem;
      font-weight: 600;
      letter-spacing: .1em;
      text-transform: uppercase;
      color: var(--accent);
    }
    #hdr .total {
      font-size: .75rem;
      color: var(--muted);
    }
    .album { padding: 1.6rem 2rem 0.4rem; }
    .album-hdr {
      display: flex;
      align-items: baseline;
      gap: .7rem;
      padding-bottom: .5rem;
      margin-bottom: .8rem;
      border-bottom: 1px solid #1c1c1c;
    }
    .album-hdr h2 {
      font-size: .7rem;
      letter-spacing: .1em;
      text-transform: uppercase;
      color: var(--muted);
      font-weight: 500;
    }
    .album-hdr .n { font-size: .65rem; color: #333; }
    .grid {
      display: flex;
      flex-wrap: wrap;
      gap: var(--gap);
    }
    .grid a {
      display: block;
      width: var(--thumb);
      height: var(--thumb);
      overflow: hidden;
      flex-shrink: 0;
      border-radius: 2px;
    }
    .grid img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      transition: transform .3s ease, opacity .3s ease;
    }
    .grid a:hover img { transform: scale(1.06); opacity: .8; }
    @media (prefers-reduced-motion: reduce) {
      .grid img { transition: none; }
    }
    """


def _gallery_photo_anchor(plex: PlexServer, photo: Photo) -> List[str]:
    """Return HTML lines for a single Spotlight.js photo anchor."""
    esc   = html_lib.escape
    thumb = esc(_photo_thumb_url(plex, photo))
    full  = esc(_photo_full_url(plex, photo))
    title = esc(_cell(photo.title or ""))
    taken = esc(str(getattr(photo, "originallyAvailableAt", "") or ""))
    return [
        f'      <a class="spotlight" href="{full}"',
        f'         data-title="{title}" data-description="{taken}">',
        f'        <img src="{thumb}" loading="lazy" alt="{title}">',
        "      </a>",
    ]


def _gallery_album_section(
    plex: PlexServer, album_name: str, album_photos: List[Photo]
) -> List[str]:
    """Return HTML lines for one album section."""
    esc = html_lib.escape
    lines: List[str] = [
        '  <section class="album">',
        '    <div class="album-hdr">',
        f'      <h2>{esc(album_name)}</h2>',
        f'      <span class="n">{len(album_photos)}</span>',
        "    </div>",
        '    <div class="grid spotlight-group">',
    ]
    for photo in album_photos:
        lines.extend(_gallery_photo_anchor(plex, photo))
    lines += ["    </div>", "  </section>"]
    return lines


def _group_photos_by_album(photos: List[Photo]) -> Dict[str, List[Photo]]:
    """Group photos by parentTitle, using 'Uncategorised' as fallback."""
    groups: Dict[str, List[Photo]] = {}
    for photo in photos:
        album = _cell(getattr(photo, "parentTitle", "") or "") or "Uncategorised"
        groups.setdefault(album, []).append(photo)
    return groups


def _write_gallery_html(
    plex: PlexServer,
    photos: List[Photo],
    output_path: str,
    library_title: str,
) -> None:
    """Write a Spotlight.js HTML5 gallery for a list of Photo objects.

    Photos are grouped by album (parentTitle).  The gallery uses CDN-hosted
    Spotlight.js for the lightbox and Plex server URLs for all images.
    """
    esc  = html_lib.escape
    cdn  = "https://cdn.jsdelivr.net/npm/spotlight.js"
    head = (
        ["<!DOCTYPE html>", '<html lang="en">', "<head>",
         '  <meta charset="UTF-8">',
         '  <meta name="viewport" content="width=device-width, initial-scale=1">',
         f"  <title>{esc(library_title)}</title>",
         f'  <link rel="stylesheet" href="{cdn}/dist/css/spotlight.min.css">',
         "  <style>"]
        + [f"  {l}" for l in _gallery_css().splitlines()]
        + ["  </style>", "</head>", "<body>",
           '  <header id="hdr">',
           f'    <h1>{esc(library_title)}</h1>',
           f'    <span class="total">{len(photos):,} photos</span>',
           "  </header>"]
    )
    albums = _group_photos_by_album(photos)
    body   = [l for name in sorted(albums)
               for l in _gallery_album_section(plex, name, albums[name])]
    foot   = [f'  <script src="{cdn}/dist/js/spotlight.bundle.min.js"></script>',
              "</body>", "</html>", ""]

    out = Path(output_path).expanduser()
    out.write_text("\n".join(head + body + foot), encoding="utf-8")
    LOG.info("Gallery written to %s (%d photos)", out, len(photos))


def cmd_export_titles(plex: PlexServer, args: argparse.Namespace) -> None:
    """Export an entire library to an M3U file."""
    try:
        section = plex.library.sectionByID(args.library_id)
    except NotFound:
        sys.exit(f"Library ID not found: {args.library_id}")

    LOG.info(
        "Collecting items from library '%s' (type=%s)", section.title, section.type
    )
    items = _collect_library_items(section)

    if not items:
        sys.exit(f"Library '{section.title}' contains no items.")

    sorted_items = _apply_sort(items, args.sort)
    LOG.info(
        "Exporting %d item(s) sorted by '%s' to %s",
        len(sorted_items), args.sort, args.output_path,
    )
    if section.type == "photo":
        _write_gallery_html(plex, sorted_items, args.output_path, section.title)
    else:
        _write_m3u(sorted_items, args.output_path)
        print(f"Exported {len(sorted_items)} items to: {args.output_path}")


# ---------------------------------------------------------------------------
# Command: export-playlist
# ---------------------------------------------------------------------------

def cmd_export_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """Export an existing playlist to an M3U file."""
    user_plex = _server_for_user(plex, args.user_id)
    try:
        playlist: Playlist = user_plex.playlist(args.playlist)
    except NotFound:
        sys.exit(f"Playlist not found: {args.playlist!r}")

    items: List[MediaItem] = list(playlist.items())
    if not items:
        sys.exit(f"Playlist '{args.playlist}' is empty — nothing to export.")

    LOG.info("Exporting %d items from '%s' to %s", len(items), args.playlist, args.m3u)
    _write_m3u(items, args.m3u)
    print(f"Exported {len(items)} items to: {args.m3u}")


# ---------------------------------------------------------------------------
# Command: copy-playlist helpers
# ---------------------------------------------------------------------------

def _resolve_dest_name(user_plex: PlexServer, desired_name: str) -> Tuple[str, bool]:
    """
    Return (final_name, overwrite).
    If desired_name doesn't exist → use it (no overwrite).
    If desired_name exists → try desired_name + ' admin copy'.
    If that also exists → overwrite it (return that name, overwrite=True).
    """
    existing = {pl.title for pl in user_plex.playlists()}
    if desired_name not in existing:
        return desired_name, False
    candidate = desired_name + " admin copy"
    if candidate not in existing:
        return candidate, False
    return candidate, True


def _copy_playlist_to(
    src_items: List[MediaItem],
    user_plex: PlexServer,
    desired_name: str,
    args: argparse.Namespace,
) -> None:
    """Copy items to user_plex under resolved name, applying naming rules."""
    final_name, overwrite = _resolve_dest_name(user_plex, desired_name)
    LOG.info("Copying to '%s' (overwrite=%s)", final_name, overwrite)

    if overwrite and not args.dry_run:
        try:
            existing_pl: Playlist = user_plex.playlist(final_name)
            existing_pl.delete()
            LOG.debug("Deleted existing playlist '%s'", final_name)
        except NotFound:
            pass

    finalize_playlist(user_plex, final_name, src_items, args)


def cmd_copy_playlist_all_users(plex: PlexServer, args: argparse.Namespace) -> None:
    """Copy a playlist from any user to all managed users."""
    src_plex = _server_for_user(plex, args.source_user_id)
    try:
        src: Playlist = src_plex.playlist(args.source_playlist)
    except NotFound:
        sys.exit(f"Source playlist not found: {args.source_playlist!r}")

    src_items: List[MediaItem] = list(src.items())
    account = plex.myPlexAccount()

    for user in account.users():
        user_id = normalize_rating_key(user.id)
        LOG.info("Copying to user '%s' (id=%d)", user.title, user_id)
        try:
            user_plex = _server_for_user(plex, user_id)
            _copy_playlist_to(src_items, user_plex, args.source_playlist, args)
        except Exception as exc:  # pylint: disable=broad-except
            LOG.warning("Failed for user '%s': %s", user.title, exc)


def cmd_copy_playlist_to_user(plex: PlexServer, args: argparse.Namespace) -> None:
    """Copy a playlist from any user to a specific user under a given name."""
    src_plex = _server_for_user(plex, args.source_user_id)
    try:
        src: Playlist = src_plex.playlist(args.source_playlist)
    except NotFound:
        sys.exit(f"Source playlist not found: {args.source_playlist!r}")

    src_items: List[MediaItem] = list(src.items())
    user_plex = _server_for_user(plex, args.user_id)
    _copy_playlist_to(src_items, user_plex, args.dest, args)


# ---------------------------------------------------------------------------
# Command: append-playlist
# ---------------------------------------------------------------------------

def cmd_append_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """Append one or more items to an existing playlist."""
    user_plex = _server_for_user(plex, args.user_id)
    try:
        playlist: Playlist = user_plex.playlist(args.playlist)
    except NotFound:
        sys.exit(f"Playlist not found: {args.playlist!r}")

    rating_keys = [normalize_rating_key(k) for k in args.rating_keys]
    new_items: List[MediaItem] = []
    for rk in rating_keys:
        try:
            new_items.append(user_plex.fetchItem(rk))
        except NotFound:
            sys.exit(f"ratingKey not found: {rk}")

    if not new_items:
        sys.exit("No items to append.")

    LOG.info("Appending %d item(s) to '%s'", len(new_items), args.playlist)

    preview_rows = [
        {
            "index": i + 1,
            "ratingKey": normalize_rating_key(item.ratingKey),
            "title": _display_title(item),
        }
        for i, item in enumerate(new_items)
    ]
    output(preview_rows, args)

    if args.dry_run:
        LOG.info("--dry-run: skipping append.")
        return

    playlist.addItems(new_items)
    LOG.info("Appended %d item(s) to '%s'.", len(new_items), args.playlist)


# ---------------------------------------------------------------------------
# Command: remove-playlist
# ---------------------------------------------------------------------------

def cmd_remove_playlist(plex: PlexServer, args: argparse.Namespace) -> None:
    """Delete a playlist from a user's account."""
    user_plex = _server_for_user(plex, args.user_id)
    try:
        playlist: Playlist = user_plex.playlist(args.playlist)
    except NotFound:
        sys.exit(f"Playlist not found: {args.playlist!r}")

    LOG.info("Removing playlist '%s' for user_id=%d", args.playlist, args.user_id)
    if args.dry_run:
        LOG.info("--dry-run: skipping playlist deletion.")
        return
    playlist.delete()
    print(f"Deleted playlist: {args.playlist!r}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _add_global_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json", action="store_true", default=False,
        help="Output machine-readable JSON instead of tables.",
    )
    parser.add_argument(
        "--verbose", action="store_true", default=False,
        help="Print high-level progress to stderr.",
    )
    parser.add_argument(
        "--debug", action="store_true", default=False,
        help="Print detailed internal logs to stderr.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False, dest="dry_run",
        help="Show what would happen without mutating Plex.",
    )


def build_parser() -> argparse.ArgumentParser:
    """Construct and return the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="plex.do",
        description="Interact with a Plex Media Server via plexapi.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_global_flags(parser)
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # list-libraries
    sub.add_parser(
        "list-libraries",
        help="List all Plex libraries (id, type, title).",
    )

    # list-titles
    p_lt = sub.add_parser("list-titles", help="List titles in a library.")
    p_lt.add_argument(
        "library_id", type=int,
        help="Library ID (int). Obtain with list-libraries.",
    )

    # search
    p_srch = sub.add_parser(
        "search",
        help="Search Plex for titles matching a query string.",
    )
    p_srch.add_argument(
        "user_id", type=int,
        help="User ID (int); use 0 for the admin account. Obtain other IDs with list-users.",
    )
    p_srch.add_argument(
        "query",
        help="Search string (str). Plex performs a prefix/substring match.",
    )
    p_srch.add_argument(
        "--media-type", dest="media_type",
        choices=list(_SEARCH_MEDIA_TYPES), default=None, metavar="TYPE",
        help=(
            "Restrict results to a single media type. "
            f"Choices: {', '.join(_SEARCH_MEDIA_TYPES)}."
        ),
    )
    p_srch.add_argument(
        "--library-id", dest="library_id", type=int, default=None, metavar="ID",
        help="Restrict search to a single library ID. Obtain IDs with list-libraries.",
    )

    # list-users
    sub.add_parser("list-users", help="List all managed/home users (id, title).")

    # list-playlists
    p_lpl = sub.add_parser("list-playlists", help="List playlists for a user.")
    p_lpl.add_argument(
        "user_id", type=int,
        help="User ID (int); use 0 for the admin account. Obtain other IDs with list-users.",
    )

    # list-playlist
    p_lp = sub.add_parser("list-playlist", help="List items in a specific playlist.")
    p_lp.add_argument(
        "user_id", type=int,
        help="User ID (int); use 0 for the admin account. Obtain other IDs with list-users.",
    )
    p_lp.add_argument(
        "playlist", type=str,
        help="Playlist name (str) or ratingKey (int). Obtain either with list-playlists.",
    )
    p_lp.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )

    # list-show
    p_ls = sub.add_parser(
        "list-show",
        help="List all episodes in a show (skipping specials), with optional M3U export.",
    )
    p_ls.add_argument(
        "rating_key", type=int,
        help="Show ratingKey (int). Obtain with list-titles.",
    )
    p_ls.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )

    # show-metadata
    p_sm = sub.add_parser(
        "show-metadata",
        help="Display metadata for a single item by ratingKey.",
    )
    p_sm.add_argument(
        "rating_key", type=int,
        help="Item ratingKey (int). Obtain with list-titles or list-show.",
    )

    # build-interleaved
    p_bi = sub.add_parser(
        "build-interleaved",
        help="Round-robin interleaved playlist from multiple shows.",
    )
    p_bi.add_argument("name", help="Name for the new playlist (str).")
    p_bi.add_argument(
        "rating_keys", nargs="+", type=int, metavar="ratingKey",
        help="One or more Show ratingKeys (int). Obtain with list-titles.",
    )
    p_bi.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )

    # build-chronological
    p_bc = sub.add_parser(
        "build-chronological",
        help="Date-sorted playlist from shows and/or movies.",
    )
    p_bc.add_argument("name", help="Name for the new playlist (str).")
    p_bc.add_argument(
        "rating_keys", nargs="+", type=int, metavar="ratingKey",
        help="One or more Show/Movie ratingKeys (int). Obtain with list-titles.",
    )
    p_bc.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )

    # build-randomize
    p_pr = sub.add_parser(
        "build-randomize",
        help="Randomize a source playlist into a new destination playlist.",
    )
    p_pr.add_argument(
        "user_id", type=int,
        help="User ID (int); use 0 for the admin account. Obtain other IDs with list-users.",
    )
    p_pr.add_argument("source", help="Source playlist title (str).")
    p_pr.add_argument("dest", help="Destination playlist title (str).")
    p_pr.add_argument(
        "--m3u", metavar="PATH",
        help="Also export an M3U file at PATH using Plex server filesystem paths.",
    )

    _register_copy_and_mutation_subparsers(sub)
    return parser


def _register_copy_and_mutation_subparsers(
    sub: argparse._SubParsersAction,  # pylint: disable=protected-access
) -> None:
    """Register copy, export, remove, and append subparsers."""
    uid_help = "User ID (int); use 0 for the admin account. Obtain other IDs with list-users."
    src_uid_help = "Source user ID (int); use 0 for the admin account. Obtain other IDs with list-users."

    p_cpau = sub.add_parser(
        "copy-playlist-all-users",
        help="Copy a playlist from any user to all managed users.",
    )
    p_cpau.add_argument("source_user_id", type=int, help=src_uid_help)
    p_cpau.add_argument("source_playlist", help="Source playlist title (str).")

    p_cptu = sub.add_parser(
        "copy-playlist-to-user",
        help="Copy a playlist from any user to a specific user.",
    )
    p_cptu.add_argument("source_user_id", type=int, help=src_uid_help)
    p_cptu.add_argument("source_playlist", help="Source playlist title (str).")
    p_cptu.add_argument("user_id", type=int, help=f"Target {uid_help}")
    p_cptu.add_argument("dest", help="Destination playlist title (str).")

    p_ep = sub.add_parser("export-playlist", help="Export an existing playlist to an M3U file.")
    p_ep.add_argument("user_id", type=int, help=uid_help)
    p_ep.add_argument("playlist", help="Playlist title to export (str).")
    p_ep.add_argument("m3u", metavar="PATH",
                      help="Destination M3U file path (Plex server filesystem paths will be used).")

    p_rp = sub.add_parser("remove-playlist", help="Delete a playlist from a user's account.")
    p_rp.add_argument("user_id", type=int, help=uid_help)
    p_rp.add_argument("playlist", help="Playlist title to delete (str).")

    p_ap = sub.add_parser("append-playlist",
                          help="Append one or more items to an existing playlist.")
    p_ap.add_argument("user_id", type=int, help=uid_help)
    p_ap.add_argument("playlist", help="Playlist title to append to (str).")
    p_ap.add_argument(
        "rating_keys", nargs="+", type=int, metavar="ratingKey",
        help="One or more item ratingKeys to append (int). Obtain with list-titles or list-show.",
    )

    # export-titles
    p_et = sub.add_parser(
        "export-titles",
        help="Export an entire library to an M3U file.",
    )
    p_et.add_argument(
        "library_id", type=int,
        help="Library ID (int). Obtain with list-libraries.",
    )
    p_et.add_argument(
        "output_path", metavar="PATH",
        help=(
            "Output file path. M3U for show/movie libraries; "
            "HTML gallery for photo libraries."
        ),
    )
    p_et.add_argument(
        "--sort", choices=["alpha", "date", "random"], default="alpha",
        help=(
            "Sort order: 'alpha' = alphabetical by title/show+episode (default), "
            "'date' = by original air date (undated items last), "
            "'random' = randomised."
        ),
    )

    sub.add_parser("write-config-example", help="Write a template config file.")


# ---------------------------------------------------------------------------
# Command dispatch
# ---------------------------------------------------------------------------

COMMANDS_REQUIRING_PLEX: Sequence[str] = (
    "list-libraries",
    "list-titles",
    "search",
    "list-users",
    "list-playlists",
    "list-playlist",
    "list-show",
    "show-metadata",
    "build-interleaved",
    "build-chronological",
    "build-randomize",
    "copy-playlist-all-users",
    "copy-playlist-to-user",
    "remove-playlist",
    "export-playlist",
    "append-playlist",
    "export-titles",
)

COMMAND_MAP = {
    "list-libraries": cmd_list_libraries,
    "list-titles": cmd_list_titles,
    "search": cmd_search,
    "list-users": cmd_list_users,
    "list-playlists": cmd_list_playlists,
    "list-playlist": cmd_list_playlist,
    "list-show": cmd_list_show,
    "show-metadata": cmd_show_metadata,
    "build-interleaved": cmd_build_interleaved,
    "build-chronological": cmd_build_chronological,
    "build-randomize": cmd_build_randomize,
    "copy-playlist-all-users": cmd_copy_playlist_all_users,
    "copy-playlist-to-user": cmd_copy_playlist_to_user,
    "remove-playlist": cmd_remove_playlist,
    "export-playlist": cmd_export_playlist,
    "append-playlist": cmd_append_playlist,
    "export-titles": cmd_export_titles,
    "write-config-example": cmd_write_config_example,
}


def main(argv: Optional[List[str]] = None) -> None:
    """Entry point for plex.do."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    configure_logging(args.verbose, args.debug)

    handler = COMMAND_MAP.get(args.command)
    if handler is None:
        sys.exit(f"Unknown command: {args.command}")

    if args.command in COMMANDS_REQUIRING_PLEX:
        cfg = load_config()
        plex = connect_plex(cfg)
        handler(plex, args)
    else:
        handler(None, args)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
