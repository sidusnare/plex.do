# SPDX-License-Identifier: GPL-3.0-or-later

"""Item title formatting and common item helpers."""

from typing import Any, List
import secrets
import sys

from plexapi.exceptions import NotFound
from plexapi.server import PlexServer
from plexapi.video import Episode, Show

from plexdo.convert import normalize_rating_key


def _display_title(item: Any) -> str:
    """Return a display title, prepending series name for TV episodes."""
    if isinstance(item, Episode):
        return f"{item.grandparentTitle} - {item.title}"
    return item.title


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


def _shuffle_list(lst: List[Any]) -> List[Any]:
    """Fisher-Yates shuffle using secrets.randbelow."""
    result = list(lst)
    for i in range(len(result) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        result[i], result[j] = result[j], result[i]
    return result


def fetch_item(plex: PlexServer, rating_key: Any) -> Any:
    """Fetch a single item by ratingKey, failing fast if it does not exist."""
    key = normalize_rating_key(rating_key)
    try:
        return plex.fetchItem(key)
    except NotFound:
        sys.exit(f"ratingKey not found: {key}")
