# SPDX-License-Identifier: GPL-3.0-or-later

"""Sort orders shared by the export commands."""

from typing import List, Tuple
import datetime

from plexapi.video import Episode

from plexdo.console import _cell
from plexdo.constants import MediaItem
from plexdo.convert import parse_date
from plexdo.titles import _shuffle_list


_DATE_SENTINEL = datetime.datetime.max  # sort undated items last


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
