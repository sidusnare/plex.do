# SPDX-License-Identifier: GPL-3.0-or-later

"""Playlist resolution, creation, and copy naming rules."""

from typing import List, Optional, Tuple
import argparse
import sys

from plexapi.exceptions import NotFound
from plexapi.playlist import Playlist
from plexapi.server import PlexServer

from plexdo.console import output
from plexdo.constants import LOG, MediaItem
from plexdo.convert import normalize_rating_key
from plexdo.titles import _display_title


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


def _resolve_dest_name(
    user_plex: PlexServer, desired_name: str, force_overwrite: bool = False
) -> Optional[Tuple[str, bool]]:
    """
    Return (final_name, delete_first), or None if the copy should be skipped.

    With force_overwrite (--overwrite), the desired name is always used and
    is replaced if it already exists; the ' admin copy' fallback is skipped.

    Otherwise the default naming rules apply:
    If desired_name doesn't exist -> use it.
    If desired_name exists -> fall back to desired_name + ' admin copy'.
    If BOTH already exist -> return None so the caller skips this target
    without destroying either playlist; --overwrite is required to replace.
    """
    existing = {pl.title for pl in user_plex.playlists()}
    if force_overwrite:
        return desired_name, desired_name in existing
    if desired_name not in existing:
        return desired_name, False
    candidate = desired_name + " admin copy"
    if candidate not in existing:
        return candidate, False
    return None


def _copy_playlist_to(
    src_items: List[MediaItem],
    user_plex: PlexServer,
    desired_name: str,
    args: argparse.Namespace,
    target_label: str = "target",
) -> None:
    """Copy items to user_plex under resolved name, applying naming rules."""
    resolved = _resolve_dest_name(
        user_plex, desired_name, getattr(args, "overwrite", False)
    )
    if resolved is None:
        LOG.warning(
            "Skipping %s: both %r and %r already exist. Nothing was created "
            "or deleted. Re-run with --overwrite to replace %r.",
            target_label, desired_name, desired_name + " admin copy", desired_name,
        )
        return

    final_name, overwrite = resolved
    LOG.info("Copying to '%s' (overwrite=%s)", final_name, overwrite)

    if overwrite and not args.dry_run:
        try:
            existing_pl: Playlist = user_plex.playlist(final_name)
            existing_pl.delete()
            LOG.debug("Deleted existing playlist '%s'", final_name)
        except NotFound:
            pass

    finalize_playlist(user_plex, final_name, src_items, args)
