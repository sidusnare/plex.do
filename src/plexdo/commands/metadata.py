# SPDX-License-Identifier: GPL-3.0-or-later

"""Per-item metadata display command."""

from typing import Any, Dict, List
import argparse

from plexapi.audio import Track
from plexapi.server import PlexServer
from plexapi.video import Episode, Movie, Show

from plexdo.console import _cell, output
from plexdo.convert import _format_duration, normalize_rating_key
from plexdo.titles import _display_title, fetch_item


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
    item = fetch_item(plex, args.rating_key)
    builder = _METADATA_BUILDERS.get(item.type, _base_metadata)
    record: Dict[str, Any] = builder(item)

    output(record, args)


def register(
    sub: "argparse._SubParsersAction",
    parents: "List[argparse.ArgumentParser]",
) -> None:
    """Register the metadata subparser."""
    parser = sub.add_parser(
        "show-metadata", parents=parents,
        help="Display metadata for a single item by ratingKey.",
    )
    parser.add_argument(
        "rating_key", type=int,
        help="Item ratingKey (int). Obtain with list-titles or list-show.",
    )


COMMANDS = {"show-metadata": cmd_show_metadata}

REQUIRES_PLEX = frozenset(COMMANDS)
