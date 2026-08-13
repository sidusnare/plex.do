# SPDX-License-Identifier: GPL-3.0-or-later

"""Library search command."""

from typing import Any, Dict, List, Optional
import argparse

from plexapi.server import PlexServer

from plexdo.accounts import _server_for_user
from plexdo.console import output
from plexdo.constants import LOG
from plexdo.convert import normalize_rating_key
from plexdo.sections import resolve_sections
from plexdo.titles import _display_title


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
    sections = resolve_sections(user_plex, library_id)
    rows: List[Dict[str, Any]] = []
    for section in sections:
        rows.extend(_search_in_section(section, query, media_type))
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


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the search subparser."""
    parser = sub.add_parser(
        "search", parents=parents,
        help="Search Plex for titles matching a query string.",
    )
    parser.add_argument(
        "user_id", metavar="USER",
        help="User ID (int) or user title (str); use 0 for the admin account. Obtain both with list-users.",
    )
    parser.add_argument(
        "query",
        help="Search string (str). Plex performs a prefix/substring match.",
    )
    parser.add_argument(
        "--media-type", dest="media_type",
        choices=list(_SEARCH_MEDIA_TYPES), default=None, metavar="TYPE",
        help=(
            "Restrict results to a single media type. "
            f"Choices: {', '.join(_SEARCH_MEDIA_TYPES)}."
        ),
    )
    parser.add_argument(
        "--library-id", dest="library_id", type=int, default=None, metavar="ID",
        help="Restrict search to a single library ID. Obtain IDs with list-libraries.",
    )


COMMANDS = {"search": cmd_search}

REQUIRES_PLEX = frozenset(COMMANDS)
