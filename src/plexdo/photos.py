# SPDX-License-Identifier: GPL-3.0-or-later

"""Photo album traversal and library item collection."""

from typing import Any, List, Optional
import sys

from plexapi.photo import Photo

from plexdo.console import _cell
from plexdo.constants import MediaItem
from plexdo.titles import _non_special_episodes


_LIBRARY_ITEM_TYPES = ("show", "movie", "photo")


def _collect_photos(
    section: Any, album: Optional[str] = None
) -> List[Photo]:
    """Return photos from a photo library section, optionally filtered by album.

    Walks section.all() (albums) then album.photos() — the same pattern used
    for show libraries.  section.search(libtype="photo") is NOT used because
    Plex requires a non-empty query string and returns nothing for an empty one.

    If *album* is given, only photos from the matching album are returned
    (case-insensitive title match).  Fails fast if the name is not found.
    """
    photos: List[Photo] = []
    for palbum in section.all():
        album_title = _cell(getattr(palbum, "title", "") or "")
        if album is not None and album_title.lower() != album.lower():
            continue
        photos.extend(palbum.photos())

    if album is not None and not photos:
        sys.exit(
            f"Album '{album}' not found in library '{section.title}'. "
            "Use list-titles to see available albums."
        )
    return photos


def _collect_library_items(
    section: Any, album: Optional[str] = None
) -> List[MediaItem]:
    """Expand a library section into a flat list of playable items.

    TV show libraries are walked show -> season (>0) -> episode.
    Movie libraries return movies directly.
    Photo libraries return photos, optionally filtered to a single album.
    """
    if section.type == "show":
        items: List[MediaItem] = []
        for show in section.all():
            items.extend(_non_special_episodes(show))
        return items
    if section.type == "movie":
        return list(section.all())
    if section.type == "photo":
        return _collect_photos(section, album)  # type: ignore[return-value]
    sys.exit(
        f"Library type '{section.type}' is not supported. "
        f"Supported types: {', '.join(_LIBRARY_ITEM_TYPES)}."
    )


def _photo_file_path(photo: Photo) -> Optional[str]:
    """Return the server filesystem path for a photo, or None if unavailable."""
    try:
        return photo.media[0].parts[0].file or None
    except (IndexError, AttributeError):
        return None
